from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class CompetencyTemplate(models.Model):
    _name = 'competency.template'
    _description = 'Competency Template'

    name = fields.Char(string='Template Name', required=True)
    evaluation_group_id = fields.Many2one(
        'evaluation.group',
        string='Evaluation Group',
        help="Evaluation group this template is designed for"
    )
    total_points = fields.Float(string='Total Allowed Points', required=True, default=20.0)

    computed_total = fields.Float(
        string='Current Total Points',
        compute='_compute_current_total',
        store=True
    )

    # Status field for UI
    allocation_status = fields.Selection([
        ('under', 'Under Allocated'),
        ('perfect', 'Perfectly Allocated'),
        ('over', 'Over Allocated')
    ], string='Allocation Status', compute='_compute_allocation_status', store=True)

    line_ids = fields.One2many(
        'competency.template.line',
        'template_id',
        string='Competencies',
        copy=True
    )

    @api.depends('line_ids.points')
    def _compute_current_total(self):
        for template in self:
            template.computed_total = sum(line.points for line in template.line_ids)

    @api.depends('computed_total', 'total_points')
    def _compute_allocation_status(self):
        """Compute allocation status for UI display"""
        for template in self:
            if template.computed_total > template.total_points:
                template.allocation_status = 'over'
            elif template.computed_total == template.total_points:
                template.allocation_status = 'perfect'
            else:
                template.allocation_status = 'under'

    @api.constrains('line_ids', 'total_points')
    def _check_total_points(self):
        """Validate that sum doesn't exceed total allowed points - ONLY FOR ERRORS"""
        for template in self:
            total_line_points = sum(line.points for line in template.line_ids)

            # ERROR if exceeds total - block save
            if total_line_points > template.total_points:
                raise ValidationError(
                    f"❌ Total points of all competencies ({total_line_points}) exceeds "
                    f"the allowed total points ({template.total_points})!"
                )
            # Don't raise ValidationError for under or perfect - those are not errors

    @api.model
    def create(self, vals):
        record = super(CompetencyTemplate, self).create(vals)
        record._show_warning_if_under_total()
        return record

    def write(self, vals):
        result = super(CompetencyTemplate, self).write(vals)
        self._show_warning_if_under_total()
        return result

    def _show_warning_if_under_total(self):
        """Show warning if total points is less than allowed total"""
        for template in self:
            total_line_points = sum(line.points for line in template.line_ids)

            if total_line_points < template.total_points:
                remaining = template.total_points - total_line_points
                # This will show a warning but allow save
                return {
                    'warning': {
                        'title': 'Points Not Fully Allocated',
                        'message': f"⚠️ Total points allocated ({total_line_points}) is less than "
                                   f"the defined total ({template.total_points}). "
                                   f"Remaining: {remaining} points."
                    }
                }
            elif total_line_points == template.total_points:
                return {
                    'warning': {
                        'title': 'Perfect Allocation!',
                        'message': f"✅ Perfect! All {template.total_points} points are allocated."
                    }
                }
        return {}

    def action_check_allocation(self):
        """Button to manually check allocation"""
        self.ensure_one()
        total_line_points = sum(line.points for line in self.line_ids)

        if total_line_points > self.total_points:
            raise UserError(  # Changed from UserWarning
                f"❌ Over Allocated: {total_line_points}/{self.total_points} points"
            )

