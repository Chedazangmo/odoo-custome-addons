from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PerformancePlanCompetencyLine(models.Model):
    _name = 'performance.plan.competency.line'
    _description = 'Performance Plan Competency Line'
    _order = 'sequence, id'

    performance_plan_id = fields.Many2one(
        'performance.plan',
        required=True,
        ondelete='cascade'
    )

    sequence = fields.Integer(string='Sequence', default=10)
    competency_name = fields.Char(string='Competency Name', required=True)
    definition = fields.Text(string='Definition')
    max_points = fields.Float(string='Max Points', required=True)

    # Employee target fields
    employee_target = fields.Text(
        string='Employee Target',
        help="Specific target set by the employee"
    )

    plan_state = fields.Selection(
        related='performance_plan_id.state',
        string='Plan State',
        readonly=True,
        store=False  # Don't store in database, just compute on the fly
    )

    # Manager fields
    manager_notes = fields.Text(string="Manager Notes")
    reviewer_comments = fields.Text(string="Reviewer Comments")


