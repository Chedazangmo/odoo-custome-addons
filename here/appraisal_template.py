from odoo import models, fields, api
from odoo.exceptions import ValidationError

class AppraisalTemplate(models.Model):
    _name = 'appraisal.template'
    _description = 'Appraisal Template'
    _order = 'name'

    name = fields.Char(
        string='Template Name', required=True, tracking=True
    )
    evaluation_group_id = fields.Many2one(
        'pms.evaluation.group', 
        string='Evaluation Group', 
        required=True, 
        ondelete='restrict', 
        tracking=True
    )
    competency_group = fields.Char(
        string='Competency Group',
        help='Will be linked to competency template in future'
    )
    kra_ids = fields.One2many(
        'appraisal.kra', 
        'template_id', 
        string='Key Result Areas'
    )
    
    kra_count = fields.Integer(
        string='KRA Count', 
        compute='_compute_kra_count', 
        store=True
    )
    
    # compute_sudo: prevent issues during nested deletion
    total_kpi_score = fields.Float(
        string='Total KPI Score', 
        compute='_compute_total_kpi_score', 
        store=True,
        compute_sudo=True,  # Run as superuser
        help='Sum of all KPI scores across all KRAs'
    )
    
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('locked', 'Locked (In Use)'),
        ],
        default='draft',
        tracking=True,
        required=True
    )
    active = fields.Boolean(
        string='Active', default=True
    )

    _sql_constraints = [
        ('unique_evaluation_group', 'UNIQUE(evaluation_group_id)', 
         'Only one template can be created per employee_evaluation!')
    ]

    @api.depends('kra_ids')
    def _compute_kra_count(self):
        for record in self:
            record.kra_count = len(record.kra_ids)

    @api.depends('kra_ids.kpi_ids.score')
    def _compute_total_kpi_score(self):
        for record in self:
            total = sum(
                kpi.score 
                for kra in record.kra_ids 
                for kpi in kra.kpi_ids
            )
            record.total_kpi_score = total