from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta
import re


class PMSCycle(models.Model):
    _name = 'pms.cycle'
    _description = 'Performance Management Cycle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence desc, id desc'

    name = fields.Char(
        string='Cycle Name',
        store=True,
        readonly=True
    )

    sequence = fields.Char(
        string='Sequence',
        required=True,
        copy=False,
        readonly=True,
        default='New'
    )

    cycle_type = fields.Selection([
        ('annual', 'Annual (12 Months)'),
        ('semi_annual', 'Semi-Annual (6 Months)'),
        ('probation', 'Probation (3 Months)')
    ], string='Cycle Type', required=True, tracking=True, default='annual')

    start_date = fields.Date(
        string='Start Date',
        required=True,
        tracking=True
    )
    end_date = fields.Date(
        string='Planning & Monitoring End Date',
        compute='_compute_end_date',
        store=True,
        readonly=False,
        tracking=True
    )

    planning_duration = fields.Integer(
        string='Planning Duration (Days)',
        required=True,
        default=15,
        tracking=True,
        help='Number of days from start date for planning'
    )
    planning_deadline = fields.Date(
        string='Planning Deadline',
        compute='_compute_planning_deadline',
        store=True,
        readonly=True,
        help='Deadline for employees to complete their planning'
    )

    resubmission_days = fields.Integer(
        string='Resubmission Days',
        default=5,
        help='Days allowed for resubmission after HR sets plan to draft'
    )

    apply_to = fields.Selection([
        ('all', 'All Employees'),
        ('selected', 'Selected Employees')
    ], string='Apply To', required=True, default='all', tracking=True)

    employee_ids = fields.Many2many(
        'hr.employee',
        'pms_cycle_employee_rel',
        'cycle_id',
        'employee_id',
        string='Selected Employees',
        domain="[('active', '=', True), ('evaluation_group_id', '!=', False)]"
    )

    appraisal_ids = fields.One2many(
        'pms.appraisal',
        'cycle_id',
        string='Employee Appraisals'
    )

    appraisal_count = fields.Integer(  # number of employees for a particular cycle
        string='Employee Count',
        compute='_compute_appraisal_count',
        store=True
    )

    final_score_selection = fields.Selection([
        ('reviewer', 'Reviewer Score'),  # takes reviewer score as the final one
        ('average', 'Average')  # takes the average of sup + sec sup (if exists) + rev
    ], string='Final Score', required=True, default='reviewer', tracking=True,
        help="Determines how the final appraisal score is calculated for employees in this cycle.")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('planning', 'Planning'),
        ('monitoring', 'Monitoring'),
        ('appraisal', 'Appraisal'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True, copy=False)

    active = fields.Boolean(string='Active',
                            default=True)  # not the state of the cycle but whether the record is active or archived

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    # To check employees for different cycles

    is_manager_in_cycle = fields.Boolean(
        string='Is Manager',
        compute='_compute_is_manager_in_cycle',
        search='_search_is_manager_in_cycle'
    )

    def _compute_is_manager_in_cycle(self):
        is_hr = self.env.user.has_group('hr_employee_evaluation.group_pms_hr_manager')
        appraisals = self.env['pms.appraisal'].search([
            ('cycle_id', 'in', self.ids),
            '|', '|',
            ('supervisor_id.user_id', '=', self.env.uid),
            ('secondary_supervisor_id.user_id', '=', self.env.uid),
            ('reviewer_id.user_id', '=', self.env.uid),
        ])
        involved_cycle_ids = set(appraisals.mapped('cycle_id').ids)

        for cycle in self:
            if is_hr:
                cycle.is_manager_in_cycle = True
            else:
                cycle.is_manager_in_cycle = cycle.id in involved_cycle_ids

    def _search_is_manager_in_cycle(self, operator, value):
        if self.env.user.has_group('hr_employee_evaluation.group_pms_hr_manager'):
            return [('id', '!=', False)]  # God Mode for. All cycles to appear

        appraisals = self.env['pms.appraisal'].search([
            '|', '|',
            ('supervisor_id.user_id', '=', self.env.uid),
            ('secondary_supervisor_id.user_id', '=', self.env.uid),
            ('reviewer_id.user_id', '=', self.env.uid),
        ])

        if not appraisals:
            return [('id', '=', -1)]  # Forces absolute zero records (No ghost cycles)

        return [('id', 'in', appraisals.mapped('cycle_id').ids)]

    def action_open_subordinate_plans(self):
        self.ensure_one()
        is_hr = self.env.user.has_group('hr_employee_evaluation.group_pms_hr_manager')
        domain = [('cycle_id', '=', self.id)]

        if not is_hr:
            domain.extend([
                '|', '|',
                ('supervisor_id.user_id', '=', self.env.uid),
                ('secondary_supervisor_id.user_id', '=', self.env.uid),
                ('reviewer_id.user_id', '=', self.env.uid),
            ])

        return {
            'name': f'Employee Plans — {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pms.appraisal',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('hr_employee_evaluation.view_employee_plans_all_list').id, 'list'),
                (self.env.ref('hr_employee_evaluation.view_employee_plans_supervisor_form').id, 'form'),
            ],
            'domain': domain,
            'context': {'create': False, 'delete': False},
        }

    def action_open_subordinate_appraisals(self):
        self.ensure_one()
        is_hr = self.env.user.has_group('hr_employee_evaluation.group_pms_hr_manager')
        domain = [
            ('cycle_id', '=', self.id),
            ('state', 'in', [
                'appraisal_draft', 'appraisal_pending_supervisor',
                'appraisal_pending_secondary_supervisor',
                'appraisal_pending_reviewer', 'appraisal_approved',
            ])
        ]

        if not is_hr:
            domain.extend([
                '|', '|',
                ('supervisor_id.user_id', '=', self.env.uid),
                ('secondary_supervisor_id.user_id', '=', self.env.uid),
                ('reviewer_id.user_id', '=', self.env.uid),
            ])

        return {
            'name': f'Employee Appraisals — {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pms.appraisal',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('hr_employee_evaluation.view_employee_appraisals_all_list').id, 'list'),
                (self.env.ref('hr_employee_evaluation.view_employee_appraisals_supervisor_form').id, 'form'),
            ],
            'domain': domain,
            'context': {'create': False, 'delete': False},
        }

    @api.depends('cycle_type', 'start_date')
    def _compute_end_date(self):
        # Auto-compute end date based on cycle type
        for record in self:
            if not record.start_date:
                record.end_date = False
                continue

            if record.cycle_type == 'annual':
                record.end_date = record.start_date + relativedelta(years=1, days=-1)
            elif record.cycle_type == 'semi_annual':
                record.end_date = record.start_date + relativedelta(months=6, days=-1)
            elif record.cycle_type == 'probation':
                record.end_date = record.start_date + relativedelta(months=3, days=-1)

    @api.depends('start_date', 'planning_duration')
    def _compute_planning_deadline(self):
        # Compute planning deadline
        for record in self:
            if record.start_date and record.planning_duration:
                record.planning_deadline = record.start_date + relativedelta(days=record.planning_duration)
            else:
                record.planning_deadline = False

    @api.depends('appraisal_ids')
    def _compute_appraisal_count(self):
        for record in self:
            record.appraisal_count = len(record.appraisal_ids)

    @api.constrains('start_date', 'end_date', 'appraisal_end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date:
                if record.end_date <= record.start_date:
                    raise ValidationError(
                        'Planning & Monitoring End Date must be after Start Date.'
                    )
            if record.appraisal_end_date and record.appraisal_start_date:
                if record.appraisal_end_date <= record.appraisal_start_date:
                    raise ValidationError(
                        'Appraisal End Date must be after Appraisal Start Date '
                        f'({record.appraisal_start_date}).'
                    )

    @api.constrains('planning_duration')
    def _check_planning_duration(self):
        for record in self:
            if record.planning_duration <= 0:
                raise ValidationError('Planning duration must be greater than 0.')

    @api.constrains('appraisal_duration', 'appraisal_start_date', 'appraisal_end_date')
    def _check_appraisal_duration(self):
        for record in self:
            if record.appraisal_duration <= 0:
                raise ValidationError('Appraisal Duration must be greater than 0 days.')

            if record.appraisal_start_date and record.appraisal_end_date and record.appraisal_duration:
                half = record.appraisal_duration // 2
                employee_deadline = record.appraisal_start_date + relativedelta(days=half)

                # End date must be after start date
                if record.appraisal_end_date <= record.appraisal_start_date:
                    raise ValidationError(
                        f'Appraisal End Date ({record.appraisal_end_date}) '
                        f'must be after Appraisal Start Date ({record.appraisal_start_date}).'
                    )

                # Employee deadline must not exceed end date
                if employee_deadline > record.appraisal_end_date:
                    raise ValidationError(
                        f'Appraisal Duration is too long.\n\n'
                        f'  Start Date         : {record.appraisal_start_date}\n'
                        f'  Duration           : {record.appraisal_duration} days\n'
                        f'  End Date           : {record.appraisal_end_date}\n'
                        f'  Employee Deadline  : {employee_deadline} '
                        f'(Start + {half} days)\n\n'
                        f'The Employee Self-Rating Deadline ({employee_deadline}) '
                        f'falls after the Appraisal End Date ({record.appraisal_end_date}).\n'
                        f'Please either reduce the Duration or extend the End Date.'
                    )

    @api.constrains('employee_ids', 'apply_to')
    def _check_selected_employees(self):
        for record in self:
            if record.apply_to == 'selected' and not record.employee_ids:
                raise ValidationError('Please select at least one employee.')

    # @api.model_create_multi
    # def create(self, vals_list):
    #     for vals in vals_list:
    #         if vals.get('sequence', 'New') == 'New':
    #             vals['sequence'] = self.env['ir.sequence'].next_by_code('pms.cycle') or 'New'

    #         if vals.get('name'):
    #             if vals.get('start_date'):
    #                 cycle_year = vals['start_date'][:4]
    #             else:
    #                 cycle_year = fields.Date.today().year

    #             vals['name'] = f"{vals['name']} - {cycle_year}"

    #     return super().create(vals_list)

    @api.onchange('name', 'start_date')
    def _onchange_name_date(self):
        for record in self:
            if record.name and record.start_date:
                year = str(record.start_date.year)
                base_name = re.sub(r' - \d{4}$', '', record.name).strip()
                record.name = f"{base_name} - {year}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sequence', 'New') == 'New':
                vals['sequence'] = self.env['ir.sequence'].next_by_code('pms.cycle') or 'New'

            if vals.get('name') and vals.get('start_date'):
                year = str(vals['start_date'])[:4]
                base_name = re.sub(r' - \d{4}$', '', vals['name']).strip()
                vals['name'] = f"{base_name} - {year}"

        return super().create(vals_list)

    # def write(self, vals):
    #     if not self.env.context.get('skip_cycle_edit_check'):
    #         protected_fields = [
    #             'cycle_type', 'start_date', 'apply_to',
    #             'employee_ids', 'final_score_selection'
    #         ]
    #         if any(field in vals for field in protected_fields):
    #             for record in self:
    #                 if record.state != 'draft':
    #                     raise UserError('Cannot modify cycle configuration after activation.')
    #     return super().write(vals)

    def write(self, vals):
        if not self.env.context.get('skip_cycle_edit_check'):
            protected_fields = [
                'cycle_type', 'start_date', 'apply_to',
                'employee_ids', 'final_score_selection'
            ]
            if any(f in vals for f in protected_fields):
                for record in self:
                    if record.state != 'draft':
                        raise UserError(
                            'Cannot modify cycle configuration after activation.'
                        )

        # ── Planning duration guard ───────────────────────────────────────
        duration_snapshots = {}
        if 'planning_duration' in vals:
            new_duration = vals['planning_duration']
            for cycle in self:
                if cycle.state not in ('draft', 'planning', 'monitoring'):
                    raise UserError(
                        'Planning duration can only be changed while the cycle '
                        'is in Draft, Planning, or Monitoring state.'
                    )
                if cycle.state != 'draft' and new_duration < cycle.planning_duration:
                    raise UserError(
                        f'Cannot reduce the planning duration after a cycle has '
                        f'been activated.\n\n'
                        f'Current duration: {cycle.planning_duration} days\n'
                        f'Requested duration: {new_duration} days\n\n'
                        f'You may only extend it.'
                    )
                duration_snapshots[cycle.id] = {
                    'old_duration': cycle.planning_duration,
                    'old_state': cycle.state,
                }

        # ── Appraisal End Date guard ──────────────────────────────────────
        if 'appraisal_end_date' in vals and not self.env.context.get('skip_cycle_edit_check'):
            new_ap_end = vals.get('appraisal_end_date')
            if new_ap_end and isinstance(new_ap_end, str):
                from datetime import datetime
                new_ap_end = datetime.strptime(new_ap_end, '%Y-%m-%d').date()
            elif not new_ap_end:
                new_ap_end = None

            for cycle in self:
                if cycle.state not in ('draft', 'planning', 'monitoring', 'appraisal'):
                    raise UserError(
                        'Appraisal End Date can only be changed while the cycle '
                        'is in Draft, Planning, Monitoring, or Appraisal state.'
                    )
                if new_ap_end:
                    ap_duration = vals.get('appraisal_duration') or cycle.appraisal_duration
                    ap_start = cycle.appraisal_start_date
                    if ap_start and ap_duration:
                        half = ap_duration // 2
                        fresh_employee_deadline = ap_start + relativedelta(days=half)
                        if new_ap_end < fresh_employee_deadline:
                            raise UserError(
                                f'Appraisal End Date ({new_ap_end}) cannot be before '
                                f'the Employee Self-Rating Deadline '
                                f'({fresh_employee_deadline}).'
                            )
        # ─────────────────────────────────────────────────────────────────

        res = super().write(vals)

        # ── Post-write: planning duration change side effects ─────────────
        if duration_snapshots:
            today = fields.Date.today()
            for cycle in self:
                snap = duration_snapshots.get(cycle.id)
                if not snap:
                    continue
                old_duration = snap['old_duration']
                old_state = snap['old_state']
                new_duration = cycle.planning_duration
                delta = new_duration - old_duration

                if delta == 0:
                    continue

                pending = cycle.appraisal_ids.filtered(
                    lambda a: a.state != 'approved'
                )
                for appraisal in pending:
                    if appraisal.planning_end_date:
                        appraisal.with_context(skip_edit_check=True).write({
                            'planning_end_date': (
                                    appraisal.planning_end_date + relativedelta(days=delta)
                            )
                        })

                moved_back = False
                if (
                        old_state == 'monitoring'
                        and cycle.planning_deadline
                        and cycle.planning_deadline > today
                ):
                    cycle.write({'state': 'planning'})
                    moved_back = True

                deadline_str = str(cycle.planning_deadline) if cycle.planning_deadline else '—'
                if moved_back:
                    body = (
                        f'Planning duration extended from {old_duration} to {new_duration} days '
                        f'(new deadline: {deadline_str}). Cycle automatically moved back to '
                        f'Planning phase. {len(pending)} pending appraisal deadline(s) updated.'
                    )
                else:
                    body = (
                        f'Planning duration extended from {old_duration} to {new_duration} days '
                        f'(new deadline: {deadline_str}). '
                        f'{len(pending)} pending appraisal deadline(s) updated.'
                    )
                cycle.message_post(body=body, message_type='notification')
        # ─────────────────────────────────────────────────────────────────

        return res

    # def write(self, vals):
    #     # Prevent editing fields when not in draft
    #     protected_fields = [
    #         'cycle_type', 'start_date', 'apply_to',
    #         'employee_ids', 'final_score_selection'
    #     ]
    #     if any(field in vals for field in protected_fields):
    #         for record in self:
    #             if record.state != 'draft':
    #                 raise UserError('Cannot modify cycle configuration after activation.')
    #     return super().write(vals)

    def unlink(self):
        # Prevent deletion of non-draft cycles
        for record in self:
            if record.state != 'draft':
                raise UserError('Cannot delete activated cycles. Cancel them instead.')
        return super().unlink()

    def action_activate_cycle(self):
        self.ensure_one()

        if self.state != 'draft':
            raise UserError('Only draft cycles can be activated.')

        active_states = ['planning', 'monitoring', 'appraisal']
        if self.cycle_type in ['annual', 'semi_annual']:
            if self.search_count([
                ('state', 'in', active_states),
                ('cycle_type', 'in', ['annual', 'semi_annual']),
                ('id', '!=', self.id)
            ]):
                raise UserError(
                    'Cannot activate: A Regular cycle (Annual or Semi-Annual) is already active. '
                    'Please complete or cancel it first.'
                )
        elif self.cycle_type == 'probation':
            if self.search_count([
                ('state', 'in', active_states),
                ('cycle_type', '=', 'probation'),
                ('id', '!=', self.id)
            ]):
                raise UserError(
                    'Cannot activate: A Probation cycle is already active. '
                    'Please complete or cancel it first.'
                )

        if not self.start_date or not self.end_date:
            raise UserError('Start date and Planning & Monitoring End Date must be set.')
        if not self.appraisal_end_date:
            raise UserError('Appraisal End Date must be set before activating the cycle.')
        if self.appraisal_end_date <= self.appraisal_start_date:
            raise UserError(
                f'Appraisal End Date ({self.appraisal_end_date}) must be after '
                f'Appraisal Start Date ({self.appraisal_start_date}).'
            )

        if self.apply_to == 'all':
            domain = [
                ('active', '=', True),
                ('evaluation_group_id', '!=', False)
            ]
            if self.cycle_type in ['annual', 'semi_annual']:
                domain.append(('category_ids.name', 'ilike', 'Regular'))
            elif self.cycle_type == 'probation':
                domain.append(('category_ids.name', 'ilike', 'Probation'))

            employees = self.env['hr.employee'].search(domain)
            if not employees:
                raise UserError(
                    "No employees found with an Evaluation Group and the required tag."
                )
            self.with_context(skip_cycle_edit_check=True).write({
                'employee_ids': [(6, 0, employees.ids)]
            })
        else:
            employees = self.employee_ids
            if not employees:
                raise UserError('No employees selected to create appraisals.')

        self._validate_employees(employees)
        self._create_employee_appraisals(employees, is_late=False)

        self.with_context(skip_cycle_edit_check=True).write({'state': 'planning'})

        self.message_post(
            body=f"Cycle activated. {len(employees)} employee appraisals created.",
            message_type='notification'
        )
        return True

    # def action_activate_cycle(self):
    #     self.ensure_one()

    #     if self.state != 'draft':
    #         raise UserError('Only draft cycles can be activated.')

    #     if not self.start_date or not self.end_date:
    #         raise UserError('Start date and end date must be set.')

    #     if self.apply_to == 'all':
    #         employees = self.env['hr.employee'].search([
    #             ('active', '=', True),
    #             ('evaluation_group_id', '!=', False)
    #         ])
    #         # Force the employee_ids list to populate so we can view them in the UI!
    #         self.write({'employee_ids': [(6, 0, employees.ids)]})
    #     else:
    #         employees = self.employee_ids

    #     if not employees:
    #         raise UserError('No employees found to create appraisals.')

    #     self._validate_employees(employees)
    #     self._create_employee_appraisals(employees, is_late=False)

    #     self.write({'state': 'planning'})

    #     self.message_post(
    #         body=f"Cycle activated. {len(employees)} employee appraisals created.",
    #         message_type='notification'
    #     )
    #     return True

    def _validate_employees(self, employees):
        """Reusable validation for activating cycles and adding late employees"""
        error_messages = []

        # ─── Tag Validation for Manual Selection ───
        invalid_for_regular = self.env['hr.employee']
        invalid_for_probation = self.env['hr.employee']

        for e in employees:
            # Extract all tags for the employee and convert to lowercase for safe checking
            tags = [tag.lower() for tag in e.category_ids.mapped('name') if tag]
            has_probation = any('probation' in t for t in tags)

            if self.cycle_type in ['annual', 'semi_annual']:
                # Regular cycles can have any tag EXCEPT Probation
                if has_probation:
                    invalid_for_regular |= e
            elif self.cycle_type == 'probation':
                # Probation cycles MUST have the Probation tag
                if not has_probation:
                    invalid_for_probation |= e

        if invalid_for_regular:
            names = "\n".join([f"- {e.name}" for e in invalid_for_regular])
            error_messages.append(
                f"Regular cycles CANNOT include employees on Probation. "
                f"Please remove these employees or update their tags:\n{names}\n"
            )

        if invalid_for_probation:
            names = "\n".join([f"- {e.name}" for e in invalid_for_probation])
            error_messages.append(
                f"Probation cycles can ONLY include employees with the 'Probation' tag. "
                f"Please remove these employees or update their tags:\n{names}\n"
            )

        active_appraisals = self.env['pms.appraisal'].search([
            ('employee_id', 'in', employees.ids),
            ('cycle_id', '!=', self.id),
            ('cycle_id.state', 'not in', ['draft', 'completed', 'cancelled'])
        ])

        if active_appraisals:
            busy_employee_names = list(set(active_appraisals.mapped('employee_id.name')))
            names = "\n".join([f"- {name}" for name in busy_employee_names])
            error_messages.append(f"The following employees already have an active cycle:\n{names}\n")

        employees_missing_supervisor = employees.filtered(lambda e: not e.parent_id)
        employees_missing_reviewer = employees.filtered(lambda e: not e.reviewer_id)

        if employees_missing_supervisor:
            names = "\n".join([f"- {e.name}" for e in employees_missing_supervisor])
            error_messages.append(f"The following employees do not have a Supervisor assigned:\n{names}\n")

        if employees_missing_reviewer:
            names = "\n".join([f"- {e.name}" for e in employees_missing_reviewer])
            error_messages.append(f"The following employees do not have a Reviewer assigned:\n{names}\n")

        employees_missing_group = employees.filtered(lambda e: not e.evaluation_group_id)
        employees_with_group = employees - employees_missing_group

        if employees_with_group:
            unique_groups = employees_with_group.mapped('evaluation_group_id')
            valid_templates = self.env['appraisal.template'].search([
                ('evaluation_group_id', 'in', unique_groups.ids),
                ('active', '=', True)
            ])
            valid_group_ids = valid_templates.mapped('evaluation_group_id.id')
            employees_missing_template = employees_with_group.filtered(
                lambda e: e.evaluation_group_id.id not in valid_group_ids
            )
        else:
            employees_missing_template = self.env['hr.employee']

        total_template_errors = employees_missing_group | employees_missing_template

        if total_template_errors:
            names = "\n".join(
                [f"- {e.name} (Group: {e.evaluation_group_id.name or 'None'})" for e in total_template_errors])
            error_messages.append(
                f"The following employees do not have a valid Appraisal Template assigned:\n{names}\n"
                "Please ensure they have an Evaluation Group assigned and a valid Template.\n"
            )

        if error_messages:
            full_error = "\n\n".join(error_messages)
            raise UserError(f"Cannot proceed due to configuration errors:\n\n{full_error}")

    def _create_employee_appraisals(self, employees, is_late=False):
        AppraisalObj = self.env['pms.appraisal']
        created_count = 0
        created_appraisals = self.env['pms.appraisal']

        for employee in employees:
            template = self.env['appraisal.template'].search([
                ('evaluation_group_id', '=', employee.evaluation_group_id.id),
                ('active', '=', True)
            ], limit=1)

            if not template:
                continue

            existing = AppraisalObj.search([('cycle_id', '=', self.id), ('employee_id', '=', employee.id)], limit=1)
            if existing:
                continue

            # Calculate custom dates if employee is added late
            start_date = fields.Date.today() if is_late else self.start_date
            end_date = start_date + relativedelta(days=self.planning_duration) if is_late else self.planning_deadline

            supervisor = employee.parent_id
            sec_supervisor = employee.secondary_manager_id
            reviewer = employee.reviewer_id

            appraisal = AppraisalObj.create({
                'cycle_id': self.id,
                'employee_id': employee.id,
                'template_id': template.id,
                'supervisor_id': supervisor.id if supervisor else False,
                'secondary_supervisor_id': sec_supervisor.id if sec_supervisor else False,
                'reviewer_id': reviewer.id if reviewer else False,
                'planning_start_date': start_date,
                'planning_end_date': end_date,
            })

            appraisal._clone_template_structure()
            created_appraisals |= appraisal
            created_count += 1

        if created_appraisals:
            self._notify_employees(created_appraisals)

        return created_count

    def action_open_add_employee_wizard(self):
        self.ensure_one()
        return {
            'name': 'Add Employees to Cycle',
            'type': 'ir.actions.act_window',
            'res_model': 'pms.add.employee.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_cycle_id': self.id}
        }

    def _notify_employees(self, appraisals):
        # Notify employees that their performance plan is ready
        ActivityType = self.env['mail.activity.type']

        # Get or create activity type for PMS notifications
        activity_type = ActivityType.search([
            ('name', '=', 'Performance Plan'),
            ('category', '=', 'default')
        ], limit=1)

        if not activity_type:
            # Use default todo activity type
            activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)

        for appraisal in appraisals:
            # Only notify if employee has a user account
            if appraisal.employee_id.user_id:
                try:
                    # Create activity for employee
                    appraisal.activity_schedule(
                        activity_type_id=activity_type.id if activity_type else False,
                        summary=f'New Performance Plan - {self.name}',
                        note=f'Your performance plan for {self.name} is now active. '
                             f'Planning deadline: {self.planning_deadline.strftime("%B %d, %Y")}. '
                             f'Please review and submit your plan before the deadline.',
                        user_id=appraisal.employee_id.user_id.id,
                        date_deadline=self.planning_deadline
                    )

                    # send an email notification
                    appraisal.message_post(
                        body=f"""Dear {appraisal.employee_id.name}, your performance plan for {self.name} is now active.""",
                        subject=f'Performance Plan Active - {self.name}',
                        message_type='notification',
                        subtype_xmlid='mail.mt_comment'
                    )
                except Exception as e:
                    # Log error but don't fail the entire activation
                    self.message_post(
                        body=f"Warning: Could not notify {appraisal.employee_id.name}: {str(e)}",
                        message_type='comment'
                    )

    def _get_unapproved_appraisals(self):
        """Return appraisals in this cycle that have not yet reached 'approved' state."""
        planning_states = {'draft', 'pending_supervisor', 'pending_secondary_supervisor', 'pending_reviewer'}
        return self.appraisal_ids.filtered(lambda a: a.state in planning_states)

    def action_move_to_monitoring(self):
        """Manually move cycle from planning to monitoring phase."""
        self.ensure_one()

        if self.state != 'planning':
            raise UserError('Only cycles in the Planning phase can be moved to Monitoring.')

        unapproved = self._get_unapproved_appraisals()
        if unapproved:
            names = '\n'.join(
                f'  \u2022 {a.employee_id.name} ({dict(a._fields["state"].selection).get(a.state, a.state)})'
                for a in unapproved
            )
            raise UserError(
                f'Cannot move to Monitoring. The following {len(unapproved)} employee plan(s) '
                f'have not been approved yet:\n\n{names}\n\n'
                f'All plans must reach "Approved" status before the cycle can move to Monitoring.'
            )

        self.write({'state': 'monitoring'})
        self.message_post(
            body=f"Moved to Monitoring phase. All {len(self.appraisal_ids)} plans approved — plans are now locked.",
            message_type='notification'
        )
        return True

    def action_complete_cycle(self):
        """Mark cycle as completed"""
        self.ensure_one()

        if self.state not in ['planning', 'appraisal']:
            raise UserError('Cannot complete cycle from this state.')

        self.write({'state': 'completed'})

        return True

    def action_cancel_cycle(self):
        """Cancel the cycle"""
        self.ensure_one()

        if self.state == 'completed':
            raise UserError('Cannot cancel completed cycles.')

        self.write({'state': 'cancelled', 'active': False})

        return True

    def action_view_appraisals(self):
        self.ensure_one()

        return {
            'name': f'Appraisals - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pms.appraisal',
            'view_mode': 'list,form',
            'domain': [('cycle_id', '=', self.id)],
            'context': {'default_cycle_id': self.id}
        }

    @api.model
    def _cron_auto_move_to_monitoring(self):
        """
        Cron: auto-move cycles whose planning deadline has passed to Monitoring.
        Cycles with unapproved plans are skipped and a chatter message is posted
        so HR can see which employees are still pending.
        """
        today = fields.Date.today()
        expired_planning_cycles = self.search([
            ('state', '=', 'planning'),
            ('planning_deadline', '<', today)
        ])

        for cycle in expired_planning_cycles:
            unapproved = cycle._get_unapproved_appraisals()
            if unapproved:
                names = ', '.join(a.employee_id.name for a in unapproved)
                cycle.message_post(
                    body=(
                        f'⚠️ Cycle could not be automatically moved to Monitoring '
                        f'because {len(unapproved)} plan(s) are still pending approval: '
                        f'{names}. Please approve all plans before moving to Monitoring.'
                    ),
                    message_type='notification'
                )
            else:
                cycle.write({'state': 'monitoring'})
                cycle.message_post(
                    body=f"Automatically moved to Monitoring phase. All {len(cycle.appraisal_ids)} plans were approved.",
                    message_type='notification'
                )

    appraisal_end_date = fields.Date(
        string='Appraisal End Date',
        compute='_compute_appraisal_end_date',
        store=True,
        readonly=False,  # allow HR to override manually
        tracking=True,
        help='Last day of the appraisal phase. Auto-computed from Appraisal Start Date + Duration.'
    )

    appraisal_duration = fields.Integer(
        string='Appraisal Duration (Days)',
        required=True,
        default=30,
        tracking=True,
        help='Total number of days for the appraisal phase. '
             'Must not push past the Appraisal End Date. '
             'Can only be extended after activation.'
    )

    appraisal_employee_deadline = fields.Date(
        string='Employee Self-Rating Deadline',
        compute='_compute_appraisal_employee_deadline',
        store=True,
        readonly=True,
        help='Deadline for employees to submit self-ratings: '
             'Appraisal Start Date + floor(Appraisal Duration / 2).'
    )
    appraisal_start_date = fields.Date(
        string='Appraisal Start Date',
        compute='_compute_appraisal_start_date',
        store=True,
        readonly=True,
        tracking=True,
        help='Automatically set to the day after the Planning & Monitoring End Date.'
    )

    @api.depends('end_date')
    def _compute_appraisal_start_date(self):
        for record in self:
            if record.end_date:
                record.appraisal_start_date = record.end_date + relativedelta(days=1)
            else:
                record.appraisal_start_date = False

    @api.depends('appraisal_start_date', 'appraisal_duration')
    def _compute_appraisal_end_date(self):
        for record in self:
            if record.appraisal_start_date and record.appraisal_duration:
                record.appraisal_end_date = (
                        record.appraisal_start_date + relativedelta(days=record.appraisal_duration)
                )
            else:
                record.appraisal_end_date = False


    @api.depends('appraisal_start_date', 'appraisal_duration')
    def _compute_appraisal_employee_deadline(self):
        for record in self:
            if record.appraisal_start_date and record.appraisal_duration:
                half = record.appraisal_duration // 2  # floor for odd numbers
                record.appraisal_employee_deadline = (
                        record.appraisal_start_date + relativedelta(days=half)
                )
            else:
                record.appraisal_employee_deadline = False


    def action_move_to_appraisal(self):
        self.ensure_one()

        if self.state != 'monitoring':
            raise UserError('Only cycles in the Monitoring phase can be moved to Appraisal.')

        # Freeze planning_state for ALL appraisals before transitioning
        for appraisal in self.appraisal_ids:
            appraisal.with_context(skip_edit_check=True).write({
                'planning_state': appraisal.state,
            })

        approved_appraisals = self.appraisal_ids.filtered(
            lambda a: a.state == 'approved'
        )

        if approved_appraisals:
            approved_appraisals.with_context(skip_edit_check=True).write({
                'state': 'appraisal_draft'
            })

        self.write({'state': 'appraisal'})

        self.message_post(
            body=f"Moved to Appraisal phase. {len(approved_appraisals)} plans unlocked for employee self-rating.",
            message_type='notification'
        )
        return True

    @api.model
    def _cron_auto_move_to_appraisal(self):
        today = fields.Date.today()
        # Move state to appraisal automatically after appraisal_start_date reaches
        ready_appraisal_cycles = self.search([
            ('state', '=', 'monitoring'),
            ('appraisal_start_date', '<=', today)
        ])

        for cycle in ready_appraisal_cycles:
            cycle.action_move_to_appraisal()

    @api.constrains('state', 'cycle_type')
    def _check_concurrent_active_cycles(self):
        active_states = ['planning', 'monitoring', 'appraisal']
        for cycle in self:
            if cycle.state in active_states:
                domain = [('state', 'in', active_states), ('id', '!=', cycle.id)]

                if cycle.cycle_type in ['annual', 'semi_annual']:
                    domain.append(('cycle_type', 'in', ['annual', 'semi_annual']))
                    if self.search_count(domain):
                        raise ValidationError('Only one Regular cycle (Annual or Semi-Annual) can be active at a time.')

                elif cycle.cycle_type == 'probation':
                    domain.append(('cycle_type', '=', 'probation'))
                    if self.search_count(domain):
                        raise ValidationError('Only one Probation cycle can be active at a time.')
