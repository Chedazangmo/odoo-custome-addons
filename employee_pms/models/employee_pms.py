from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    secondary_manager_id = fields.Many2one(
        'hr.employee',
        string='Secondary Manager',
        domain="[('id', '!=', id)]",
    )

    reviewer_id = fields.Many2one(
        'hr.employee',
        string='Reviewer',
        domain="[('id', '!=', id)]",
    )

    evaluation_group_id = fields.Many2one(
        'pms.evaluation.group',
        string='Evaluation Group'
    )


    @api.constrains('parent_id')
    def _check_employee_not_own_manager(self):
        for employee in self:
            if employee.parent_id == employee:
                raise ValidationError(
                    "An employee cannot be their own manager."
                )

    @api.constrains('secondary_manager_id', 'parent_id')
    def _check_managers_not_same(self):
        for rec in self:
            if rec.secondary_manager_id and rec.parent_id and \
               rec.secondary_manager_id == rec.parent_id:
                raise ValidationError(
                    "Primary and Secondary Manager cannot be the same person"
                )
    
    @api.constrains('reviewer_id')
    def _check_employee_not_own_reviewer(self):
        for employee in self:
            if employee.reviewer_id == employee:
                raise ValidationError(
                    "An employee cannot be their own reviewer."
                )

    @api.constrains('secondary_manager_id', 'reviewer_id')
    def _check_secondary_manager_and_reviewer_not_same(self):
        for employee in self:
            if employee.secondary_manager_id and employee.reviewer_id and \
               employee.secondary_manager_id == employee.reviewer_id:
                raise ValidationError(
                    "Secondary Manager and Reviewer cannot be the same person."
                )

    @api.constrains('parent_id', 'reviewer_id')
    def _check_reviewer_not_reporting_to_employee(self):
        for employee in self:
            if employee.reviewer_id and employee.reviewer_id.parent_id == employee:
                raise ValidationError(
                    "Reviewer cannot report to the employee."
                )

 