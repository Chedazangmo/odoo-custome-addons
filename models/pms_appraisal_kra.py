from odoo import models, fields, api


class PMSAppraisalKRA(models.Model):
    _name = 'pms.appraisal.kra'
    _description = 'Employee Appraisal KRA'
    _order = 'sequence, id'
    
    name = fields.Char(
        string='KRA Name',
        required=True,
        tracking=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of KRA tabs'
    )
    
    appraisal_id = fields.Many2one(
        'pms.appraisal',
        string='Appraisal',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    template_kra_id = fields.Many2one(
        'appraisal.kra',
        string='Original Template KRA',
        ondelete='restrict',
        help='Reference to the original template KRA'
    )
    
    kpi_ids = fields.One2many(
        'pms.appraisal.kpi',
        'kra_id',
        string='Key Performance Indicators',
        ondelete='cascade'
    )
    
    kpi_count = fields.Integer(
        string='Total KPIs',
        compute='_compute_kpi_count',
        store=True
    )
    
    selected_kpi_count = fields.Integer(
        string='Selected KPIs',
        compute='_compute_selected_kpi_count',
        store=True
    )
    
    total_weightage = fields.Float(
        string='Total Weightage',
        compute='_compute_total_weightage',
        store=True,
        compute_sudo=True,
        help='Sum of all selected KPI weightages in this KRA'
    )
    
    @api.depends('kpi_ids')
    def _compute_kpi_count(self):
        for record in self:
            record.kpi_count = len(record.kpi_ids)
    
    @api.depends('kpi_ids', 'kpi_ids.is_selected')
    def _compute_selected_kpi_count(self):
        for record in self:
            record.selected_kpi_count = len(record.kpi_ids.filtered(lambda k: k.is_selected))
    
    @api.depends('kpi_ids.weightage', 'kpi_ids.is_selected')
    def _compute_total_weightage(self):
        for record in self:
            selected_kpis = record.kpi_ids.filtered(lambda k: k.is_selected)
            record.total_weightage = sum(selected_kpis.mapped('weightage'))
    
    def name_get(self):
        result = []
        for record in self:
            name = f"{record.name} ({record.selected_kpi_count}/{record.kpi_count} KPIs)"
            result.append((record.id, name))
        return result