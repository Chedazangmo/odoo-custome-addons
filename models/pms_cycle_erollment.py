from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PMSCycleEnrollment(models.Model):
    _name = 'pms.cycle.enrollment'
    _description = 'PMS Cycle Late Joiner Enrollment'
    _order = 'cycle_id, id'

    cycle_id = fields.Many2one(
        'pms.cycle', string='Cycle', required=True, ondelete='cascade', index=True
    )
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, ondelete='restrict',
        domain="[('active', '=', True), ('evaluation_group_id', '!=', False)]"
    )

    # Auto-detected from employee tags (category_ids). Any tag whose name
    # contains 'probation' (case-insensitive) marks this employee as probation.
    pms_type = fields.Selection([
        ('regular', 'Regular'),
        ('probation', 'Probation'),
    ], string='Type', compute='_compute_pms_type', store=True, readonly=False)

    state = fields.Selection([
        ('pending', 'Pending'),
        ('enrolled', 'Enrolled'),
    ], string='Status', default='pending', readonly=True)

    enrollment_date = fields.Date(string='Enrolled On', readonly=True)

    # Post-probation settings: applied when probation appraisal completes and the
    # employee is auto-enrolled into the parent cycle as a regular employee.
    post_probation_planning_duration = fields.Integer(
        string='Post-Probation Planning Duration (Days)', default=0
    )
    post_probation_resubmission_days = fields.Integer(
        string='Post-Probation Resubmission Days', default=5
    )

    # Links set once enrollment is processed
    appraisal_id = fields.Many2one('pms.appraisal', string='Appraisal', readonly=True)
    probation_cycle_id = fields.Many2one('pms.cycle', string='Probation Sub-Cycle', readonly=True)

    # Display helpers
    employee_evaluation_group_id = fields.Many2one(
        related='employee_id.evaluation_group_id', string='Evaluation Group', readonly=True
    )
    employee_supervisor_id = fields.Many2one(
        related='employee_id.parent_id', string='Supervisor', readonly=True
    )

    @api.depends('employee_id', 'employee_id.category_ids', 'employee_id.category_ids.name')
    def _compute_pms_type(self):
        for rec in self:
            if rec.employee_id:
                is_probation = any(
                    'probation' in (tag.name or '').lower()
                    for tag in rec.employee_id.category_ids
                )
                rec.pms_type = 'probation' if is_probation else 'regular'
            else:
                rec.pms_type = 'regular'

    @api.constrains('employee_id', 'cycle_id')
    def _check_unique_enrollment(self):
        for rec in self:
            existing = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('cycle_id', '=', rec.cycle_id.id),
                ('id', '!=', rec.id),
            ])
            if existing:
                raise ValidationError(
                    f'{rec.employee_id.name} is already in the enrollment list for this cycle.'
                )