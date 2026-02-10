from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # Manager (built-in: parent_id)
    # Second Manager (your new field)
    second_manager_id = fields.Many2one(
        'hr.employee',
        string='Second Manager',
        help="Secondary reporting manager or additional supervisor"
    )

    # Reviewer field
    reviewer_id = fields.Many2one(
        'hr.employee',
        string='Reviewer',
        help="Person who reviews this employee's performance/KPIs"
    )

    # Evaluation Group
    evaluation_group_id = fields.Many2one(
        'evaluation.group',
        string='Evaluation Group',
        help="Evaluation group/category for this employee"
    )