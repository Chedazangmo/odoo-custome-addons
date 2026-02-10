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
    department_id = fields.Many2one('hr.department', related='employee_id.department_id')

    # === TEMPLATES (FROM YOUR kpi_form MODULE) ===
    kpi_template_id = fields.Many2one('kpi.template', string='KPI Template', required=True)
    competency_template_id = fields.Many2one('competency.template', string='Competency Template', required=True)

    # === USE YOUR EXISTING LINE MODELS ===
    kpi_line_ids = fields.One2many(
        'kpi.template.line',  # ✅ YOUR EXISTING MODEL from kpi_form
        'performance_plan_id',  # You need to add this field to kpi.template.line
        string='KPI Targets',
        domain=[('is_template_line', '=', False)],  # Only show performance plan lines
        copy=True
    )

    competency_line_ids = fields.One2many(
        'competency.template.line',  # ✅ YOUR EXISTING MODEL from kpi_form
        'performance_plan_id',  # You need to add this field to competency.template.line
        string='Competency Targets',
        domain=[('is_template_line', '=', False)],  # Only show performance plan lines
        copy=True
    )

    # === WORKFLOW ===
    state = fields.Selection([
        ('draft', 'Draft - Setting Targets'),
        ('submitted', 'Submitted for Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', tracking=True)

    # === METHODS ===
    def _auto_populate_kpi_lines(self):
        """Create copies of KPI template lines linked to this performance plan"""
        # Clear existing
        self.kpi_line_ids = [(5, 0, 0)]

        for template_line in self.kpi_template_id.line_ids:
            # Create a COPY of the template line
            self.env['kpi.template.line'].create({
                'performance_plan_id': self.id,  # Links to this performance plan
                'template_id': template_line.template_id.id,  # Reference original template
                'kpi_name': template_line.kpi_name,
                'definition': template_line.definition,
                'score': template_line.score,  # Max score
                'employee_target': '',  # Empty for employee to fill
                'target_score': 0,  # Will be set by employee
                'is_template_line': False,  # This is a performance plan line, not template
            })

    def _auto_populate_competency_lines(self):
        """Create copies of competency template lines linked to this performance plan"""
        # Clear existing
        self.competency_line_ids = [(5, 0, 0)]

        for template_line in self.competency_template_id.line_ids:
            # Create a COPY of the template line
            self.env['competency.template.line'].create({
                'performance_plan_id': self.id,  # Links to this performance plan
                'template_id': template_line.template_id.id,  # Reference original template
                'competency_name': template_line.competency_name,
                'competency_definition': template_line.competency_definition,
                'points': template_line.points,  # Max points
                'employee_target': '',  # Empty for employee to fill
                'target_points': 0,  # Will be set by employee
                'is_template_line': False,  # This is a performance plan line, not template
            })

    def action_submit_for_approval(self):
        """Employee submits targets for approval"""
        for kpi_line in self.kpi_line_ids:
            if not kpi_line.employee_target:
                raise ValidationError(f"Please fill target for KPI: {kpi_line.kpi_name}")

        for comp_line in self.competency_line_ids:
            if not comp_line.employee_target:
                raise ValidationError(f"Please fill target for Competency: {comp_line.competency_name}")

        self.state = 'submitted'