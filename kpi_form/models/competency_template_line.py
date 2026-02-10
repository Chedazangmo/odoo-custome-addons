from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CompetencyTemplateLine(models.Model):
    _name = 'competency.template.line'
    _description = 'Competency Template Line'

    template_id = fields.Many2one(
        'competency.template',
        string='Template',
        required=True,
        ondelete='cascade'
    )

    competency_name = fields.Char(string='Competency Name', required=True)
    competency_definition = fields.Text(string='Competency Definition', required=True)
    points = fields.Float(string='Points', required=True)

    @api.constrains('points')
    def _check_points_positive(self):
        """Validate that points are positive"""
        for line in self:
            if line.points <= 0:  # Changed from < 0 to <= 0
                raise ValidationError("Points must be greater than 0!")

    @api.constrains('points', 'template_id')
    def _check_total_points_limit(self):
        """Validate that adding/updating this line doesn't exceed template's total points"""
        for line in self:
            if line.template_id:
                # Get all other lines (excluding current one if updating)
                other_lines = line.template_id.line_ids - line
                other_lines_total = sum(other_line.points for other_line in other_lines)

                # Calculate new total with this line
                new_total = other_lines_total + line.points

                if new_total > line.template_id.total_points:
                    raise ValidationError(
                        f"Cannot add/update this competency!\n\n"
                        f"Current total (without this line): {other_lines_total}\n"
                        f"This competency points: {line.points}\n"
                        f"New total would be: {new_total}\n"
                        f"But template limit is: {line.template_id.total_points}\n\n"
                        f"You would exceed by: {new_total - line.template_id.total_points} points"
                    )

