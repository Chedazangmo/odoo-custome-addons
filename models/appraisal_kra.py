from odoo import models, fields, api
from odoo.exceptions import ValidationError

class AppraisalKRA(models.Model):
    _name = 'appraisal.kra'
    _description = 'Key Result Area'
    _order = 'sequence, id'

    name = fields.Char(
        string='KRA Name', required=True, tracking=True
    )
    sequence = fields.Integer(
        string='Sequence', default=10, help='Order of KRA tabs'
    )
    template_id = fields.Many2one(
        'appraisal.template', 
        string='Template', 
        required=True, 
        ondelete='cascade', 
        index=True
    )
    
    # Add ondelete='cascade' here to ensure KPIs are deleted when KRA is deleted
    kpi_ids = fields.One2many(
        'appraisal.kpi', 
        'kra_id', 
        string='Key Performance Indicators',
        ondelete='cascade'  # This was missing!
    )
    
    kpi_count = fields.Integer(
        string='KPI Count', 
        compute='_compute_kpi_count', 
        store=True
    )
    
    # ✅ FIX: Added compute_sudo to prevent access issues during deletion
    total_score = fields.Float(
        string='Total Score', 
        compute='_compute_total_score', 
        store=True,
        compute_sudo=True,  # Run as superuser to avoid access issues
        help='Sum of all KPI scores in this KRA'
    )

    @api.depends('kpi_ids')
    def _compute_kpi_count(self):
        for record in self:
            record.kpi_count = len(record.kpi_ids)

    @api.depends('kpi_ids.score')
    def _compute_total_score(self):
        for record in self:
            record.total_score = sum(record.kpi_ids.mapped('score'))

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.name} ({record.kpi_count} KPIs)"
            result.append((record.id, name))
        return result
