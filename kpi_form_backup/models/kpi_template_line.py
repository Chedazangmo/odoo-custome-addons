from odoo import models, fields, api
from odoo.exceptions import ValidationError


class KpiTemplateLine(models.Model):
    _name = 'kpi.template.line'
    _description = 'KPI Template Line'

    template_id = fields.Many2one(
        'kpi.template',
        string='Template',
        required=True,
        ondelete='cascade'
    )

    kpi_name = fields.Char(string='KPI Name', required=True)
    definition = fields.Text(string='KPI Definition')
    score = fields.Float(string='Score', required=True)
    evaluation_criteria = fields.Text(string='Evaluation Criteria')

    @api.constrains('score')
    def _check_score_positive(self):
        """Validate that score is positive"""
        for line in self:
            if line.score <= 0:
                raise ValidationError("Score must be greater than 0!")

    @api.constrains('score', 'template_id')
    def _check_total_score_limit(self):
        """Check if adding/updating this line exceeds template total score"""
        for line in self:
            if line.template_id:
                # Get all other lines (excluding current one if updating)
                other_lines = line.template_id.line_ids - line
                other_lines_total = sum(other_line.score for other_line in other_lines)

                # Calculate new total with this line
                new_total = other_lines_total + line.score

                # ERROR if exceeds template total
                if new_total > line.template_id.total_score:
                    exceed_amount = new_total - line.template_id.total_score
                    raise ValidationError(
                        f"Cannot add/update this KPI!\n"
                        f"Current total (without this line): {other_lines_total}\n"
                        f"This KPI score: {line.score}\n"
                        f"New total would be: {new_total}\n"
                        f"Template limit: {line.template_id.total_score}\n"
                        f"❌ Exceeds by: {exceed_amount} points"
                    )

    # Add this method to trigger template recomputation
    @api.model
    def create(self, vals):
        record = super(KpiTemplateLine, self).create(vals)
        if record.template_id:
            record.template_id._compute_current_total()
        return record

    def write(self, vals):
        result = super(KpiTemplateLine, self).write(vals)
        for record in self:
            if record.template_id:
                record.template_id._compute_current_total()
        return result

    def unlink(self):
        templates_to_update = self.mapped('template_id')
        result = super(KpiTemplateLine, self).unlink()
        for template in templates_to_update:
            template._compute_current_total()
        return result