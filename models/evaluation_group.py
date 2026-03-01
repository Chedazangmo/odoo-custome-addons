from odoo import models, fields

class EvaluationGroup(models.Model):
    _name = 'pms.evaluation.group'
    _description = 'Evaluation Group'

    name = fields.Char(required=True)
    code = fields.Char()
    active = fields.Boolean(default=True)
