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
        'pms.evaluation.group', string='Evaluation Group', required=True, ondelete='restrict', tracking=True
    )
    total_score = fields.Float(string='Total Score', required=True, default=100.0, tracking=True,
        help='Maximum total score for all KPIs combined'
    )
    competency_group = fields.Char(
        string='Competency Group',
        help='Will be linked to competency template in future'
    )
    kra_ids = fields.One2many(
        'appraisal.kra', 'template_id', string='Key Result Areas'
    )
    kra_count = fields.Integer(
        string='KRA Count', compute='_compute_kra_count', store=True
    )
    total_kpi_score = fields.Float(
        string='Total KPI Score', compute='_compute_total_kpi_score', store=True, help='Sum of all KPI scores across all KRAs'
    )
    active = fields.Boolean(
        string='Active', default=True
    )
    active_kra_id = fields.Integer(
        string='Active KRA ID', help='Stores the currently active KRA tab ID for delete operations'
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

    @api.constrains('total_score')
    def _check_total_score(self):
        for record in self:
            if record.total_score <= 0:
                raise ValidationError('Total Score must be greater than zero.')

    def action_add_kra(self):
        self.ensure_one()
        return {
            'name': 'Add Key Result Area',
            'type': 'ir.actions.act_window',
            'res_model': 'add.kra.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
            },
        }

    def action_delete_kra(self):
        """Delete the currently active KRA with confirmation"""
        self.ensure_one()
        
        if not self.kra_ids:
            raise ValidationError('No KRAs to delete.')
        
        active_kra_id = self.env.context.get('active_kra_id') or self.active_kra_id
        
        if not active_kra_id:
            raise ValidationError('No KRA is currently selected. Please select a KRA tab first.')
        
        kra = self.env['appraisal.kra'].browse(active_kra_id)
        
        if not kra.exists():
            raise ValidationError('The selected KRA no longer exists.')
        
        kra_name = kra.name
        kpi_count = kra.kpi_count
        
        kra.unlink()
        
        self.active_kra_id = False
        
        message = f'"{kra_name}" and its {kpi_count} KPI(s) have been deleted.'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'title': 'KRA Deleted',
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }

 