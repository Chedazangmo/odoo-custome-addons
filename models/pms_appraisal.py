from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta


class PMSAppraisal(models.Model):
    _name = 'pms.appraisal'
    _description = 'Employee Performance Appraisal'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Appraisal Name',
        compute='_compute_name',
        store=True,
        readonly=True
    )

    cycle_id = fields.Many2one(
        'pms.cycle',
        string='Performance Cycle',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True
    )

    template_id = fields.Many2one(
        'appraisal.template',
        string='Template Used',
        required=True,
        ondelete='restrict',
        tracking=True
    )

    supervisor_id = fields.Many2one(
        'hr.employee',
        string='Supervisor',
        tracking=True,
        help='Direct manager who will review this appraisal'
    )

    reviewer_id = fields.Many2one(
        'hr.employee',
        string='Reviewer',
        tracking=True,
        help='Final reviewer'
    )

    kra_ids = fields.One2many(
        'pms.appraisal.kra',
        'appraisal_id',
        string='Key Result Areas'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_supervisor', 'Supervisor Approval'),
        ('pending_reviewer', 'Reviewer Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', required=True, tracking=True, copy=False)

    submitted_date = fields.Datetime(string='Submitted Date', readonly=True, tracking=True)
    supervisor_review_date = fields.Datetime(string='Supervisor Review Date', readonly=True, tracking=True)
    reviewer_approval_date = fields.Datetime(string='Reviewer Approval Date', readonly=True, tracking=True)
    rejection_date = fields.Datetime(string='Rejection Date', readonly=True, tracking=True)

    resubmission_deadline = fields.Datetime(
        string='Resubmission Deadline',
        readonly=True,
        compute='_compute_resubmission_deadline',
        store=True,
        help='Deadline for resubmission after rejection'
    )

    kra_count = fields.Integer(string='KRA Count', compute='_compute_kra_count', store=True)
    selected_kpi_count = fields.Integer(string='Selected KPIs', compute='_compute_kpi_counts', store=True)
    total_kpi_count = fields.Integer(string='Total KPIs', compute='_compute_kpi_counts', store=True)

    planning_progress = fields.Float(
        string='Planning Progress (%)',
        compute='_compute_planning_progress',
        store=True
    )

    is_own_appraisal = fields.Boolean(
        string='Is Own Appraisal',
        compute='_compute_access_flags',
        help='True if the current user is the employee of this appraisal'
    )

    is_supervisor_of_appraisal = fields.Boolean(
        string='Is Supervisor',
        compute='_compute_access_flags',
        help='True if the current user is the supervisor of this appraisal'
    )

    can_employee_edit = fields.Boolean(
        string='Can Employee Edit',
        compute='_compute_access_flags',
        help='True only when: current user is the employee, state is draft/rejected, '
             'within planning deadline, and cycle is in planning phase'
    )

    can_supervisor_add_remarks = fields.Boolean(
        string='Can Supervisor Add Remarks',
        compute='_compute_access_flags',
        help='True only when: current user is the supervisor, state is pending_supervisor, '
             'and cycle is in planning phase'
    )

    is_editable = fields.Boolean(
        string='Is Editable',
        compute='_compute_access_flags',
        help='Generic editability flag (used by existing XML). '
             'True only for the employee when conditions are met.'
    )

    is_past_planning_deadline = fields.Boolean(
        string='Past Planning Deadline',
        compute='_compute_is_past_planning_deadline'
    )

    active = fields.Boolean(string='Active', default=True)

    company_id = fields.Many2one(
        'res.company',
        related='employee_id.company_id',
        store=True,
        readonly=True
    )

    # Related convenience fields
    employee_job_id = fields.Many2one(
        'hr.job', related='employee_id.job_id',
        string='Job Position', store=False, readonly=True
    )
    employee_department_id = fields.Many2one(
        'hr.department', related='employee_id.department_id',
        string='Department', store=False, readonly=True
    )
    employee_evaluation_group_id = fields.Many2one(
        'pms.evaluation.group', related='employee_id.evaluation_group_id',
        string='Evaluation Group', store=False, readonly=True
    )

    planning_start_date = fields.Date(
        related='cycle_id.start_date',
        string='Planning Start', store=False, readonly=True
    )
    planning_end_date = fields.Date(
        related='cycle_id.planning_deadline',
        string='Planning Deadline', store=False, readonly=True
    )
    template_total_score = fields.Float(
        related='template_id.total_kpi_score',
        string='Template Total Score', store=False, readonly=True,
        help='Original template total for validation'
    )
    current_total_score = fields.Float(
        string='Current Total Score',
        compute='_compute_current_total_score',
        help='Sum of selected KPI scores'
    )

    @api.depends('employee_id', 'cycle_id')
    def _compute_name(self):
        for record in self:
            if record.employee_id and record.cycle_id:
                record.name = f"{record.employee_id.name} - {record.cycle_id.name}"
            else:
                record.name = 'New Appraisal'

    @api.depends('kra_ids')
    def _compute_kra_count(self):
        for record in self:
            record.kra_count = len(record.kra_ids)

    @api.depends('kra_ids.kpi_ids', 'kra_ids.kpi_ids.is_selected')
    def _compute_kpi_counts(self):
        for record in self:
            all_kpis = record.kra_ids.mapped('kpi_ids')
            record.total_kpi_count = len(all_kpis)
            record.selected_kpi_count = len(all_kpis.filtered(lambda k: k.is_selected))

    @api.depends('kra_ids.kpi_ids', 'kra_ids.kpi_ids.is_selected',
                 'kra_ids.kpi_ids.target', 'kra_ids.kpi_ids.planning_remarks')
    def _compute_planning_progress(self):
        for record in self:
            all_kpis = record.kra_ids.mapped('kpi_ids')
            selected_kpis = all_kpis.filtered(lambda k: k.is_selected)
            if not selected_kpis:
                record.planning_progress = 0.0
                continue
            completed = sum(1 for kpi in selected_kpis if kpi.target and kpi.planning_remarks)
            record.planning_progress = (completed / len(selected_kpis)) * 100

    @api.depends('kra_ids.kpi_ids', 'kra_ids.kpi_ids.is_selected', 'kra_ids.kpi_ids.weightage')
    def _compute_current_total_score(self):
        for record in self:
            selected_kpis = record.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)
            record.current_total_score = sum(selected_kpis.mapped('weightage'))

    @api.depends(
        'state',
        'employee_id.user_id',
        'supervisor_id.user_id',
        'cycle_id.state',
        'cycle_id.planning_deadline',
        'rejection_date',
        'resubmission_deadline',
    )
    def _compute_access_flags(self):
        current_user = self.env.user
        today = fields.Date.today()
        now = fields.Datetime.now()

        for record in self:
            emp_user = record.employee_id.user_id
            sup_user = record.supervisor_id.user_id

            is_own = bool(emp_user and emp_user.id == current_user.id)
            is_sup = bool(sup_user and sup_user.id == current_user.id)
            cycle_in_planning = record.cycle_id.state == 'planning'

            record.is_own_appraisal = is_own
            record.is_supervisor_of_appraisal = is_sup

            # --- can_employee_edit ---
            if not is_own or not cycle_in_planning:
                record.can_employee_edit = False
            elif record.state == 'approved':
                record.can_employee_edit = False
            elif record.cycle_id.planning_deadline and record.cycle_id.planning_deadline < today:
                # Past deadline: only editable if rejected and within resubmission window
                if record.state == 'rejected' and record.resubmission_deadline:
                    record.can_employee_edit = now <= record.resubmission_deadline
                else:
                    record.can_employee_edit = False
            elif record.state in ('draft', 'rejected'):
                if record.state == 'rejected' and record.resubmission_deadline:
                    record.can_employee_edit = now <= record.resubmission_deadline
                else:
                    record.can_employee_edit = True
            else:
                # pending_supervisor, pending_reviewer, etc.
                record.can_employee_edit = False

            # can_supervisor_add_remarks is True ONLY when: current user is the supervisor, plan has been
            # submitted (pending_supervisor), and the cycle is still in planning.
            record.can_supervisor_add_remarks = bool(
                is_sup
                and record.state == 'pending_supervisor'
                and cycle_in_planning
            )

            # Backward-compat alias
            record.is_editable = record.can_employee_edit

    @api.depends('cycle_id.planning_deadline')
    def _compute_is_past_planning_deadline(self):
        today = fields.Date.today()
        for record in self:
            record.is_past_planning_deadline = bool(
                record.cycle_id.planning_deadline
                and record.cycle_id.planning_deadline < today
            )

    @api.depends('rejection_date', 'cycle_id.resubmission_days')
    def _compute_resubmission_deadline(self):
        for record in self:
            if record.rejection_date and record.cycle_id.resubmission_days:
                record.resubmission_deadline = record.rejection_date + timedelta(
                    days=record.cycle_id.resubmission_days
                )
            else:
                record.resubmission_deadline = False

    @api.constrains('employee_id', 'cycle_id')
    def _check_unique_employee_cycle(self):
        for record in self:
            existing = self.search([
                ('employee_id', '=', record.employee_id.id),
                ('cycle_id', '=', record.cycle_id.id),
                ('id', '!=', record.id)
            ])
            if existing:
                raise ValidationError(
                    f'An appraisal for {record.employee_id.name} in cycle '
                    f'{record.cycle_id.name} already exists.'
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'employee_id' in vals and 'supervisor_id' not in vals:
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                if employee.parent_id:
                    vals['supervisor_id'] = employee.parent_id.id
        return super().create(vals_list)

    def write(self, vals):
        # The OWL widget always sends the full KPI row on save not just the
        # changed field. So we strip the payload per-role before it hits
        # the database, not just check whether kra_ids is present.

        # Roles:
        #   Employee (can_employee_edit=True):
        #       kra_ids → kpi_ids → is_selected, target, planning_remarks, weightage
        #   Supervisor (can_supervisor_add_remarks=True):
        #       kra_ids → kpi_ids → supervisor_planning_remarks  ← ONLY this field
        #   HR (skip_edit_check context):
        #       Unrestricted — used by action methods for state transitions.
        #   Everyone else: denied.
        # Action methods bypass this guard via context flag.
        if self.env.context.get('skip_edit_check'):
            return super().write(vals)

        system_fields = {
            'state', 'submitted_date', 'supervisor_review_date',
            'reviewer_approval_date', 'rejection_date', 'active',
        }

        user_facing_fields = set(vals.keys()) - system_fields

        # Nothing user-facing — let through (e.g. pure state change).
        if not user_facing_fields:
            return super().write(vals)

        current_user = self.env.user
        is_hr = current_user.has_group('hr_employee_evaluation.group_pms_hr_manager')

        # Fields the employee is permitted to change on a KPI row.
        EMPLOYEE_KPI_FIELDS = {'is_selected', 'target', 'planning_remarks', 'weightage'}

        # Fields the supervisor is permitted to change on a KPI row.
        SUPERVISOR_KPI_FIELDS = {'target'} #{'supervisor_planning_remarks', 'target'}

        filtered_vals = dict(vals)

        for record in self:
            if record.can_employee_edit:
                # Employee path — strip supervisor-only fields from any kra_ids payload.
                if 'kra_ids' in filtered_vals:
                    filtered_vals['kra_ids'] = self._filter_kra_commands(
                        filtered_vals['kra_ids'],
                        allowed_kpi_fields=EMPLOYEE_KPI_FIELDS,
                    )
                non_kra = user_facing_fields - {'kra_ids'}
                if non_kra and not is_hr:
                    raise UserError(
                        'You do not have permission to modify these fields on a performance plan.'
                    )

            elif record.can_supervisor_add_remarks:
                # strip everything from each KPI row except supervisor_planning_remarks
                if 'kra_ids' in filtered_vals:
                    filtered_vals['kra_ids'] = self._filter_kra_commands(
                        filtered_vals['kra_ids'],
                        allowed_kpi_fields=SUPERVISOR_KPI_FIELDS,
                    )
                non_kra = user_facing_fields - {'kra_ids'}
                if non_kra:
                    raise UserError(
                        'You do not have permission to modify these fields on a performance plan.'
                    )

            elif is_hr:
                # HR path — read-only through the UI; only reachable via
                # technical/admin operations. Pass through as-is.
                pass

            else:
                raise UserError(
                    'You do not have permission to edit this performance plan at this stage.'
                )

        return super().write(filtered_vals)


    def _filter_kra_commands(self, kra_commands, allowed_kpi_fields):
        # One2many command codes:
        #   0 = CREATE  (0, 0, vals)
        #   1 = UPDATE  (1, id, vals)
        #   2 = DELETE  (2, id, 0)
        #   3 = UNLINK  (3, id, 0)
        #   4 = LINK    (4, id, 0)
        #   5 = CLEAR   (5, 0, 0)
        #   6 = SET     (6, 0, [ids])
        filtered_kra_commands = []

        for cmd in kra_commands:
            cmd_code = cmd[0]

            if cmd_code == 1:
                # UPDATE existing KRA — inspect nested kpi_ids commands.
                kra_vals = dict(cmd[2]) if cmd[2] else {}

                if 'kpi_ids' in kra_vals:
                    filtered_kpi_commands = []
                    for kpi_cmd in kra_vals['kpi_ids']:
                        kpi_code = kpi_cmd[0]

                        if kpi_code == 1:
                            # UPDATE existing KPI — keep only the allowed fields.
                            raw_kpi_vals = kpi_cmd[2] or {}
                            safe_kpi_vals = {
                                k: v for k, v in raw_kpi_vals.items()
                                if k in allowed_kpi_fields
                            }
                            if safe_kpi_vals:
                                # Only emit the command if something survived the filter.
                                filtered_kpi_commands.append((1, kpi_cmd[1], safe_kpi_vals))

                        elif kpi_code in (0, 2, 3):
                            # CREATE / DELETE / UNLINK on a KPI row.
                            # Supervisors are never allowed structural changes.
                            if allowed_kpi_fields == {'supervisor_planning_remarks'}:
                                continue  # Drop silently for supervisor
                            filtered_kpi_commands.append(kpi_cmd)

                        else:
                            # LINK / CLEAR / SET — pass through as-is.
                            filtered_kpi_commands.append(kpi_cmd)

                    kra_vals['kpi_ids'] = filtered_kpi_commands

                filtered_kra_commands.append((1, cmd[1], kra_vals))

            elif cmd_code == 0:
                # CREATE a new KRA — only valid in template mode; pass through.
                filtered_kra_commands.append(cmd)

            else:
                # All other KRA-level commands — pass through.
                filtered_kra_commands.append(cmd)

        return filtered_kra_commands

    def action_submit_for_review(self):
        # employee submits their plan for supervisor review
        self.ensure_one()

        if self.state not in ['draft', 'rejected']:
            raise UserError('Only draft or rejected plans can be submitted.')

        if not self.can_employee_edit:
            raise UserError('Cannot submit: you do not own this plan, it is locked, or past deadline.')

        if self.selected_kpi_count == 0:
            raise UserError('Please select at least one KPI before submitting.')

        all_kpis = self.kra_ids.mapped('kpi_ids')
        selected_kpis = all_kpis.filtered(lambda k: k.is_selected)

        incomplete_kpis = selected_kpis.filtered(lambda k: not k.target) #(lambda k: not k.target or not k.planning_remarks) incase remarks is required
        if incomplete_kpis:
            raise UserError('All selected KPIs must have Target and Planning Remarks filled.')

        template_total = self.template_id.total_kpi_score
        employee_total = sum(selected_kpis.mapped('weightage'))
        if abs(employee_total - template_total) > 0.01:
            raise UserError(
                f'Total KPI score ({employee_total:.2f}) must equal '
                f'the template total ({template_total:.2f}). '
                f'Please adjust your KPI scores before submitting.'
            )

        self.with_context(skip_edit_check=True).write({
            'state': 'pending_supervisor',
            'submitted_date': fields.Datetime.now(),
        })

        if self.supervisor_id and self.supervisor_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.supervisor_id.user_id.id,
                summary=f'Review performance plan for {self.employee_id.name}',
                note=f'{self.employee_id.name} has submitted their performance plan for review.'
            )

        self.message_post(
            body=f"Performance plan submitted by {self.employee_id.name} for supervisor review.",
            message_type='notification'
        )
        return True

    def action_supervisor_approve(self):
        # Supervisor approves employee plan
        self.ensure_one()

        if self.state != 'pending_supervisor':
            raise UserError('Only plans pending supervisor review can be approved.')

        # Enforce: only the assigned supervisor (or HR) can approve
        current_user = self.env.user
        is_hr = current_user.has_group('hr_employee_evaluation.group_pms_hr_manager')
        if not is_hr and not self.is_supervisor_of_appraisal:
            raise UserError('Only the assigned supervisor can approve this plan.')

        selected_kpis = self.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)
        # missing_remarks = selected_kpis.filtered(lambda k: not k.supervisor_planning_remarks)
        # uncomment if supremarks are necessary
        # if missing_remarks:
        #     kpi_names = ', '.join(missing_remarks.mapped('name'))
        #     raise UserError(f'Supervisor remarks are required for all selected KPIs before approving. Missing remarks on: {kpi_names}')

        self.with_context(skip_edit_check=True).write({
            'state': 'approved',
            'supervisor_review_date': fields.Datetime.now(),
        })

        if self.employee_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.employee_id.user_id.id,
                summary='Your performance plan has been approved',
                note=f'Your supervisor {self.supervisor_id.name} has approved your performance plan.'
            )

        self.message_post(
            body=f"Planning approved by supervisor {self.supervisor_id.name}. Planning phase complete.",
            message_type='notification'
        )
        return True

    def action_supervisor_reject(self):
        # Supervisor rejects the planning
        self.ensure_one()

        if self.state != 'pending_supervisor':
            raise UserError('Only plans pending supervisor review can be rejected.')

        current_user = self.env.user
        is_hr = current_user.has_group('hr_employee_evaluation.group_pms_hr_manager')
        if not is_hr and not self.is_supervisor_of_appraisal:
            raise UserError('Only the assigned supervisor can reject this plan.')

        selected_kpis = self.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)
        # missing_remarks = selected_kpis.filtered(lambda k: not k.supervisor_planning_remarks)
        # uncommnent if you sup remarks is needed ask sir
        # if missing_remarks:
        #     kpi_names = ', '.join(missing_remarks.mapped('name'))
        #     raise UserError(f'Supervisor remarks are required for all selected KPIs before rejecting. Missing remarks on: {kpi_names}')

        self.with_context(skip_edit_check=True).write({
            'state': 'rejected',
            'rejection_date': fields.Datetime.now(),
        })

        if self.employee_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.employee_id.user_id.id,
                summary='Your performance plan needs revision',
                note=(
                    f'Your supervisor has rejected your plan. '
                    f'You have {self.cycle_id.resubmission_days} days to revise and resubmit. '
                    f'Check supervisor remarks for feedback.'
                )
            )

        self.message_post(
            body=(
                f"Planning rejected by supervisor {self.supervisor_id.name}. "
                f"Employee has {self.cycle_id.resubmission_days} days to resubmit."
            ),
            message_type='notification'
        )
        return True

    def _clone_template_structure(self):
        # Clone KRAs and KPIs from template
        self.ensure_one()

        if not self.template_id:
            raise UserError('Template is required to clone structure.')

        AppraisalKRAObj = self.env['pms.appraisal.kra']
        AppraisalKPIObj = self.env['pms.appraisal.kpi']

        for template_kra in self.template_id.kra_ids:
            appraisal_kra = AppraisalKRAObj.create({
                'appraisal_id': self.id,
                'name': template_kra.name,
                'sequence': template_kra.sequence,
                'template_kra_id': template_kra.id,
            })
            for template_kpi in template_kra.kpi_ids:
                AppraisalKPIObj.create({
                    'kra_id': appraisal_kra.id,
                    'name': template_kpi.name,
                    'description': template_kpi.description,
                    'criteria': template_kpi.criteria,
                    'weightage': template_kpi.score,
                    'template_kpi_id': template_kpi.id,
                    'is_selected': True,
                })

        return True