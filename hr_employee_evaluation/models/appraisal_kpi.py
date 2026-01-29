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
        related='kra_id.template_id',
        store=True,
        readonly=True
    )

    @api.constrains('name', 'description', 'criteria', 'score')
    def _check_required_fields(self):
        for rec in self:
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

    @api.constrains('score', 'kra_id')
    def _check_total_score_limit(self):
        for rec in self:
            if not rec.template_id:
                continue

            total = sum(
                rec.template_id.kra_ids
                .mapped('kpi_ids')
                .mapped('score')
            )

            if total > rec.template_id.total_score:
                raise ValidationError(
                    "Total KPI score exceeds the allocated template score."
                )
