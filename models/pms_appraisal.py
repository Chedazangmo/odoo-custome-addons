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

    secondary_supervisor_id = fields.Many2one(
        'hr.employee',
        string='Secondary Supervisor',
        tracking=True,
        help='Second-level manager for review'
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
        ('pending_supervisor', '1st Review'),
        ('pending_secondary_supervisor', '2nd Review'),
        ('pending_reviewer', 'Final Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', required=True, tracking=True, copy=False)

    submitted_date = fields.Datetime(string='Submitted Date', readonly=True, tracking=True)
    supervisor_review_date = fields.Datetime(string='Supervisor Review Date', readonly=True, tracking=True)
    secondary_supervisor_review_date = fields.Datetime(string='Secondary Supervisor Review Date', readonly=True, tracking=True)
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

    is_secondary_supervisor_of_appraisal = fields.Boolean(
        string='Is Secondary Supervisor',
        compute='_compute_access_flags',
        help='True if the current user is the secondary supervisor of this appraisal'
    )

    is_reviewer_of_appraisal = fields.Boolean(
        string='Is Reviewer',
        compute='_compute_access_flags',
        help='True if the current user is the reviewer of this appraisal'
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

    can_secondary_supervisor_add_remarks = fields.Boolean(
        string='Can Secondary Supervisor Add Remarks',
        compute='_compute_access_flags',
        help='True only when: current user is the secondary supervisor, state is pending_secondary_supervisor, '
    )

    can_reviewer_add_remarks = fields.Boolean(
        string='Can Reviewer Add Remarks',
        compute='_compute_access_flags',
        help='True only when: current user is the reviewer, state is pending_reviewer' #currently reviewer cant edit
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
        'secondary_supervisor_id.user_id',
        'reviewer_id.user_id',
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
            sec_sup_user = record.secondary_supervisor_id.user_id
            rev_user = record.reviewer_id.user_id

            is_own = bool(emp_user and emp_user.id == current_user.id)
            is_sup = bool(sup_user and sup_user.id == current_user.id)
            is_sec_sup = bool(sec_sup_user and sec_sup_user.id == current_user.id)
            is_rev = bool(rev_user and rev_user.id == current_user.id)
            cycle_in_planning = record.cycle_id.state == 'planning'

            record.is_own_appraisal = is_own
            record.is_supervisor_of_appraisal = is_sup
            record.is_secondary_supervisor_of_appraisal = is_sec_sup
            record.is_reviewer_of_appraisal = is_rev

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

            record.can_secondary_supervisor_add_remarks = bool(
                is_sec_sup
                and record.state == 'pending_secondary_supervisor'
                and cycle_in_planning
            )

            record.can_reviewer_add_remarks = bool(
                is_rev
                and record.state == 'pending_reviewer'
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
            if 'employee_id' in vals:
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                # Auto-populate approval chain from hr.employee fields
                if 'supervisor_id' not in vals and employee.parent_id:
                    vals['supervisor_id'] = employee.parent_id.id
                if 'secondary_supervisor_id' not in vals and employee.secondary_manager_id:  
                    vals['secondary_supervisor_id'] = employee.secondary_manager_id.id
                if 'reviewer_id' not in vals and employee.reviewer_id:
                    vals['reviewer_id'] = employee.reviewer_id.id
        return super().create(vals_list)

    def write(self, vals):
        # The OWL widget always sends the full KPI row on save not just the
        # changed field. So we strip the payload per-role before it hits
        # the database

        # Roles:
        #   Employee (can_employee_edit=True):
        #       kra_ids → kpi_ids → is_selected, target, planning_remarks, weightage
        #   Supervisor (can_supervisor_add_remarks=True):
        #       kra_ids → kpi_ids → supervisor_planning_remarks  ← ONLY this field
        #   HR (skip_edit_check context):
        #       Unrestricted — used by action methods for state transitions.
        # Action methods bypass this guard via context flag.
        if self.env.context.get('skip_edit_check'):
            return super().write(vals)

        system_fields = {
            'state', 'submitted_date', 'supervisor_review_date',
            'secondary_supervisor_review_date','reviewer_approval_date', 'rejection_date', 'active',
        }

        user_facing_fields = set(vals.keys()) - system_fields

        # Nothing user-facing — let through 
        if not user_facing_fields:
            return super().write(vals)

        current_user = self.env.user
        is_hr = current_user.has_group('hr_employee_evaluation.group_pms_hr_manager')

        # Fields the employee is permitted to change on a KPI row.
        EMPLOYEE_KPI_FIELDS = {'is_selected', 'target', 'planning_remarks', 'weightage'}

        # Fields the supervisor is permitted to change on a KPI row.
        SUPERVISOR_KPI_FIELDS = {'target'} #{'supervisor_planning_remarks', 'target'}

        SECONDARY_SUPERVISOR_KPI_FIELDS = {'target'} 

        filtered_vals = dict(vals)

        for record in self:
            if record.can_employee_edit:
                # Employee path 
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
            
            elif record.can_secondary_supervisor_add_remarks:    
                if 'kra_ids' in filtered_vals:
                    filtered_vals['kra_ids'] = self._filter_kra_commands(
                        filtered_vals['kra_ids'],
                        allowed_kpi_fields=SECONDARY_SUPERVISOR_KPI_FIELDS,
                    )
                non_kra = user_facing_fields - {'kra_ids'}
                if non_kra:
                    raise UserError('You do not have permission to modify these fields on a performance plan.')

            elif record.can_reviewer_add_remarks:               
                # Reviewer only approves/rejects — they have no KPI fields to edit.
                raise UserError('Reviewers cannot edit KPI fields. Please use the Approve/Reject buttons.')

            elif is_hr:
                # HR path — read-only through the UI
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


    def _next_state_after_supervisor(self):
        """Return the correct next state after the primary supervisor approves."""
        self.ensure_one()
        if self.secondary_supervisor_id:
            return 'pending_secondary_supervisor'
        elif self.reviewer_id:
            return 'pending_reviewer'
        else:
            return 'approved'

    def _next_state_after_secondary(self):
        """Return the correct next state after the secondary supervisor approves."""
        self.ensure_one()
        if self.reviewer_id:
            return 'pending_reviewer'
        else:
            return 'approved'

    def _state_label(self, state_key):
        """Return the human-readable label for a state key."""
        return dict(self._fields['state'].selection).get(state_key, state_key)

    def _notify_next_approver(self, next_state):
        """Schedule an activity for whoever is next in the approval chain."""
        self.ensure_one()
        emp_name = self.employee_id.name

        if next_state == 'pending_secondary_supervisor' and self.secondary_supervisor_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.secondary_supervisor_id.user_id.id,
                summary=f'Review performance plan for {emp_name}',
                note=(
                    f"{emp_name}'s plan has been approved by the primary supervisor "
                    f"and now requires your review."
                ),
            )
        elif next_state == 'pending_reviewer' and self.reviewer_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.reviewer_id.user_id.id,
                summary=f'Final review: performance plan for {emp_name}',
                note=f"{emp_name}'s plan is ready for your final approval.",
            )
        elif next_state == 'approved' and self.employee_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.employee_id.user_id.id,
                summary='Your performance plan has been approved',
                note='Your performance plan has been fully approved.',
            )
    
    def _notify_employee_rejected(self, rejected_by):
        """Notify the employee their plan was rejected and needs revision."""
        self.ensure_one()
        if self.employee_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.employee_id.user_id.id,
                summary='Your performance plan needs revision',
                note=(
                    f'{rejected_by.name} has rejected your performance plan. '
                    f'You have {self.cycle_id.resubmission_days} days to revise and resubmit. '
                    f'Please check the remarks on each KPI for feedback.'
                ),
            )

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
        """Primary supervisor approves. Routes to secondary, reviewer, or approved."""
        self.ensure_one()

        if self.state != 'pending_supervisor':
            raise UserError('Only plans pending supervisor review can be approved here.')

        if not self.is_supervisor_of_appraisal:
            raise UserError('Only the assigned supervisor can approve this plan.')

        # Uncomment if supervisor remarks are required before approving:
        # selected_kpis = self.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)
        # missing = selected_kpis.filtered(lambda k: not k.supervisor_planning_remarks)
        # if missing:
        #     raise UserError(f'Supervisor remarks required on: {", ".join(missing.mapped("name"))}')

        next_state = self._next_state_after_supervisor()

        self.with_context(skip_edit_check=True).write({
            'state': next_state,
            'supervisor_review_date': fields.Datetime.now(),
        })

        self._notify_next_approver(next_state)

        self.message_post(
            body=(
                f"Plan approved by supervisor {self.supervisor_id.name}. "
                f"Status → {self._state_label(next_state)}."
            ),
            message_type='notification',
        )
        return True

    def action_supervisor_reject(self):
        """Primary supervisor rejects. Plan goes back to employee for revision."""
        self.ensure_one()

        if self.state != 'pending_supervisor':
            raise UserError('Only plans pending supervisor review can be rejected here.')

        if not self.is_supervisor_of_appraisal:
            raise UserError('Only the assigned supervisor can reject this plan.')

        # Uncomment if supervisor remarks are required before rejecting:
        # selected_kpis = self.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)
        # missing = selected_kpis.filtered(lambda k: not k.supervisor_planning_remarks)
        # if missing:
        #     raise UserError(f'Supervisor remarks required on: {", ".join(missing.mapped("name"))}')

        self.with_context(skip_edit_check=True).write({
            'state': 'rejected',
            'rejection_date': fields.Datetime.now(),
        })

        self._notify_employee_rejected(rejected_by=self.supervisor_id)
        self.message_post(
            body=(
                f"Plan rejected by supervisor {self.supervisor_id.name}. "
                f"Employee has {self.cycle_id.resubmission_days} days to resubmit."
            ),
            message_type='notification',
        )
        return True

    def action_secondary_supervisor_approve(self):
        """Secondary supervisor approves. Routes to reviewer or approved."""
        self.ensure_one()

        if self.state != 'pending_secondary_supervisor':
            raise UserError('Only plans pending secondary supervisor review can be approved here.')

        if not self.is_secondary_supervisor_of_appraisal:
            raise UserError('Only the assigned secondary supervisor can approve this plan.')

        next_state = self._next_state_after_secondary()

        self.with_context(skip_edit_check=True).write({
            'state': next_state,
            'secondary_supervisor_review_date': fields.Datetime.now(),
        })

        self._notify_next_approver(next_state)

        self.message_post(
            body=(
                f"Plan approved by secondary supervisor {self.secondary_supervisor_id.name}. "
                f"Status → {self._state_label(next_state)}."
            ),
            message_type='notification',
        )
        return True

    def action_secondary_supervisor_reject(self):
        """Secondary supervisor rejects. Plan goes back to employee — full chain restarts."""
        self.ensure_one()

        if self.state != 'pending_secondary_supervisor':
            raise UserError('Only plans pending secondary supervisor review can be rejected here.')

        if not self.is_secondary_supervisor_of_appraisal:
            raise UserError('Only the assigned secondary supervisor can reject this plan.')

        self.with_context(skip_edit_check=True).write({
            'state': 'rejected',
            'rejection_date': fields.Datetime.now(),
        })

        self._notify_employee_rejected(rejected_by=self.secondary_supervisor_id)
        self.message_post(
            body=(
                f"Plan rejected by secondary supervisor {self.secondary_supervisor_id.name}. "
                f"Employee has {self.cycle_id.resubmission_days} days to resubmit. "
                f"After resubmission the full approval chain restarts."
            ),
            message_type='notification',
        )
        return True

    def action_reviewer_approve(self):
        """Reviewer gives final approval. Plan is now approved."""
        self.ensure_one()

        if self.state != 'pending_reviewer':
            raise UserError('Only plans pending reviewer approval can be approved here.')

        if not self.is_reviewer_of_appraisal:
            raise UserError('Only the assigned reviewer can give final approval.')

        self.with_context(skip_edit_check=True).write({
            'state': 'approved',
            'reviewer_approval_date': fields.Datetime.now(),
        })

        self._notify_next_approver('approved')  # notifies the employee

        self.message_post(
            body=f"Plan fully approved by reviewer {self.reviewer_id.name}. Planning phase complete.",
            message_type='notification',
        )
        return True

    def action_reviewer_reject(self):
        """Reviewer rejects. Plan goes back to employee — full chain restarts."""
        self.ensure_one()

        if self.state != 'pending_reviewer':
            raise UserError('Only plans pending reviewer approval can be rejected here.')

        if not self.is_reviewer_of_appraisal:
            raise UserError('Only the assigned reviewer can reject this plan.')

        self.with_context(skip_edit_check=True).write({
            'state': 'rejected',
            'rejection_date': fields.Datetime.now(),
        })

        self._notify_employee_rejected(rejected_by=self.reviewer_id)
        self.message_post(
            body=(
                f"Plan rejected by reviewer {self.reviewer_id.name}. "
                f"Employee has {self.cycle_id.resubmission_days} days to resubmit. "
                f"After resubmission the full approval chain restarts."
            ),
            message_type='notification',
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