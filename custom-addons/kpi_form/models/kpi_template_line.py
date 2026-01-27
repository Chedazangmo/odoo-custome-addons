from odoo import models, fields


class KpiTemplateLine(models.Model):
    _name = 'kpi.template.line'
    _description = 'KPI Template Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    template_id = fields.Many2one(
        'kpi.template',
        string='Template',
        required=True,
        ondelete='cascade'
    )

    # KPI Details
    kpi_name = fields.Char(string='KPI Name', required=True)
    definition = fields.Text(string='KPI Definition')

    # Scoring
    score = fields.Float(string='Score', required=True)
    weight = fields.Float(string='Weight (%)', default=0.0)  # ADDED
    max_score = fields.Float(string='Maximum Score', default=100.0)  # ADDED

    # Target Information
    target_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('amount', 'Amount'),
        ('count', 'Count'),
        ('binary', 'Yes/No')
    ], string='Target Type', default='percentage')

    evaluation_criteria = fields.Text(string='Evaluation Criteria')
    measurement_unit = fields.Char(string='Unit of Measurement')  # ADDED