from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PerformancePlanKpiLine(models.Model):
    _name = 'performance.plan.kpi.line'
    _description = 'Performance Plan KPI Line'
    _order = 'sequence, id'

    performance_plan_id = fields.Many2one(
        'performance.plan',
        required=True,
        ondelete='cascade'
    )

    sequence = fields.Integer(string='Sequence', default=10)
    kpi_name = fields.Char(string='KPI Name', required=True)
    definition = fields.Text(
        string='Definition',
        default=lambda self: self._get_default_definition()
    )
    max_score = fields.Float(string='Max Score', required=True)

    # Employee target fields
    employee_target = fields.Text(
        string='Employee Target',
        help="Specific target set by the employee"
    )
    evaluation_criteria = fields.Text(string='Evaluation Criteria',required=True)

    plan_state = fields.Selection(
        related='performance_plan_id.state',
        string='Plan State',
        readonly=True,
        store=False  # Don't store in database, just compute on the fly
    )
    # Manager fields
    manager_notes = fields.Text(string="Manager Notes")
    reviewer_comments = fields.Text(string="Reviewer Comments")


    def _get_default_definition(self):
        """Get default definition if empty"""
        if self.kpi_name:
            return f"Target for: {self.kpi_name}"
        return "Please define your performance target"






