from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class PerformancePlan(models.Model):
    _name = 'performance.plan'
    _description = 'Performance Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # === BASIC FIELDS ===
    evaluation_planning_id = fields.Many2one(
        'evaluation.planning',
        string='Evaluation Plan',
        readonly=True,
        ondelete='cascade'
    )

    name = fields.Char(string='Plan Reference', default="New")
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', readonly=True)

    # === GROUP/EVALUATION GROUP FIELD (IMPORTANT FOR TEMPLATE ASSIGNMENT) ===
    evaluation_group_id = fields.Many2one(
        'evaluation.group',
        string='Evaluation Group',
        help="Group that determines which templates to use"
    )

    # === TEMPLATES ===
    kpi_template_id = fields.Many2one('kpi.template', string='KPI Template')
    competency_template_id = fields.Many2one('competency.template', string='Competency Template')

    # === LINE MODELS ===
    kpi_line_ids = fields.One2many(
        'performance.plan.kpi.line',
        'performance_plan_id',
        string='KPI Targets'
    )

    competency_line_ids = fields.One2many(
        'performance.plan.competency.line',
        'performance_plan_id',
        string='Competency Targets'
    )

    # === WORKFLOW ===
    state = fields.Selection([
        ('draft', 'Draft - Setting Targets'),
        ('submitted', 'Submitted for Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', tracking=True)

    # === COMPUTED TOTALS ===
    kpi_total_max = fields.Float(
        string='Total Max Score',
        compute='_compute_kpi_totals',
        store=True
    )


    competency_total_max = fields.Float(
        string='Total Max Points',
        compute='_compute_competency_totals',
        store=True
    )



    # === APPROVAL FIELDS ===
    employee_comments = fields.Text(string='Employee Comments')
    manager_comments = fields.Text(string='Manager Comments')
    approval_date = fields.Date(string='Approval Date', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Set sequence number on create - handles both single and multiple creates"""
        # Ensure vals_list is always a list
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        # Process each value dictionary
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('performance.plan') or 'New'

        # Call parent create
        records = super().create(vals_list)

        # Auto-assign templates for each created record
        for record in records:
            if record.evaluation_group_id:
                record._auto_assign_templates()

        return records

    @api.depends('kpi_line_ids.max_score')
    def _compute_kpi_totals(self):
        for plan in self:
            plan.kpi_total_max = sum(line.max_score for line in plan.kpi_line_ids)

    @api.depends('competency_line_ids.max_points')
    def _compute_competency_totals(self):
        for plan in self:
            plan.competency_total_max = sum(line.max_points for line in plan.competency_line_ids)

    def _auto_assign_templates(self):
        """Auto-assign templates based on evaluation group"""
        if self.evaluation_group_id:
            # Search for KPI template linked to this evaluation group
            kpi_template = self.env['kpi.template'].search([
                ('evaluation_group_id', '=', self.evaluation_group_id.id),
            ], limit=1)

            # Search for competency template linked to this evaluation group
            competency_template = self.env['competency.template'].search([
                ('evaluation_group_id', '=', self.evaluation_group_id.id),
            ], limit=1)

            if kpi_template:
                self.kpi_template_id = kpi_template
            if competency_template:
                self.competency_template_id = competency_template
    @api.onchange('evaluation_group_id')
    def _onchange_evaluation_group_id(self):
        """When evaluation group changes, auto-assign templates"""
        if self.evaluation_group_id:
            self._auto_assign_templates()

    @api.onchange('kpi_template_id')
    def _onchange_kpi_template_id(self):
        """Populate KPI lines from template when template changes"""
        if self.kpi_template_id and self.state == 'draft':
            self._auto_populate_kpi_lines()

    @api.onchange('competency_template_id')
    def _onchange_competency_template_id(self):
        """Populate competency lines from template when template changes"""
        if self.competency_template_id and self.state == 'draft':
            self._auto_populate_competency_lines()

    def _auto_populate_kpi_lines(self):
        """Copy from template to our OWN models"""
        if not self.kpi_template_id:
            return

        # Clear existing lines
        self.kpi_line_ids = [(5, 0, 0)]

        try:
            # Check if template model exists
            if self.env['kpi.template'].search_count([('id', '=', self.kpi_template_id.id)]) > 0:
                for template_line in self.kpi_template_id.line_ids:
                    self.env['performance.plan.kpi.line'].create({
                        'performance_plan_id': self.id,
                        'kpi_name': template_line.kpi_name,
                        'definition': template_line.definition,
                        'max_score': template_line.score,
                        'employee_target': '',  # Empty for employee to fill
                    })
        except Exception as e:
            _logger.error(f"Error loading KPI template: {e}")
            raise UserError(f"Error loading KPI template: {str(e)}")

    def _auto_populate_competency_lines(self):
        """Copy from template to our OWN models"""
        if not self.competency_template_id:
            return

        # Clear existing lines
        self.competency_line_ids = [(5, 0, 0)]

        try:
            # Check if template model exists
            if self.env['competency.template'].search_count([('id', '=', self.competency_template_id.id)]) > 0:
                for template_line in self.competency_template_id.line_ids:
                    self.env['performance.plan.competency.line'].create({
                        'performance_plan_id': self.id,
                        'competency_name': template_line.competency_name,
                        'definition': template_line.competency_definition,
                        'max_points': template_line.points,
                        'employee_target': '',  # Empty for employee to fill
                    })
        except Exception as e:
            _logger.error(f"Error loading competency template: {e}")
            raise UserError(f"Error loading competency template: {str(e)}")

    def action_submit_for_approval(self):
        """Employee submits targets for approval"""
        # Validate all targets are filled
        for kpi_line in self.kpi_line_ids:
            if not kpi_line.employee_target or kpi_line.employee_target.strip() == '':
                raise ValidationError(f"Please fill target for KPI: {kpi_line.kpi_name}")

        for comp_line in self.competency_line_ids:
            if not comp_line.employee_target or comp_line.employee_target.strip() == '':
                raise ValidationError(f"Please fill target for Competency: {comp_line.competency_name}")

        self.state = 'submitted'

        # Notify manager
        if self.employee_id.parent_id and self.employee_id.parent_id.user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=f'Performance Plan Submitted: {self.name}',
                note=f'{self.employee_id.name} has submitted their performance plan for your approval.',
                user_id=self.employee_id.parent_id.user_id.id
            )

    def action_approve(self):
        """Manager approves the plan"""
        self.state = 'approved'
        self.approval_date = fields.Date.today()

        # Notify employee
        if self.employee_id.user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=f'Performance Plan Approved: {self.name}',
                note=f'Your performance plan has been approved by your manager.',
                user_id=self.employee_id.user_id.id
            )

    def action_reject(self):
        """Manager rejects the plan"""
        if not self.manager_comments:
            raise ValidationError("Please provide rejection comments")

        self.state = 'rejected'

        # Notify employee
        if self.employee_id.user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=f'Performance Plan Rejected: {self.name}',
                note=f'Your performance plan was rejected. Comments: {self.manager_comments}',
                user_id=self.employee_id.user_id.id
            )

    def action_reset_to_draft(self):
        """Reset plan to draft for revisions"""
        if self.state in ['rejected', 'submitted']:
            self.state = 'draft'
            self.manager_comments = False

    # === CONSTRAINTS ===
    @api.constrains('kpi_template_id', 'competency_template_id')
    def _check_template_availability(self):
        """Validate that templates exist in the system"""
        if self.kpi_template_id and not self.env['kpi.template'].search_count([('id', '=', self.kpi_template_id.id)]):
            raise ValidationError("Selected KPI template is not available in the system.")

        if self.competency_template_id and not self.env['competency.template'].search_count(
                [('id', '=', self.competency_template_id.id)]):
            raise ValidationError("Selected competency template is not available in the system.")

    def action_load_kpi_template(self):
        """Manual button to load KPI template"""
        self.ensure_one()

        if self.state != 'draft':
            raise UserError("You can only load templates in draft state.")

        if not self.kpi_template_id:
            raise UserError("Please select a KPI template first.")

        self._auto_populate_kpi_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Template Loaded',
                'message': f'KPI template "{self.kpi_template_id.name}" loaded successfully.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_load_competency_template(self):
        """Manual button to load competency template"""
        self.ensure_one()

        if self.state != 'draft':
            raise UserError("You can only load templates in draft state.")

        if not self.competency_template_id:
            raise UserError("Please select a competency template first.")

        self._auto_populate_competency_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Template Loaded',
                'message': f'Competency template "{self.competency_template_id.name}" loaded successfully.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_load_templates(self):
        """Load both templates at once"""
        self.ensure_one()

        if self.state != 'draft':
            raise UserError("You can only load templates in draft state.")

        loaded = False
        messages = []

        if self.kpi_template_id:
            self._auto_populate_kpi_lines()
            messages.append(f'KPI: {self.kpi_template_id.name}')
            loaded = True

        if self.competency_template_id:
            self._auto_populate_competency_lines()
            messages.append(f'Competency: {self.competency_template_id.name}')
            loaded = True

        if not loaded:
            raise UserError("Please select KPI and/or Competency templates first.")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Templates Loaded',
                'message': 'Loaded: ' + ', '.join(messages),
                'type': 'success',
                'sticky': False,
            }
        }