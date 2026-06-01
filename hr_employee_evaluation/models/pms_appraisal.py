from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import io
import base64
import xlsxwriter

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

    cycle_state = fields.Selection(
        related='cycle_id.state',
        string='Cycle State',
        store=False,
        readonly=True
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

    competency_score_ids = fields.One2many(
        'appraisal.competency.score',
        'appraisal_id',
        string='Competency Scores'
    )

    state = fields.Selection([
        # Planning states
        ('draft', 'Draft'),
        ('pending_supervisor', '1st Review'),
        ('pending_secondary_supervisor', '2nd Review'),
        ('pending_reviewer', 'Final Review'),
        ('approved', 'Approved'),

        # Appraisal states
        ('appraisal_draft', 'Draft'),
        ('appraisal_pending_supervisor', '1st Appraisal'),
        ('appraisal_pending_secondary_supervisor', '2nd Appraisal'),
        ('appraisal_pending_reviewer', 'Final Appraisal'),
        ('appraisal_approved', 'Completed'),
    ], string='Status', default='draft', required=True, tracking=True, copy=False)

    submitted_date = fields.Datetime(string='Submitted Date', readonly=True, tracking=True)
    supervisor_review_date = fields.Datetime(string='Supervisor Review Date', readonly=True, tracking=True)
    secondary_supervisor_review_date = fields.Datetime(string='Secondary Supervisor Review Date', readonly=True, tracking=True)
    reviewer_approval_date = fields.Datetime(string='Reviewer Approval Date', readonly=True, tracking=True)

    draft_reset_date = fields.Datetime(
        string='Draft Reset Date',
        readonly=True,
        tracking=True,
        help='Set by HR when the plan is reset to draft'
    )

    resubmission_deadline = fields.Datetime(
        string='Resubmission Deadline',
        readonly=True,
        compute='_compute_resubmission_deadline',
        store=True,
        help='Deadline for resubmission after plan is set to draft'
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
    )
    can_supervisor_edit_target = fields.Boolean(
        string='Can Supervisor Add Remarks',
        compute='_compute_access_flags',
    )
    can_secondary_supervisor_edit_target = fields.Boolean(
        string='Can Secondary Supervisor Add Remarks',
        compute='_compute_access_flags',
    )
    is_editable = fields.Boolean(
        string='Is Editable',
        compute='_compute_access_flags',
    )
    is_past_planning_deadline = fields.Boolean(
        string='Past Planning Deadline',
        compute='_compute_is_past_planning_deadline'
    )
    self_planning_deadline = fields.Date(
        string='Self-Planning Deadline',
        compute='_compute_self_planning_deadline',
        store=True,
        help='Deadline for the employee to complete self-planning (5 days before the actual deadline).'
    )

    # Appraisal phase access flags
    can_employee_self_rate = fields.Boolean(
        string='Can Employee Self Rate',
        compute='_compute_access_flags',
        help='True when cycle is at appraisal and it is the employee turn'
    )
    can_supervisor_rate = fields.Boolean(
        string='Can Supervisor Rate',
        compute='_compute_access_flags',
    )
    can_secondary_supervisor_rate = fields.Boolean(
        string='Can Secondary Supervisor Rate',
        compute='_compute_access_flags',
    )
    can_reviewer_rate = fields.Boolean(
        string='Can Reviewer Rate',
        compute='_compute_access_flags',
    )

    planning_total_score = fields.Float(
        string='Planning Total Score',
        compute='_compute_planning_total_score',
        store=True,
        help='Sum of weightages of all selected KPIs during the planning phase'
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
        string='Planning Start', store=True, readonly=True
    )
    planning_end_date = fields.Date(
        string='Planning Deadline', store=True, readonly=True
    )

    template_total_score = fields.Float(
        related='template_id.total_kpi_score',
        string='Template Total Score', store=False, readonly=True,
        help='Original template total for validation'
    )

    allocated_total_score = fields.Float(
        string='Allocated Total Score',
        compute='_compute_allocated_total_score',
        help='Template KPI total + Competency total (e.g., 84 + 16 = 100)'
    )

    current_total_score = fields.Float(
        string='Current Total Score',
        compute='_compute_current_total_score',
        help='Sum of actual scores (KPI + Competency) for current rater'
    )

    appraisal_reset_date = fields.Datetime(
        string='Appraisal Reset Date',
        readonly=True,
        tracking=True,
        help='Stamped when HR resets the appraisal back to draft'
    )
    appraisal_start_date_display = fields.Date(
        related='cycle_id.appraisal_start_date',
        string='Appraisal Start Date', store=False, readonly=True
    )
    # Full cycle end date — kept for display / HR reference
    appraisal_end_date_display = fields.Date(
        related='cycle_id.end_date',
        string='Cycle End Date', store=False, readonly=True
    )
    # Employee-facing deadline: 10 days before the cycle ends
    appraisal_end_date = fields.Date(
        string='Appraisal Employee Deadline',
        compute='_compute_appraisal_end_date',
        store=True,
        help='Last day an employee may submit self-ratings (cycle end − 10 days).'
    )

    self_has_zero_scores = fields.Boolean(
        string='Self Score Has Zeros',
        compute='_compute_self_has_zero_scores',
        help='True if any selected KPI has a self_score of 0'
    )
    supervisor_has_zero_scores = fields.Boolean(
        string='Supervisor Score Has Zeros',
        compute='_compute_self_has_zero_scores',
    )
    secondary_supervisor_has_zero_scores = fields.Boolean(
        string='Secondary Supervisor Score Has Zeros',
        compute='_compute_self_has_zero_scores',
    )
    reviewer_has_zero_scores = fields.Boolean(
        string='Reviewer Score Has Zeros',
        compute='_compute_self_has_zero_scores',
    )

    total_self_score = fields.Float(
        string='Total Self Score (KRA)',
        compute='_compute_total_scores',
        store=True
    )
    total_supervisor_score = fields.Float(
        string='Total Supervisor Score (KRA)',
        compute='_compute_total_scores',
        store=True
    )
    total_secondary_score = fields.Float(
        string='Total Secondary Score (KRA)',
        compute='_compute_total_scores',
        store=True
    )
    total_reviewer_score = fields.Float(
        string='Total Reviewer Score (KRA)',
        compute='_compute_total_scores',
        store=True
    )

    competency_max_total = fields.Float(
        string='Competency Max Points',
        compute='_compute_competency_totals',
        store=True,
    )
    competency_self_total = fields.Float(
        string='Competency Emp Total',
        compute='_compute_competency_totals',
        store=True,
    )
    competency_supervisor_total = fields.Float(
        string='Competency Supervisor Total',
        compute='_compute_competency_totals',
        store=True,
    )
    competency_secondary_total = fields.Float(
        string='Competency 2nd Supervisor Total',
        compute='_compute_competency_totals',
        store=True,
    )
    competency_reviewer_total = fields.Float(
        string='Competency Reviewer Total',
        compute='_compute_competency_totals',
        store=True,
    )

    grand_total_self_score = fields.Float(
        string='Grand Total Self Score',
        compute='_compute_grand_totals',
        store=True,
        help='KRA self score + competency self score'
    )
    grand_total_supervisor_score = fields.Float(
        string='Grand Total Supervisor Score',
        compute='_compute_grand_totals',
        store=True,
    )
    grand_total_secondary_score = fields.Float(
        string='Grand Total Secondary Score',
        compute='_compute_grand_totals',
        store=True,
    )
    grand_total_reviewer_score = fields.Float(
        string='Grand Total Reviewer Score',
        compute='_compute_grand_totals',
        store=True,
    )

    final_appraisal_score = fields.Float(
        string='Final Appraisal Score',
        compute='_compute_final_appraisal_score',
        store=True,
        help='Final score combining KRA and competency scores'
    )

    # Competency Framework HTML field for planning phase display
    competency_framework_html = fields.Html(
        string='Competency Framework',
        compute='_compute_competency_framework_html',
        store=False,
        readonly=True,
        sanitize=False,
    )

    # ─────────────────────────────────────────────────────────────
    # Compute methods
    # ─────────────────────────────────────────────────────────────

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

    @api.depends('template_id.total_kpi_score', 'competency_max_total')
    def _compute_allocated_total_score(self):
        for record in self:
            template_kpi_total = record.template_id.total_kpi_score or 0.0
            competency_max = record.competency_max_total or 0.0
            record.allocated_total_score = template_kpi_total + competency_max

    @api.depends(
        'kra_ids.kpi_ids.self_score',
        'kra_ids.kpi_ids.supervisor_score',
        'kra_ids.kpi_ids.secondary_supervisor_score',
        'kra_ids.kpi_ids.reviewer_score',
        'kra_ids.kpi_ids.is_selected',
        'competency_score_ids.self_score',
        'competency_score_ids.supervisor_score',
        'competency_score_ids.secondary_supervisor_score',
        'competency_score_ids.reviewer_score',
        'state',
    )
    def _compute_current_total_score(self):
        for record in self:
            if record.state == 'appraisal_draft':
                score_type = 'self'
            elif record.state == 'appraisal_pending_supervisor':
                score_type = 'supervisor'
            elif record.state == 'appraisal_pending_secondary_supervisor':
                score_type = 'secondary_supervisor'
            elif record.state == 'appraisal_pending_reviewer':
                score_type = 'reviewer'
            else:
                score_type = 'self'

            selected_kpis = record.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)
            if score_type == 'self':
                kpi_total = sum(selected_kpis.mapped('self_score'))
            elif score_type == 'supervisor':
                kpi_total = sum(selected_kpis.mapped('supervisor_score'))
            elif score_type == 'secondary_supervisor':
                kpi_total = sum(selected_kpis.mapped('secondary_supervisor_score'))
            elif score_type == 'reviewer':
                kpi_total = sum(selected_kpis.mapped('reviewer_score'))
            else:
                kpi_total = sum(selected_kpis.mapped('self_score'))

            if score_type == 'self':
                competency_total = sum(record.competency_score_ids.mapped('self_score'))
            elif score_type == 'supervisor':
                competency_total = sum(record.competency_score_ids.mapped('supervisor_score'))
            elif score_type == 'secondary_supervisor':
                competency_total = sum(record.competency_score_ids.mapped('secondary_supervisor_score'))
            elif score_type == 'reviewer':
                competency_total = sum(record.competency_score_ids.mapped('reviewer_score'))
            else:
                competency_total = sum(record.competency_score_ids.mapped('self_score'))

            record.current_total_score = kpi_total + competency_total

    @api.depends(
        'kra_ids.kpi_ids.self_score',
        'kra_ids.kpi_ids.supervisor_score',
        'kra_ids.kpi_ids.secondary_supervisor_score',
        'kra_ids.kpi_ids.reviewer_score',
        'kra_ids.kpi_ids.is_selected',
    )
    def _compute_total_scores(self):
        for record in self:
            selected_kpis = record.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)
            record.total_self_score       = sum(selected_kpis.mapped('self_score'))
            record.total_supervisor_score = sum(selected_kpis.mapped('supervisor_score'))
            record.total_secondary_score  = sum(selected_kpis.mapped('secondary_supervisor_score'))
            record.total_reviewer_score   = sum(selected_kpis.mapped('reviewer_score'))

    @api.depends(
        'competency_score_ids.line_points',
        'competency_score_ids.self_score',
        'competency_score_ids.supervisor_score',
        'competency_score_ids.secondary_supervisor_score',
        'competency_score_ids.reviewer_score',
    )
    def _compute_competency_totals(self):
        for record in self:
            rows = record.competency_score_ids
            record.competency_max_total        = sum(rows.mapped('line_points'))
            record.competency_self_total       = sum(rows.mapped('self_score'))
            record.competency_supervisor_total = sum(rows.mapped('supervisor_score'))
            record.competency_secondary_total  = sum(rows.mapped('secondary_supervisor_score'))
            record.competency_reviewer_total   = sum(rows.mapped('reviewer_score'))

    @api.depends(
        'total_self_score', 'total_supervisor_score',
        'total_secondary_score', 'total_reviewer_score',
        'competency_self_total', 'competency_supervisor_total',
        'competency_secondary_total', 'competency_reviewer_total',
    )
    def _compute_grand_totals(self):
        for record in self:
            record.grand_total_self_score       = record.total_self_score       + record.competency_self_total
            record.grand_total_supervisor_score = record.total_supervisor_score + record.competency_supervisor_total
            record.grand_total_secondary_score  = record.total_secondary_score  + record.competency_secondary_total
            record.grand_total_reviewer_score   = record.total_reviewer_score   + record.competency_reviewer_total

    @api.depends(
        'grand_total_reviewer_score',
        'grand_total_supervisor_score',
        'grand_total_secondary_score',
        'cycle_id.final_score_selection',
    )
    def _compute_final_appraisal_score(self):
        for appraisal in self:
            if appraisal.cycle_id.final_score_selection == 'reviewer':
                appraisal.final_appraisal_score = appraisal.grand_total_reviewer_score
            elif appraisal.cycle_id.final_score_selection == 'average':
                scores = []
                if appraisal.grand_total_supervisor_score:
                    scores.append(appraisal.grand_total_supervisor_score)
                if appraisal.grand_total_secondary_score:
                    scores.append(appraisal.grand_total_secondary_score)
                if appraisal.grand_total_reviewer_score:
                    scores.append(appraisal.grand_total_reviewer_score)
                appraisal.final_appraisal_score = sum(scores) / len(scores) if scores else 0.0
            else:
                appraisal.final_appraisal_score = 0.0

    @api.depends(
        'kra_ids.kpi_ids.self_score',
        'kra_ids.kpi_ids.supervisor_score',
        'kra_ids.kpi_ids.secondary_supervisor_score',
        'kra_ids.kpi_ids.reviewer_score',
        'kra_ids.kpi_ids.is_selected',
    )
    def _compute_self_has_zero_scores(self):
        for record in self:
            selected = record.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)
            record.self_has_zero_scores                    = any(k.self_score == 0.0 for k in selected)
            record.supervisor_has_zero_scores              = any(k.supervisor_score == 0.0 for k in selected)
            record.secondary_supervisor_has_zero_scores    = any(k.secondary_supervisor_score == 0.0 for k in selected)
            record.reviewer_has_zero_scores                = any(k.reviewer_score == 0.0 for k in selected)

    @api.depends(
        'state',
        'employee_id.user_id',
        'supervisor_id.user_id',
        'secondary_supervisor_id.user_id',
        'reviewer_id.user_id',
        'cycle_id.state',
        'planning_end_date',
        'self_planning_deadline',
        'appraisal_end_date',
        'draft_reset_date',
        'resubmission_deadline',
    )
    def _compute_access_flags(self):
        current_user = self.env.user
        today = fields.Date.today()
        now = fields.Datetime.now()

        for record in self:
            emp_user     = record.employee_id.user_id
            sup_user     = record.supervisor_id.user_id
            sec_sup_user = record.secondary_supervisor_id.user_id
            rev_user     = record.reviewer_id.user_id

            is_own      = bool(emp_user     and emp_user.id     == current_user.id)
            is_sup      = bool(sup_user     and sup_user.id     == current_user.id)
            is_sec_sup  = bool(sec_sup_user and sec_sup_user.id == current_user.id)
            is_rev      = bool(rev_user     and rev_user.id     == current_user.id)

            cycle_in_appraisal = record.cycle_id.state == 'appraisal'

            # Ensure individual has started and cycle allows planning
            has_started = bool(record.planning_start_date and record.planning_start_date <= today)
            cycle_allows_planning = record.cycle_id.state in ('planning', 'monitoring')

            record.is_own_appraisal                        = is_own
            record.is_supervisor_of_appraisal              = is_sup
            record.is_secondary_supervisor_of_appraisal    = is_sec_sup
            record.is_reviewer_of_appraisal                = is_rev

            # ── Planning edit window ──────────────────────────────────────
            if not is_own or not cycle_allows_planning or not has_started:
                record.can_employee_edit = False
            elif record.state == 'approved':
                record.can_employee_edit = False
            elif record.self_planning_deadline and record.self_planning_deadline < today:
                if record.state == 'draft' and record.draft_reset_date and record.resubmission_deadline:
                    record.can_employee_edit = now <= record.resubmission_deadline
                else:
                    record.can_employee_edit = False
            elif record.state == 'draft':
                record.can_employee_edit = True
            else:
                record.can_employee_edit = False

            record.can_supervisor_edit_target = bool(
                is_sup
                and record.state == 'pending_supervisor'
                and cycle_allows_planning
            )
            record.can_secondary_supervisor_edit_target = bool(
                is_sec_sup
                and record.state == 'pending_secondary_supervisor'
                and cycle_allows_planning
            )

            record.is_editable = record.can_employee_edit

            record.can_employee_self_rate = bool(
                is_own
                and record.state == 'appraisal_draft'
                and cycle_in_appraisal
                and (not record.appraisal_end_date or today <= record.appraisal_end_date)
            )
            record.can_supervisor_rate = bool(
                is_sup and record.state == 'appraisal_pending_supervisor' and cycle_in_appraisal
            )
            record.can_secondary_supervisor_rate = bool(
                is_sec_sup and record.state == 'appraisal_pending_secondary_supervisor' and cycle_in_appraisal
            )
            record.can_reviewer_rate = bool(
                is_rev and record.state == 'appraisal_pending_reviewer' and cycle_in_appraisal
            )

    @api.depends('planning_end_date')
    def _compute_is_past_planning_deadline(self):
        today = fields.Date.today()
        for record in self:
            record.is_past_planning_deadline = bool(
                record.planning_end_date
                and record.planning_end_date < today
            )

    @api.depends('draft_reset_date', 'cycle_id.resubmission_days', 'self_planning_deadline')
    def _compute_resubmission_deadline(self):
        for record in self:
            if record.draft_reset_date and record.cycle_id.resubmission_days:
                reset_plus_days = record.draft_reset_date + timedelta(
                    days=record.cycle_id.resubmission_days
                )
                if record.self_planning_deadline:
                    planning_dt = fields.Datetime.from_string(
                        str(record.self_planning_deadline)
                    )
                    record.resubmission_deadline = max(planning_dt, reset_plus_days)
                else:
                    record.resubmission_deadline = reset_plus_days
            else:
                record.resubmission_deadline = False

    @api.depends('planning_end_date')
    def _compute_self_planning_deadline(self):
        for record in self:
            if record.planning_end_date:
                record.self_planning_deadline = record.planning_end_date - timedelta(days=5)
            else:
                record.self_planning_deadline = False

    @api.depends('cycle_id.end_date')
    def _compute_appraisal_end_date(self):
        """Employee self-rating closes 10 days before the cycle end date."""
        for record in self:
            if record.cycle_id.end_date:
                record.appraisal_end_date = record.cycle_id.end_date - timedelta(days=10)
            else:
                record.appraisal_end_date = False

    @api.depends('kra_ids.kpi_ids.is_selected', 'kra_ids.kpi_ids.weightage')
    def _compute_planning_total_score(self):
        for record in self:
            selected_kpis = record.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)
            record.planning_total_score = sum(selected_kpis.mapped('weightage'))

    def _compute_competency_framework_html(self):
        """Compute HTML representation of competency framework for display in planning phase"""
        S = {
            'table':       'width:100%;border-collapse:collapse;font-size:0.88em;font-family:inherit;margin-top:10px;',
            'th':          ('background-color:#1a3c5e;color:#ffffff;font-size:0.75em;font-weight:700;'
                            'text-transform:uppercase;letter-spacing:0.06em;padding:10px 10px;'
                            'border-bottom:3px solid #e8a020;white-space:nowrap;text-align:left;'),
            'th_code':     'width:70px;text-align:center;',
            'th_pts':      'width:90px;text-align:right;',
            'th_targets':  'width:44%;',
            'grp_base':    ('font-weight:700;padding:10px 14px;border-top:3px solid #e8a020;'
                            'border-bottom:1px solid rgba(255,255,255,0.15);'),
            'grp_exact':   'background-color:#1a3c5e;color:#ffffff;',
            'grp_under':   'background-color:#134e6f;color:#fef3c7;',
            'grp_over':    'background-color:#7f1d1d;color:#fee2e2;',
            'grp_code':    ('font-family:monospace;font-size:0.82em;font-weight:700;'
                            'background-color:rgba(255,255,255,0.18);border-radius:3px;'
                            'padding:2px 8px;margin-right:10px;letter-spacing:0.04em;'),
            'grp_pts_lbl': ('font-size:0.78em;font-weight:600;text-transform:uppercase;'
                            'letter-spacing:0.05em;opacity:0.75;margin-right:4px;'),
            'grp_pts_val': 'font-size:1em;font-weight:700;',
            'grp_right':   'text-align:right;white-space:nowrap;',
            'even':        ('background-color:#ffffff;padding:8px 10px;'
                            'border-bottom:1px solid #e2e8f0;vertical-align:top;color:#1e293b;'),
            'odd':         ('background-color:#f8faff;padding:8px 10px;'
                            'border-bottom:1px solid #e2e8f0;vertical-align:top;color:#1e293b;'),
            'code_pill':   ('font-family:monospace;font-size:0.82em;font-weight:700;'
                            'color:#1d4ed8;background-color:#eff6ff;border:1px solid #93c5fd;'
                            'border-radius:4px;padding:2px 7px;display:inline-block;'),
            'td_code':     'text-align:center;width:70px;',
            'td_targets':  ('color:#334155;font-size:0.875em;word-break:break-word;'
                            'line-height:1.65;padding-top:6px;padding-bottom:6px;'),
            'td_pts':      'text-align:right;font-weight:600;white-space:nowrap;',
            'foot':        ('background-color:#dbeafe;border-top:2px solid #1a3c5e;'
                            'padding:8px 10px;font-weight:700;color:#0f172a;font-size:0.88em;'),
            'foot_pts':    'text-align:right;font-weight:700;',
        }

        for appraisal in self:
            comp_tmpl = appraisal._get_competency_template()
            
            if not comp_tmpl or not comp_tmpl.group_ids:
                appraisal.competency_framework_html = (
                    '<p style="color:#94a3b8;font-size:0.9em;padding:16px;">'
                    'No competency framework defined for this template.</p>'
                )
                continue

            rows = [
                '<table style="{table}"><thead><tr>'
                '<th style="{th}{th_code}">Sl. No</th>'
                '<th style="{th}">Competency</th>'
                '<th style="{th}{th_targets}">Targets</th>'
                '<th style="{th}{th_pts}">Points</th>'
                '<tr></thead><tbody>'.format(**S)
            ]

            total_pts = 0.0

            for group in comp_tmpl.group_ids.sorted(key=lambda g: (g.sequence, g.id)):
                status = group.points_status or 'under'
                grp_style = S['grp_base'] + S['grp_{}'.format(status)]
                grp_name = (group.name or '').replace('<', '&lt;').replace('>', '&gt;')
                grp_code = (group.hr_code or '').replace('<', '&lt;').replace('>', '&gt;')

                rows.append(
                    '<tr>'
                    '<td colspan="3" style="{gs}">'
                    '<span style="{gc}">{code}</span>{name}'
                    '</td>'
                    '<td style="{gs}{gr}">'
                    '<span style="{gl}">Total Points</span>'
                    '<span style="{gv}">{pts:.2f}</span>'
                    '</td>'
                    '</tr>'.format(
                        gs=grp_style, gc=S['grp_code'], gr=S['grp_right'],
                        gl=S['grp_pts_lbl'], gv=S['grp_pts_val'],
                        code=grp_code, name=grp_name, pts=group.points,
                    )
                )

                for i, line in enumerate(group.line_ids.sorted(key=lambda l: (l.sequence, l.id))):
                    td = S['even'] if i % 2 == 0 else S['odd']
                    targets = (line.description or '').replace('<', '&lt;').replace('>', '&gt;')
                    lname = (line.name or '').replace('<', '&lt;').replace('>', '&gt;')
                    code = (line.full_code or '').replace('<', '&lt;').replace('>', '&gt;')

                    rows.append(
                        '<tr>'
                        '<td style="{td}{tc}"><span style="{cp}">{code}</span></td>'
                        '<td style="{td}">{name}</td>'
                        '<td style="{td}{tt}">{targets}</td>'
                        '<td style="{td}{tp}">{pts:.2f}</td>'
                        '</tr>'.format(
                            td=td, tc=S['td_code'], cp=S['code_pill'],
                            tt=S['td_targets'], tp=S['td_pts'],
                            code=code, name=lname, targets=targets, pts=line.points,
                        )
                    )
                    total_pts += line.points

            rows.append(
                '<tr>'
                '<td colspan="3" style="{f}">Total Framework Points</td>'
                '<td style="{f}{fp}">{total:.2f}</td>'
                '</tr></tbody>~<tr>'.format(
                    f=S['foot'], fp=S['foot_pts'], total=total_pts,
                )
            )
            appraisal.competency_framework_html = ''.join(rows)

    # ─────────────────────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────────────────────

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

    # ─────────────────────────────────────────────────────────────
    # ORM overrides
    # ─────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'employee_id' in vals:
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                if 'supervisor_id' not in vals and employee.parent_id:
                    vals['supervisor_id'] = employee.parent_id.id
                if 'secondary_supervisor_id' not in vals and employee.secondary_manager_id:
                    vals['secondary_supervisor_id'] = employee.secondary_manager_id.id
                if 'reviewer_id' not in vals and employee.reviewer_id:
                    vals['reviewer_id'] = employee.reviewer_id.id
        records = super().create(vals_list)
        records._sync_competency_scores()
        return records

    def write(self, vals):
        if self.env.context.get('skip_edit_check'):
            return super().write(vals)

        system_fields = {
            'state', 'submitted_date', 'supervisor_review_date',
            'secondary_supervisor_review_date', 'reviewer_approval_date',
            'active', 'draft_reset_date', 'appraisal_reset_date',
            'competency_score_ids',
        }

        user_facing_fields = set(vals.keys()) - system_fields

        if not user_facing_fields and 'competency_score_ids' not in vals:
            return super().write(vals)

        current_user = self.env.user
        is_hr = current_user.has_group('hr_employee_evaluation.group_pms_hr_manager')

        EMPLOYEE_KPI_FIELDS             = {'is_selected', 'target', 'planning_remarks', 'weightage', 'criteria'}
        SUPERVISOR_KPI_FIELDS           = {'target', 'criteria'}
        SECONDARY_SUPERVISOR_KPI_FIELDS = {'target', 'criteria'}

        EMPLOYEE_SCORING_FIELDS   = {'self_score', 'self_remarks'}
        SUPERVISOR_SCORING_FIELDS = {'supervisor_score', 'supervisor_remarks'}
        SECONDARY_SCORING_FIELDS  = {'secondary_supervisor_score', 'secondary_supervisor_score_remarks'}
        REVIEWER_SCORING_FIELDS   = {'reviewer_score', 'reviewer_remarks'}

        filtered_vals = dict(vals)

        for record in self:
            if record.can_employee_edit:
                if 'kra_ids' in filtered_vals:
                    filtered_vals['kra_ids'] = record._filter_kra_commands(
                        filtered_vals['kra_ids'],
                        allowed_kpi_fields=EMPLOYEE_KPI_FIELDS,
                    )
                filtered_vals.pop('competency_score_ids', None)
                non_kra = user_facing_fields - {'kra_ids'}
                if non_kra and not is_hr:
                    raise UserError(
                        'You do not have permission to modify these fields on a performance plan.'
                    )
            elif record.can_supervisor_edit_target:
                if 'kra_ids' in filtered_vals:
                    filtered_vals['kra_ids'] = record._filter_kra_commands(
                        filtered_vals['kra_ids'],
                        allowed_kpi_fields=SUPERVISOR_KPI_FIELDS,
                    )
                filtered_vals.pop('competency_score_ids', None)
                non_kra = user_facing_fields - {'kra_ids'}
                if non_kra:
                    raise UserError(
                        'You do not have permission to modify these fields on a performance plan.'
                    )
            elif record.can_secondary_supervisor_edit_target:
                if 'kra_ids' in filtered_vals:
                    filtered_vals['kra_ids'] = record._filter_kra_commands(
                        filtered_vals['kra_ids'],
                        allowed_kpi_fields=SECONDARY_SUPERVISOR_KPI_FIELDS,
                    )
                filtered_vals.pop('competency_score_ids', None)
                non_kra = user_facing_fields - {'kra_ids'}
                if non_kra:
                    raise UserError(
                        'You do not have permission to modify these fields on a performance plan.'
                    )
            elif record.can_employee_self_rate:
                if 'kra_ids' in filtered_vals:
                    filtered_vals['kra_ids'] = record._filter_kra_commands(
                        filtered_vals['kra_ids'],
                        allowed_kpi_fields=EMPLOYEE_SCORING_FIELDS,
                    )
                if 'competency_score_ids' in filtered_vals:
                    filtered_vals['competency_score_ids'] = record._filter_competency_score_commands(
                        filtered_vals['competency_score_ids'],
                        allowed_fields=EMPLOYEE_SCORING_FIELDS,
                    )
                non_kra = user_facing_fields - {'kra_ids'}
                if non_kra and not is_hr:
                    raise UserError('You can only edit your self-scores and remarks right now.')
            elif record.can_supervisor_rate:
                if 'kra_ids' in filtered_vals:
                    filtered_vals['kra_ids'] = record._filter_kra_commands(
                        filtered_vals['kra_ids'],
                        allowed_kpi_fields=SUPERVISOR_SCORING_FIELDS,
                    )
                if 'competency_score_ids' in filtered_vals:
                    filtered_vals['competency_score_ids'] = record._filter_competency_score_commands(
                        filtered_vals['competency_score_ids'],
                        allowed_fields=SUPERVISOR_SCORING_FIELDS,
                    )
                non_kra = user_facing_fields - {'kra_ids'}
                if non_kra and not is_hr:
                    raise UserError('You can only edit supervisor scores and remarks right now.')
            elif record.can_secondary_supervisor_rate:
                if 'kra_ids' in filtered_vals:
                    filtered_vals['kra_ids'] = record._filter_kra_commands(
                        filtered_vals['kra_ids'],
                        allowed_kpi_fields=SECONDARY_SCORING_FIELDS,
                    )
                if 'competency_score_ids' in filtered_vals:
                    filtered_vals['competency_score_ids'] = record._filter_competency_score_commands(
                        filtered_vals['competency_score_ids'],
                        allowed_fields=SECONDARY_SCORING_FIELDS,
                    )
                non_kra = user_facing_fields - {'kra_ids'}
                if non_kra and not is_hr:
                    raise UserError('You can only edit secondary supervisor scores and remarks right now.')
            elif record.can_reviewer_rate:
                if 'kra_ids' in filtered_vals:
                    filtered_vals['kra_ids'] = record._filter_kra_commands(
                        filtered_vals['kra_ids'],
                        allowed_kpi_fields=REVIEWER_SCORING_FIELDS,
                    )
                if 'competency_score_ids' in filtered_vals:
                    filtered_vals['competency_score_ids'] = record._filter_competency_score_commands(
                        filtered_vals['competency_score_ids'],
                        allowed_fields=REVIEWER_SCORING_FIELDS,
                    )
                non_kra = user_facing_fields - {'kra_ids'}
                if non_kra and not is_hr:
                    raise UserError('You can only edit reviewer scores and remarks right now.')
            elif is_hr:
                pass
            else:
                raise UserError(
                    'You do not have permission to edit this performance plan at this stage.'
                )

        template_changed = 'template_id' in vals
        result = super().write(filtered_vals)
        if template_changed:
            self._sync_competency_scores()
        return result

    def _get_submit_confirmation_action(self, role, zero_kpis, zero_comps):
        message = ""
        if zero_kpis or zero_comps:
            message += "<div style='color: #856404; background-color: #fff3cd; border-color: #ffeeba; padding: 15px; border: 1px solid transparent; border-radius: 4px;'>"
            message += "<h4 style='margin-top:0;'>⚠️ Warning: Some items have a score of 0</h4>"
            message += "<ul>"
            for kpi in zero_kpis:
                message += f"<li><strong>KPI:</strong> {kpi.name}</li>"
            for comp in zero_comps:
                message += f"<li><strong>Competency:</strong> {comp.line_name}</li>"
            message += "</ul></div>"
            message += "<p class='mt-3'>Are you sure you want to proceed and submit these 0 scores?</p>"
        else:
            message = "<p class='fs-5'>Are you sure you want to submit your appraisal scores?</p>"
            
        wizard = self.env['pms.appraisal.submit.wizard'].create({
            'appraisal_id': self.id,
            'role': role,
            'message': message
        })
        
        return {
            'name': 'Confirm Submission',
            'type': 'ir.actions.act_window',
            'res_model': 'pms.appraisal.submit.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ─────────────────────────────────────────────────────────────
    # Filtering helpers
    # ─────────────────────────────────────────────────────────────

    def _filter_kra_commands(self, kra_commands, allowed_kpi_fields):
        filtered_kra_commands = []
        for cmd in kra_commands:
            cmd_code = cmd[0]
            if cmd_code == 1:
                kra_vals = dict(cmd[2]) if cmd[2] else {}
                if 'kpi_ids' in kra_vals:
                    filtered_kpi_commands = []
                    for kpi_cmd in kra_vals['kpi_ids']:
                        kpi_code = kpi_cmd[0]
                        if kpi_code == 1:
                            raw_kpi_vals = kpi_cmd[2] or {}
                            safe_kpi_vals = {
                                k: v for k, v in raw_kpi_vals.items()
                                if k in allowed_kpi_fields
                            }
                            if safe_kpi_vals:
                                filtered_kpi_commands.append((1, kpi_cmd[1], safe_kpi_vals))
                        elif kpi_code in (0, 2, 3):
                            if 'is_selected' not in allowed_kpi_fields:
                                continue
                            filtered_kpi_commands.append(kpi_cmd)
                        else:
                            filtered_kpi_commands.append(kpi_cmd)
                    kra_vals['kpi_ids'] = filtered_kpi_commands
                filtered_kra_commands.append((1, cmd[1], kra_vals))
            elif cmd_code == 0:
                filtered_kra_commands.append(cmd)
            else:
                filtered_kra_commands.append(cmd)
        return filtered_kra_commands

    def _filter_competency_score_commands(self, score_commands, allowed_fields):
        filtered = []
        for cmd in score_commands:
            cmd_code = cmd[0]
            if cmd_code == 1:
                raw_vals = cmd[2] or {}
                safe_vals = {k: v for k, v in raw_vals.items() if k in allowed_fields}
                if safe_vals:
                    filtered.append((1, cmd[1], safe_vals))
            elif cmd_code in (4, 5, 6):
                filtered.append(cmd)
        return filtered

    # ─────────────────────────────────────────────────────────────
    # Competency methods
    # ─────────────────────────────────────────────────────────────

    def _get_competency_template(self):
        self.ensure_one()
        appraisal_tmpl = self.template_id
        if not appraisal_tmpl:
            return self.env['competency.framework.template']
        comp_tmpl = getattr(appraisal_tmpl, 'competency_template_id', False)
        return comp_tmpl or self.env['competency.framework.template']

    def _sync_competency_scores(self):
        Score = self.env['appraisal.competency.score'].sudo()
        for appraisal in self:
            comp_tmpl = appraisal._get_competency_template()
            if not comp_tmpl:
                continue
            all_lines = self.env['competency.framework.line'].search([
                ('group_id.template_id', '=', comp_tmpl.id),
            ], order='group_id, sequence, id')
            if not all_lines:
                continue
            existing_line_ids = set(
                appraisal.competency_score_ids.mapped('competency_line_id').ids
            )
            new_vals = []
            for line in all_lines:
                if line.id not in existing_line_ids:
                    new_vals.append({
                        'appraisal_id': appraisal.id,
                        'competency_line_id': line.id,
                        'self_score': False,
                        'self_remarks': '',
                        'supervisor_score': False,
                        'supervisor_remarks': '',
                        'secondary_supervisor_score': False,
                        'secondary_supervisor_remarks': '',
                        'reviewer_score': False,
                        'reviewer_remarks': '',
                    })
            if new_vals:
                Score.create(new_vals)

    def get_competency_data(self):
        """Returns competency framework data formatted for the frontend widget."""
        self.ensure_one()
       
        self.sudo()._sync_competency_scores()

        comp_tmpl = self._get_competency_template()

        if not comp_tmpl:
            return {
                'has_competency_data': False,
                'competency_groups': [],
                'competency_totals': {
                    'max': 0.0,
                    'self': 0.0,
                    'supervisor': 0.0,
                    'secondary': 0.0,
                    'reviewer': 0.0,
                }
            }

        groups_data = []
        total_max = 0.0
        total_self = 0.0
        total_supervisor = 0.0
        total_secondary = 0.0
        total_reviewer = 0.0

        for group in comp_tmpl.group_ids.sorted(key=lambda g: (g.sequence, g.id)):
            group_lines = []
            for line in group.line_ids.sorted(key=lambda l: (l.sequence, l.id)):
                score_record = self.competency_score_ids.filtered(
                    lambda s: s.competency_line_id.id == line.id
                )[:1]

                line_data = {
                    'id': line.id,
                    'score_id': score_record.id or False,
                    'line_full_code': line.full_code or '',
                    'line_name': line.name or '',
                    'line_description': line.description or '',
                    'line_points': line.points or 0.0,
                    'line_sequence': line.sequence or 0,
                    'group_id': group.id,
                    'group_name': group.name or '',
                    'group_hr_code': group.hr_code or '',
                    'group_sequence': group.sequence or 0,
                    'self_score': score_record.self_score if score_record and score_record.self_score else False,
                    'supervisor_score': score_record.supervisor_score if score_record and score_record.supervisor_score else False,
                    'secondary_supervisor_score': score_record.secondary_supervisor_score if score_record and score_record.secondary_supervisor_score else False,
                    'reviewer_score': score_record.reviewer_score if score_record and score_record.reviewer_score else False,
                    'self_remarks': score_record.self_remarks if score_record and score_record.self_remarks else '',
                    'supervisor_remarks': score_record.supervisor_remarks if score_record and score_record.supervisor_remarks else '',
                    'secondary_supervisor_remarks': score_record.secondary_supervisor_remarks if score_record and score_record.secondary_supervisor_remarks else '',
                    'reviewer_remarks': score_record.reviewer_remarks if score_record and score_record.reviewer_remarks else '',
                }

                group_lines.append(line_data)

                total_max += line.points or 0.0
                if score_record:
                    total_self += score_record.self_score or 0.0
                    total_supervisor += score_record.supervisor_score or 0.0
                    total_secondary += score_record.secondary_supervisor_score or 0.0
                    total_reviewer += score_record.reviewer_score or 0.0

            if group_lines:
                groups_data.append({
                    'groupKey': group.id,
                    'groupId': group.id,
                    'groupName': group.name or 'Unnamed Group',
                    'groupCode': group.hr_code or '',
                    'groupSeq': group.sequence or 0,
                    'rows': group_lines,
                })

        groups_data.sort(key=lambda g: (g.get('groupSeq', 0), g.get('groupName', '')))

        return {
            'has_competency_data': bool(groups_data),
            'competency_groups': groups_data,
            'competency_totals': {
                'max': total_max,
                'self': total_self,
                'supervisor': total_supervisor,
                'secondary': total_secondary,
                'reviewer': total_reviewer,
            }
        }

    def save_competency_score(self, score_id, field_name, value):
        """
        Persist one competency score field from the JS widget.

        :param score_id:   int  - ID of the appraisal.competency.score row
        :param field_name: str  - field to update (e.g. 'self_score')
        :param value:      any  - new value (float for scores, str for remarks)
        :returns: True
        :raises UserError: if the caller is not authorised or value is invalid
        """
        self.ensure_one()

        EMPLOYEE_FIELDS   = {'self_score', 'self_remarks'}
        SUPERVISOR_FIELDS = {'supervisor_score', 'supervisor_remarks'}
        SECONDARY_FIELDS  = {
            'secondary_supervisor_score',
            'secondary_supervisor_remarks',
        }
        REVIEWER_FIELDS = {'reviewer_score', 'reviewer_remarks'}

        is_hr = self.env.user.has_group('hr_employee_evaluation.group_pms_hr_manager')

        appraisal = self.sudo()

        current_user     = self.env.user
        emp_user         = appraisal.employee_id.user_id
        sup_user         = appraisal.supervisor_id.user_id
        sec_sup_user     = appraisal.secondary_supervisor_id.user_id
        rev_user         = appraisal.reviewer_id.user_id
        cycle_in_appraisal = appraisal.cycle_id.state == 'appraisal'

        is_own     = bool(emp_user     and emp_user.id     == current_user.id)
        is_sup     = bool(sup_user     and sup_user.id     == current_user.id)
        is_sec_sup = bool(sec_sup_user and sec_sup_user.id == current_user.id)
        is_rev     = bool(rev_user     and rev_user.id     == current_user.id)

        can_emp  = is_own     and appraisal.state == 'appraisal_draft'                        and cycle_in_appraisal
        can_sup  = is_sup     and appraisal.state == 'appraisal_pending_supervisor'            and cycle_in_appraisal
        can_sec  = is_sec_sup and appraisal.state == 'appraisal_pending_secondary_supervisor'  and cycle_in_appraisal
        can_rev  = is_rev     and appraisal.state == 'appraisal_pending_reviewer'              and cycle_in_appraisal

        if can_emp:
            allowed = EMPLOYEE_FIELDS
        elif can_sup:
            allowed = SUPERVISOR_FIELDS
        elif can_sec:
            allowed = SECONDARY_FIELDS
        elif can_rev:
            allowed = REVIEWER_FIELDS
        elif is_hr:
            allowed = EMPLOYEE_FIELDS | SUPERVISOR_FIELDS | SECONDARY_FIELDS | REVIEWER_FIELDS
        else:
            raise UserError(
                'You are not authorised to enter scores on this appraisal '
                'at its current stage.'
            )

        if field_name not in allowed:
            raise UserError(
                f'You are not allowed to edit "{field_name}" at this stage.'
            )

        # Verify the score record belongs to this appraisal
        score = self.env['appraisal.competency.score'].sudo().browse(score_id)
        if not score.exists() or score.appraisal_id.id != self.id:
            raise UserError('Invalid competency score record.')

        # Numeric range validation
        numeric_fields = {
            'self_score', 'supervisor_score',
            'secondary_supervisor_score', 'reviewer_score',
        }
        if field_name in numeric_fields:
            value = float(value or 0.0)
            if value < 0:
                raise UserError(
                    f'Score cannot be negative for competency "{score.line_name}".'
                )
            if value > (score.line_points or 0.0):
                raise UserError(
                    f'Score ({value:.2f}) cannot exceed the maximum points '
                    f'({score.line_points:.2f}) for competency "{score.line_name}".'
                )
        else:
            value = str(value or '')

        score.sudo().write({field_name: value})
        return True

    def get_kra_data(self):
        """Returns KRA data formatted for the frontend widget."""
        self.ensure_one()

        kra_records = []
        for kra in self.kra_ids.sorted(key=lambda k: k.sequence):
            kpis = []
            for kpi in kra.kpi_ids:
                kpis.append({
                    'id': kpi.id,
                    'data': {
                        'name': kpi.name,
                        'description': kpi.description,
                        'weightage': kpi.weightage,
                        'criteria': kpi.criteria,
                        'target': kpi.target,
                        'planning_remarks': kpi.planning_remarks,
                        'is_selected': kpi.is_selected,
                        'self_score': kpi.self_score if kpi.self_score else False,
                        'supervisor_score': kpi.supervisor_score if kpi.supervisor_score else False,
                        'secondary_supervisor_score': kpi.secondary_supervisor_score if kpi.secondary_supervisor_score else False,
                        'reviewer_score': kpi.reviewer_score if kpi.reviewer_score else False,
                        'self_remarks': kpi.self_remarks,
                        'supervisor_remarks': kpi.supervisor_remarks,
                        'secondary_supervisor_score_remarks': kpi.secondary_supervisor_score_remarks,
                        'reviewer_remarks': kpi.reviewer_remarks,
                        'snapshot_employee_target': kpi.snapshot_employee_target,
                        'snapshot_employee_criteria': kpi.snapshot_employee_criteria,
                        'snapshot_supervisor_target': kpi.snapshot_supervisor_target,
                        'snapshot_supervisor_criteria': kpi.snapshot_supervisor_criteria,
                        'snapshot_secondary_target': kpi.snapshot_secondary_target,
                        'snapshot_secondary_criteria': kpi.snapshot_secondary_criteria,
                    }
                })

            kra_records.append({
                'id': kra.id,
                'data': {
                    'name': kra.name,
                    'sequence': kra.sequence,
                    'evidence_attachment_ids': kra.evidence_attachment_ids,
                },
                'kpis': kpis,
            })

        return {
            'kra_records': kra_records,
        }

    # ─────────────────────────────────────────────────────────────
    # State routing helpers
    # ─────────────────────────────────────────────────────────────

    def _next_state_after_supervisor(self):
        self.ensure_one()
        if self.secondary_supervisor_id:
            return 'pending_secondary_supervisor'
        elif self.reviewer_id:
            return 'pending_reviewer'
        return 'approved'

    def _next_state_after_secondary(self):
        self.ensure_one()
        if self.reviewer_id:
            return 'pending_reviewer'
        return 'approved'

    def _next_appraisal_state_after_supervisor(self):
        self.ensure_one()
        if self.secondary_supervisor_id:
            return 'appraisal_pending_secondary_supervisor'
        elif self.reviewer_id:
            return 'appraisal_pending_reviewer'
        return 'appraisal_approved'

    def _next_appraisal_state_after_secondary(self):
        self.ensure_one()
        if self.reviewer_id:
            return 'appraisal_pending_reviewer'
        return 'appraisal_approved'

    def _state_label(self, state_key):
        return dict(self._fields['state'].selection).get(state_key, state_key)

    # ─────────────────────────────────────────────────────────────
    # Notification helpers
    # ─────────────────────────────────────────────────────────────

    def _notify_next_approver(self, next_state):
        self.ensure_one()
        emp_name = self.employee_id.name
        todo = self.env.ref('mail.mail_activity_data_todo')

        if next_state == 'pending_secondary_supervisor' and self.secondary_supervisor_id.user_id:
            self.activity_schedule(
                activity_type_id=todo.id,
                user_id=self.secondary_supervisor_id.user_id.id,
                summary=f'Review performance plan for {emp_name}',
                note=f"{emp_name}'s plan has been approved by the primary supervisor.",
            )
        elif next_state == 'pending_reviewer' and self.reviewer_id.user_id:
            self.activity_schedule(
                activity_type_id=todo.id,
                user_id=self.reviewer_id.user_id.id,
                summary=f'Final review: performance plan for {emp_name}',
                note=f"{emp_name}'s plan is ready for your final approval.",
            )
        elif next_state == 'approved' and self.employee_id.user_id:
            self.activity_schedule(
                activity_type_id=todo.id,
                user_id=self.employee_id.user_id.id,
                summary='Your performance plan has been approved',
                note='Your performance plan has been fully approved.',
            )

    def _notify_next_appraisal_rater(self, next_state):
        self.ensure_one()
        emp_name = self.employee_id.name
        todo = self.env.ref('mail.mail_activity_data_todo')

        if next_state == 'appraisal_pending_secondary_supervisor' and self.secondary_supervisor_id.user_id:
            self.activity_schedule(
                activity_type_id=todo.id,
                user_id=self.secondary_supervisor_id.user_id.id,
                summary=f'Rate performance for {emp_name}',
                note=f'Supervisor rating for {emp_name} is done. Your rating is required.',
            )
        elif next_state == 'appraisal_pending_reviewer' and self.reviewer_id.user_id:
            self.activity_schedule(
                activity_type_id=todo.id,
                user_id=self.reviewer_id.user_id.id,
                summary=f'Final appraisal rating for {emp_name}',
                note=f"{emp_name}'s appraisal is ready for your final rating.",
            )
        elif next_state == 'appraisal_approved' and self.employee_id.user_id:
            self.activity_schedule(
                activity_type_id=todo.id,
                user_id=self.employee_id.user_id.id,
                summary='Your appraisal is complete',
                note='Your performance appraisal has been fully rated.',
            )

    # ─────────────────────────────────────────────────────────────
    # Planning phase actions
    # ─────────────────────────────────────────────────────────────

    def action_submit_for_review(self):
        self.ensure_one()

        today = fields.Date.today()
        if self.cycle_id.start_date and today < self.cycle_id.start_date:
            raise UserError(
                f"You cannot submit your plan before the cycle start date "
                f"({self.cycle_id.start_date})."
            )

        if self.state != 'draft':
            raise UserError('Only draft plans can be submitted.')

        if not self.can_employee_edit:
            raise UserError(
                'Cannot submit: you do not own this plan, it is locked, or past deadline.'
            )

        if self.selected_kpi_count == 0:
            raise UserError('Please select at least one KPI before submitting.')

        selected_kpis = self.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)

        if any(k.weightage <= 0 for k in selected_kpis):
            raise UserError('All selected KPIs must have a weightage greater than zero.')

        errors = []
        for kpi in selected_kpis:
            missing = []
            tgt = str(kpi.target).strip() if kpi.target else ''
            rem = str(kpi.planning_remarks).strip() if kpi.planning_remarks else ''
            
            if not tgt or tgt in ('<p><br></p>', 'False', 'None'):
                missing.append('Target')
 
            if missing:
                kra_name = kpi.kra_id.name or 'Unknown KRA'
                missing_str = ' & '.join(missing)
                errors.append(f'• [{kra_name}] → {kpi.name} ({missing_str} missing)')

        if errors:
            error_lines = '\n'.join(errors)
            raise UserError(
                f'Cannot submit. The following {len(errors)} KPI(s) are missing required fields:\n\n'
                f'{error_lines}\n\n'
                f'Please fill in all missing Targets and Remarks before submitting.'
            )

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
        self._snapshot_employee_targets()
        return True

    def action_supervisor_approve(self):
        self.ensure_one()

        if self.state != 'pending_supervisor':
            raise UserError('Only plans pending supervisor review can be approved here.')

        if not self.is_supervisor_of_appraisal:
            raise UserError('Only the assigned supervisor can approve this plan.')

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
        self._snapshot_supervisor_targets()
        return True

    def action_secondary_supervisor_approve(self):
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
        self._snapshot_secondary_supervisor_targets()
        return True

    def action_reviewer_approve(self):
        self.ensure_one()

        if self.state != 'pending_reviewer':
            raise UserError('Only plans pending reviewer approval can be approved here.')

        if not self.is_reviewer_of_appraisal:
            raise UserError('Only the assigned reviewer can give final approval.')

        self.with_context(skip_edit_check=True).write({
            'state': 'approved',
            'reviewer_approval_date': fields.Datetime.now(),
        })

        self._notify_next_approver('approved')
        self.message_post(
            body=f"Plan fully approved by reviewer {self.reviewer_id.name}. Planning phase complete.",
            message_type='notification',
        )
        return True

    def action_hr_reset_to_draft(self):
        self.ensure_one()
        if not self.env.user.has_group('hr_employee_evaluation.group_pms_hr_manager'):
            raise UserError('Only HR/Admin can reset a plan to draft.')

        self.kra_ids.mapped('kpi_ids').write({
            'snapshot_employee_target': False,
            'snapshot_supervisor_target': False,
            'snapshot_secondary_target': False,
        })

        self.with_context(skip_edit_check=True).write({
            'state': 'draft',
            'draft_reset_date': fields.Datetime.now(),
        })

        if self.employee_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.employee_id.user_id.id,
                summary='Your performance plan has been reset',
                note=(
                    f'HR has reset your performance plan to draft. '
                    f'You have {self.cycle_id.resubmission_days} days from today to revise and resubmit.'
                ),
            )

        self.message_post(
            body=(
                f"Plan reset to draft by HR ({self.env.user.name}). "
                f"Employee has {self.cycle_id.resubmission_days} days to resubmit."
            ),
            message_type='notification',
        )
        return True

    # ─────────────────────────────────────────────────────────────
    # Snapshot helpers
    # ─────────────────────────────────────────────────────────────

    def _snapshot_employee_targets(self):
        self.ensure_one()
        for kpi in self.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected):
            kpi.write({
                'snapshot_employee_target': kpi.target or '',
                'snapshot_employee_criteria': kpi.criteria or ''
                })

    def _snapshot_supervisor_targets(self):
        self.ensure_one()
        for kpi in self.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected):
            kpi.write({
                'snapshot_supervisor_target': kpi.target or '',
                'snapshot_supervisor_criteria': kpi.criteria or ''
                })

    def _snapshot_secondary_supervisor_targets(self):
        self.ensure_one()
        for kpi in self.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected):
            kpi.write({
                'snapshot_secondary_target': kpi.target or '',
                'snapshot_secondary_criteria': kpi.criteria or ''
            })

    # ─────────────────────────────────────────────────────────────
    # Template cloning
    # ─────────────────────────────────────────────────────────────

    def _clone_template_structure(self):
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

    # ─────────────────────────────────────────────────────────────
    # Report actions
    # ─────────────────────────────────────────────────────────────

    def action_view_plan_summary(self):
        self.ensure_one()
        self._generate_excel_attachment('plan')
        report = self.env.ref('hr_employee_evaluation.action_report_plan_summary')
        return {
            'type': 'ir.actions.act_url',
            'url': '/report/html/%s/%s' % (report.report_name, self.id),
            'target': 'new',
        }

    def action_view_appraisal_summary(self):
        self.ensure_one()
        self._generate_excel_attachment('appraisal')
        report = self.env.ref('hr_employee_evaluation.action_report_appraisal_summary')
        return {
            'type': 'ir.actions.act_url',
            'url': '/report/html/%s/%s' % (report.report_name, self.id),
            'target': 'new',
        }

    def action_sync_competency_scores(self):
        """Manual sync action for HR to trigger competency score synchronization"""
        self.ensure_one()
        self._sync_competency_scores()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'Competency scores synchronized successfully.',
                'type': 'success',
                'sticky': False,
            }
        }

    def _generate_excel_attachment(self, report_type):
        """Silently generates an Excel file and saves it as an Odoo attachment"""
        if not xlsxwriter:
            return
            
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        header_format = workbook.add_format({'bold': True, 'bg_color': '#f8f9fa', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        cell_format = workbook.add_format({'border': 1, 'text_wrap': True, 'valign': 'top'})
        cell_center = workbook.add_format({'border': 1, 'text_wrap': True, 'valign': 'top', 'align': 'center'})
        kra_format = workbook.add_format({'bold': True, 'bg_color': '#f1f3f5', 'border': 1, 'text_wrap': True, 'valign': 'top'})

        if report_type == 'plan':
            sheet = workbook.add_worksheet('Plan Summary')
            
            headers = ['KRA Name', 'KPI Name', 'Description', 'Criteria', 'Target', 'Score']
            for col, head in enumerate(headers):
                sheet.write(0, col, head, header_format)
            sheet.set_column(0, 1, 20)
            sheet.set_column(2, 4, 35)
            sheet.set_column(5, 5, 10)

            row = 1
            for kra in self.kra_ids:
                active_kpis = kra.kpi_ids.filtered(lambda k: k.is_selected)
                for kpi in active_kpis:
                    sheet.write(row, 0, kra.name or '', kra_format)
                    sheet.write(row, 1, kpi.name or '', cell_format)
                    sheet.write(row, 2, kpi.description or '', cell_format)
                    sheet.write(row, 3, kpi.criteria or '', cell_format)
                    sheet.write(row, 4, kpi.target or '', cell_format)
                    sheet.write(row, 5, kpi.weightage or 0.0, cell_center)
                    row += 1
                    
            filename = f'Plan_Summary_{self.employee_id.name.replace(" ", "_")}.xlsx'
            
        else:  # Appraisal
            sheet = workbook.add_worksheet('Appraisal Summary')
            
            headers = ['KRA Name', 'KPI Name', 'Criteria', 'Target', 'Max', 'Emp Score', 'Sup Score']
            if self.secondary_supervisor_id:
                headers.append('2nd Sup Score')
            if self.reviewer_id:
                headers.append('Rev Score')

            for col, head in enumerate(headers):
                sheet.write(0, col, head, header_format)

            sheet.set_column(0, 1, 20)
            sheet.set_column(2, 3, 35)
            sheet.set_column(4, len(headers)-1, 12)

            row = 1
            for kra in self.kra_ids:
                active_kpis = kra.kpi_ids.filtered(lambda k: k.is_selected)
                for kpi in active_kpis:
                    sheet.write(row, 0, kra.name or '', kra_format)
                    sheet.write(row, 1, kpi.name or '', cell_format)
                    sheet.write(row, 2, kpi.criteria or '', cell_format)
                    sheet.write(row, 3, kpi.target or '', cell_format)
                    sheet.write(row, 4, kpi.weightage or 0.0, cell_center)
                    sheet.write(row, 5, kpi.self_score or 0.0, cell_center)
                    sheet.write(row, 6, kpi.supervisor_score or 0.0, cell_center)
                    col = 7
                    if self.secondary_supervisor_id:
                        sheet.write(row, col, kpi.secondary_supervisor_score or 0.0, cell_center)
                        col += 1
                    if self.reviewer_id:
                        sheet.write(row, col, kpi.reviewer_score or 0.0, cell_center)
                    row += 1
                    
            filename = f'Appraisal_Summary_{self.employee_id.name.replace(" ", "_")}.xlsx'

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()

        # Delete old excel attachments
        old_attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'pms.appraisal'),
            ('res_id', '=', self.id),
            ('name', '=', filename)
        ])
        old_attachments.unlink()

        # Create new native Odoo attachment
        self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': file_data,
            'res_model': 'pms.appraisal',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

    # ─────────────────────────────────────────────────────────────
    # Appraisal phase actions with validation
    # ─────────────────────────────────────────────────────────────

    def action_submit_self_rating(self):
        self.ensure_one()
        if self.state != 'appraisal_draft':
            raise UserError('Only appraisal plans in draft can be self-rated.')
        if not self.can_employee_self_rate:
            raise UserError(
                'Cannot submit: you do not own this plan or the cycle is not in appraisal.'
            )

        selected_kpis = self.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)

        # Validate KPI scores
        for kpi in selected_kpis:
            if kpi.self_score < 0:
                raise UserError(f'Self score for "{kpi.name}" cannot be negative.')
            if kpi.self_score > kpi.weightage:
                raise UserError(
                    f'Self score ({kpi.self_score}) for "{kpi.name}" '
                    f'cannot exceed the allocated score ({kpi.weightage}).'
                )

        # Validate Competency scores
        for competency in self.competency_score_ids:
            if competency.self_score < 0:
                raise UserError(f'Self score for competency "{competency.line_name}" cannot be negative.')
            if competency.self_score > competency.line_points:
                raise UserError(
                    f'Self score ({competency.self_score}) for competency "{competency.line_name}" '
                    f'cannot exceed the maximum points ({competency.line_points}).'
                )

        self.with_context(skip_edit_check=True).write({'state': 'appraisal_pending_supervisor'})

        if self.supervisor_id and self.supervisor_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.supervisor_id.user_id.id,
                summary=f'Rate performance for {self.employee_id.name}',
                note=f'{self.employee_id.name} has submitted their self-rating.',
            )

        self.message_post(
            body=f'Self-rating submitted by {self.employee_id.name}.',
            message_type='notification',
        )
        return True

    def action_supervisor_submit_rating(self):
        self.ensure_one()
        if self.state != 'appraisal_pending_supervisor':
            raise UserError('Only plans pending supervisor rating can be rated here.')
        if not self.is_supervisor_of_appraisal:
            raise UserError('Only the assigned supervisor can submit a rating.')

        selected_kpis = self.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)

        for kpi in selected_kpis:
            if kpi.supervisor_score < 0:
                raise UserError(f'Supervisor score for "{kpi.name}" cannot be negative.')
            if kpi.supervisor_score > kpi.weightage:
                raise UserError(
                    f'Supervisor score ({kpi.supervisor_score}) for "{kpi.name}" '
                    f'cannot exceed the allocated score ({kpi.weightage}).'
                )

        # Validate competency scores
        for competency in self.competency_score_ids:
            if competency.supervisor_score < 0:
                raise UserError(f'Supervisor score for competency "{competency.line_name}" cannot be negative.')
            if competency.supervisor_score > competency.line_points:
                raise UserError(
                    f'Supervisor score ({competency.supervisor_score}) for competency "{competency.line_name}" '
                    f'cannot exceed the maximum points ({competency.line_points}).'
                )

        next_state = self._next_appraisal_state_after_supervisor()
        self.with_context(skip_edit_check=True).write({
            'state': next_state,
            'supervisor_review_date': fields.Datetime.now(),
        })
        self._notify_next_appraisal_rater(next_state)
        self.message_post(
            body=(
                f'Supervisor rating submitted by {self.supervisor_id.name}. '
                f'Status → {self._state_label(next_state)}.'
            ),
            message_type='notification',
        )
        return True

    def action_secondary_supervisor_submit_rating(self):
        self.ensure_one()
        if self.state != 'appraisal_pending_secondary_supervisor':
            raise UserError('Only plans pending secondary supervisor rating can be rated here.')
        if not self.is_secondary_supervisor_of_appraisal:
            raise UserError('Only the assigned secondary supervisor can submit a rating.')

        selected_kpis = self.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)

        for kpi in selected_kpis:
            if kpi.secondary_supervisor_score < 0:
                raise UserError(f'Secondary supervisor score for "{kpi.name}" cannot be negative.')
            if kpi.secondary_supervisor_score > kpi.weightage:
                raise UserError(
                    f'Secondary supervisor score ({kpi.secondary_supervisor_score}) for "{kpi.name}" '
                    f'cannot exceed the allocated score ({kpi.weightage}).'
                )

        # Validate competency scores
        for competency in self.competency_score_ids:
            if competency.secondary_supervisor_score < 0:
                raise UserError(f'Secondary supervisor score for competency "{competency.line_name}" cannot be negative.')
            if competency.secondary_supervisor_score > competency.line_points:
                raise UserError(
                    f'Secondary supervisor score ({competency.secondary_supervisor_score}) for competency "{competency.line_name}" '
                    f'cannot exceed the maximum points ({competency.line_points}).'
                )

        next_state = self._next_appraisal_state_after_secondary()
        self.with_context(skip_edit_check=True).write({
            'state': next_state,
            'secondary_supervisor_review_date': fields.Datetime.now(),
        })
        self._notify_next_appraisal_rater(next_state)
        self.message_post(
            body=(
                f'Secondary supervisor rating submitted by {self.secondary_supervisor_id.name}. '
                f'Status → {self._state_label(next_state)}.'
            ),
            message_type='notification',
        )
        return True

    def action_reviewer_submit_rating(self):
        self.ensure_one()
        if self.state != 'appraisal_pending_reviewer':
            raise UserError('Only plans pending reviewer rating can be rated here.')
        if not self.is_reviewer_of_appraisal:
            raise UserError('Only the assigned reviewer can submit the final rating.')

        selected_kpis = self.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)

        for kpi in selected_kpis:
            if kpi.reviewer_score < 0:
                raise UserError(f'Reviewer score for "{kpi.name}" cannot be negative.')
            if kpi.reviewer_score > kpi.weightage:
                raise UserError(
                    f'Reviewer score ({kpi.reviewer_score}) for "{kpi.name}" '
                    f'cannot exceed the allocated score ({kpi.weightage}).'
                )

        # Validate competency scores
        for competency in self.competency_score_ids:
            if competency.reviewer_score < 0:
                raise UserError(f'Reviewer score for competency "{competency.line_name}" cannot be negative.')
            if competency.reviewer_score > competency.line_points:
                raise UserError(
                    f'Reviewer score ({competency.reviewer_score}) for competency "{competency.line_name}" '
                    f'cannot exceed the maximum points ({competency.line_points}).'
                )

        self.with_context(skip_edit_check=True).write({
            'state': 'appraisal_approved',
            'reviewer_approval_date': fields.Datetime.now(),
        })

        if self.employee_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.employee_id.user_id.id,
                summary='Your appraisal is complete',
                note='Your performance appraisal has been fully rated.',
            )

        self.message_post(
            body=f'Appraisal complete. Final rating submitted by {self.reviewer_id.name}.',
            message_type='notification',
        )
        return True

    def action_hr_reset_appraisal_to_draft(self):
        self.ensure_one()
        if not self.env.user.has_group('hr_employee_evaluation.group_pms_hr_manager'):
            raise UserError('Only HR/Admin can reset an appraisal.')

        appraisal_states = {
            'appraisal_draft', 'appraisal_pending_supervisor',
            'appraisal_pending_secondary_supervisor',
            'appraisal_pending_reviewer', 'appraisal_approved',
        }
        if self.state not in appraisal_states:
            raise UserError('Can only reset records that are in the appraisal phase.')

        self.kra_ids.mapped('kpi_ids').write({
            'self_score': False,
            'self_remarks': False,
            'supervisor_score': False,
            'supervisor_remarks': False,
            'secondary_supervisor_score': False,
            'secondary_supervisor_score_remarks': False,
            'reviewer_score': False,
            'reviewer_remarks': False,
        })

        self.competency_score_ids.write({
            'self_score': False,
            'self_remarks': '',
            'supervisor_score': False,
            'supervisor_remarks': '',
            'secondary_supervisor_score': False,
            'secondary_supervisor_remarks': '',
            'reviewer_score': False,
            'reviewer_remarks': '',
        })

        self.with_context(skip_edit_check=True).write({
            'state': 'appraisal_draft',
            'appraisal_reset_date': fields.Datetime.now(),
        })

        if self.employee_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.employee_id.user_id.id,
                summary='Your appraisal has been reset',
                note='HR has reset your appraisal to draft. Please re-enter your self-rating.',
            )

        self.message_post(
            body=f'Appraisal reset to draft by HR ({self.env.user.name}). All scores cleared.',
            message_type='notification',
        )
        return True