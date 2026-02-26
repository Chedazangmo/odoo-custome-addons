from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AppraisalKPI(models.Model):
    _name = 'appraisal.kpi'
    _description = 'Key Performance Indicator'
    _order = 'kra_id, id'

    name = fields.Char(string='KPI', required=True, tracking=True)
    description = fields.Text(string='Description', required=True)
    score = fields.Float(string='Score', required=True, default=0.0, tracking=True)
    criteria = fields.Text(string='Criteria', required=True)

    kra_id = fields.Many2one(
        'appraisal.kra',
        string='KRA',
        required=True,
        ondelete='cascade',
        index=True
    )

    template_id = fields.Many2one(
        'appraisal.template',
        string='Template',
        related='kra_id.template_id',
        store=True,
        index=True
    )
    
    @api.constrains('name', 'description', 'criteria', 'score')
    def _check_required_fields(self):
        for rec in self:
            # Skip validation if we're in the middle of deletion
            if self.env.context.get('skip_kpi_validation'):
                continue
                
            if (
                not rec.name
                or not rec.description
                or not rec.criteria
                or rec.score is None
            ):
                raise ValidationError(
                    "All KPI fields must be filled. Empty values are not allowed."
                )

            if rec.score < 0:
                raise ValidationError("KPI score cannot be negative.")