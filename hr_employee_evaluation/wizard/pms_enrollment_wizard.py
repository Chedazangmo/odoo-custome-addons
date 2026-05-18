from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class PMSEnrollmentWizard(models.TransientModel):
    _name = 'pms.enrollment.wizard'
    _description = 'Enroll Late Joining Employees into Active Cycle'

    cycle_id = fields.Many2one('pms.cycle', required=True, readonly=True)

    # Settings for REGULAR late joiners: their personal planning window from today
    planning_duration = fields.Integer(
        string='Planning Duration (Days)', default=15,
        help='Days from today the regular employee has to submit their plan.'
    )
    resubmission_days = fields.Integer(
        string='Resubmission Days', default=5,
        help='Grace period after HR resets a regular late joiner plan to draft.'
    )

    # Settings for PROBATION employees: applied AFTER probation completes
    # The probation cycle itself is auto-configured (10 days planning, 3 months, last 2 weeks appraisal)
    post_probation_planning_duration = fields.Integer(
        string='Post-Probation Planning Duration (Days)', default=15,
        help='Planning window given once the employee graduates from probation into the regular cycle.'
    )
    post_probation_resubmission_days = fields.Integer(
        string='Post-Probation Resubmission Days', default=5,
        help='Resubmission grace period once the employee graduates from probation.'
    )

    # Computed visibility helpers
    has_regular_pending = fields.Boolean(compute='_compute_pending_info')
    has_probation_pending = fields.Boolean(compute='_compute_pending_info')
    pending_summary = fields.Char(compute='_compute_pending_info')

    @api.depends('cycle_id')
    def _compute_pending_info(self):
        for wiz in self:
            pending = wiz.cycle_id.enrollment_ids.filtered(lambda e: e.state == 'pending')
            reg = sum(1 for e in pending if e.pms_type == 'regular')
            prob = sum(1 for e in pending if e.pms_type == 'probation')
            wiz.has_regular_pending = bool(reg)
            wiz.has_probation_pending = bool(prob)
            parts = []
            if reg:
                parts.append(f'{reg} regular')
            if prob:
                parts.append(f'{prob} on probation')
            wiz.pending_summary = ', '.join(parts) if parts else 'none'

    def action_confirm(self):
        self.ensure_one()
        cycle = self.cycle_id

        if cycle.state in ('appraisal', 'completed', 'cancelled'):
            raise UserError(
                f'Cannot enroll employees: the cycle is in {cycle.state} state. '
                'Enrollment is only allowed during Planning and Monitoring phases.'
            )

        pending = cycle.enrollment_ids.filtered(lambda e: e.state == 'pending')
        if not pending:
            raise UserError('No pending enrollments found to process.')

        errors = []
        for enrollment in pending:
            try:
                if enrollment.pms_type == 'regular':
                    self._enroll_regular(enrollment)
                else:
                    self._enroll_probation(enrollment)
            except UserError as e:
                errors.append(f'  - {enrollment.employee_id.name}: {e.args[0]}')

        if errors:
            raise UserError('Some enrollments could not be completed:\n\n' + '\n'.join(errors))

        return {'type': 'ir.actions.act_window_close'}

    def _validate_employee(self, employee):
        """Common validation. Returns the employee's active appraisal template."""
        if not employee.evaluation_group_id:
            raise UserError(f'{employee.name} has no Evaluation Group assigned.')
        if not employee.parent_id:
            raise UserError(f'{employee.name} has no Supervisor assigned.')
        if not employee.reviewer_id:
            raise UserError(f'{employee.name} has no Reviewer assigned.')
        template = self.env['appraisal.template'].search([
            ('evaluation_group_id', '=', employee.evaluation_group_id.id),
            ('active', '=', True),
        ], limit=1)
        if not template:
            raise UserError(
                f'No active template found for {employee.name} '
                f'(group: {employee.evaluation_group_id.name}).'
            )
        return template

    def _enroll_regular(self, enrollment):
        cycle = self.cycle_id
        employee = enrollment.employee_id

        existing = self.env['pms.appraisal'].search([
            ('cycle_id', '=', cycle.id),
            ('employee_id', '=', employee.id),
        ], limit=1)
        if existing:
            raise UserError(f'{employee.name} already has an appraisal in this cycle.')

        # Ensure not in another active regular cycle
        active_elsewhere = self.env['pms.appraisal'].search([
            ('employee_id', '=', employee.id),
            ('cycle_id', '!=', cycle.id),
            ('pms_type', '=', 'regular'),
            ('cycle_id.state', 'not in', ['completed', 'cancelled', 'draft']),
        ], limit=1)
        if active_elsewhere:
            raise UserError(
                f'{employee.name} is already enrolled in another active cycle '
                f'({active_elsewhere.cycle_id.name}).'
            )

        template = self._validate_employee(employee)
        today = fields.Date.today()
        personal_deadline = today + timedelta(days=self.planning_duration)

        appraisal = self.env['pms.appraisal'].create({
            'cycle_id': cycle.id,
            'employee_id': employee.id,
            'template_id': template.id,
            'supervisor_id': employee.parent_id.id if employee.parent_id else False,
            'secondary_supervisor_id': employee.secondary_manager_id.id if employee.secondary_manager_id else False,
            'reviewer_id': employee.reviewer_id.id if employee.reviewer_id else False,
            'pms_type': 'regular',
            'personal_planning_deadline': personal_deadline,
            'personal_resubmission_days': self.resubmission_days,
        })
        appraisal._clone_template_structure()

        # Fix Gemini bug 2: add late joiner to employee_ids so they appear in all employee lists
        cycle.with_context(skip_cycle_write_check=True).write({
            'employee_ids': [(4, employee.id)],
        })

        enrollment.write({
            'state': 'enrolled',
            'enrollment_date': today,
            'appraisal_id': appraisal.id,
        })

        if employee.user_id:
            appraisal.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=employee.user_id.id,
                summary=f'Performance Plan Ready — {cycle.name}',
                note=(
                    f'You have been enrolled in {cycle.name}. '
                    f'Your planning deadline is {personal_deadline.strftime("%B %d, %Y")}.'
                ),
            )

    def _enroll_probation(self, enrollment):
        cycle = self.cycle_id
        employee = enrollment.employee_id

        template = self._validate_employee(employee)
        today = fields.Date.today()

        # Probation sub-cycle: 3 months total, 10 days planning
        probation_end = today + relativedelta(months=3, days=-1)
        prob_sequence = self.env['ir.sequence'].next_by_code('pms.cycle') or 'New'
        year = str(today.year)

        prob_cycle = self.env['pms.cycle'].with_context(skip_cycle_write_check=True).create({
            'name': f'Probation — {employee.name} — {year}',
            'sequence': prob_sequence,
            'cycle_type': 'probation',
            'start_date': today,
            'end_date': probation_end,
            'planning_duration': 10,
            'resubmission_days': cycle.resubmission_days,
            'apply_to': 'selected',
            'parent_cycle_id': cycle.id,
            'final_score_selection': cycle.final_score_selection,
            'state': 'planning',
        })
        prob_cycle.with_context(skip_cycle_write_check=True).write({
            'employee_ids': [(4, employee.id)],
        })

        appraisal = self.env['pms.appraisal'].create({
            'cycle_id': prob_cycle.id,
            'employee_id': employee.id,
            'template_id': template.id,
            'supervisor_id': employee.parent_id.id if employee.parent_id else False,
            'secondary_supervisor_id': employee.secondary_manager_id.id if employee.secondary_manager_id else False,
            'reviewer_id': employee.reviewer_id.id if employee.reviewer_id else False,
            'pms_type': 'probation',
        })
        appraisal._clone_template_structure()

        # Fix Gemini bug 2: add to parent cycle employee_ids too
        cycle.with_context(skip_cycle_write_check=True).write({
            'employee_ids': [(4, employee.id)],
        })

        personal_deadline = today + timedelta(days=10)

        enrollment.write({
            'state': 'enrolled',
            'enrollment_date': today,
            'appraisal_id': appraisal.id,
            'probation_cycle_id': prob_cycle.id,
            # Fix Gemini bug 1: explicitly save post-probation settings on the enrollment record
            'post_probation_planning_duration': self.post_probation_planning_duration,
            'post_probation_resubmission_days': self.post_probation_resubmission_days,
        })

        if employee.user_id:
            appraisal.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=employee.user_id.id,
                summary='Probation Performance Plan Ready',
                note=(
                    f'Your probation performance plan is now active. '
                    f'Planning deadline: {personal_deadline.strftime("%B %d, %Y")}. '
                    f'Probation period ends: {probation_end.strftime("%B %d, %Y")}.'
                ),
            )