from odoo import models, fields, api

class KpiTemplate(models.Model):
    _name = 'kpi.template'
    _description = 'KPI Template Master'

    name = fields.Char(string='Template Name', required=True)
    evaluation_group = fields.Char(string='Evaluation Group')
    total_marks = fields.Float(string='Total Marks', default=100.0)

    # One2many: one template has many KPI lines
    line_ids = fields.One2many(
        'kpi.template.line',
        'template_id',
        string='KPI Lines',
        copy=True
    )

    # Computed field: sum of scores from all lines
    computed_total = fields.Float(
        string='Computed Total',
        compute='_compute_total',
        store=True
    )

    @api.depends('line_ids.score')
    def _compute_total(self):
        for template in self:
            template.computed_total = sum(line.score for line in template.line_ids)