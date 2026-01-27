from odoo import models, fields


class KpiTemplateLine(models.Model):
    _name = 'kpi.template.line'
    _description = 'KPI Template Line'
    _order = 'id'

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
    evaluation_criteria = fields.Text(string='Evaluation Criteria')