from odoo import models, fields, api

class KpiTemplate(models.Model):
    _name = 'kpi.template'
    _description = 'KPI Template Master'

    name = fields.Char(string='Template Name', required=True)
    evaluation_group = fields.Char(string='Evaluation Group')

    # One2many: one template has many KPI lines
    line_ids = fields.One2many(
        'kpi.template.line',
        'template_id',
        string='KPI Lines',
        copy=True
    )
