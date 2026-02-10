from odoo import models, fields


class EvaluationGroup(models.Model):
    _name = 'evaluation.group'
    _description = 'Evaluation Group'

    name = fields.Char(string='Group Name', required=True)
    description = fields.Text(string='Description')

    # Optional: Add color for UI
    color = fields.Integer(string='Color Index')