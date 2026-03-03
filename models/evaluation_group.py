from odoo import models, fields, api

class EvaluationGroup(models.Model):
    _name = 'pms.evaluation.group'
    _description = 'Evaluation Group'

    name = fields.Char(required=True)
    code = fields.Char()
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        required=True, 
        default=lambda self: self.env.company
    )
    employee_ids = fields.One2many(
        'hr.employee', 
        'evaluation_group_id', 
        string='Employees'
    )
    employee_count = fields.Integer(string='Employee Count', compute='_compute_employee_count')
    active = fields.Boolean(string='Active', default=True)

    @api.depends('employee_ids')
    def _compute_employee_count(self):
        for group in self:
            group.employee_count = self.env['hr.employee'].search_count([('evaluation_group_id', '=', group.id)])
    
    _name_unique = models.Constraint(
        'UNIQUE(name, company_id)', 
        'The Evaluation Group name must be unique per company!'
    )