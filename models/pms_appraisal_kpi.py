from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PMSAppraisalKPI(models.Model):
    _name = 'pms.appraisal.kpi'
    _description = 'Employee Appraisal KPI'
    _order = 'kra_id, id'
    
    name = fields.Char(
        string='KPI',
        required=True,
        tracking=True
    )
    
    description = fields.Text(
        string='Description',
        required=True
    )
    
    criteria = fields.Text(
        string='Criteria',
        required=True
    )
    
    weightage = fields.Float(
        string='Weightage/Score',
        required=True,
        default=0.0,
        help='Original score from template'
    )
    
    kra_id = fields.Many2one(
        'pms.appraisal.kra',
        string='KRA',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    appraisal_id = fields.Many2one(
        'pms.appraisal',
        string='Appraisal',
        related='kra_id.appraisal_id',
        store=True,
        index=True
    )
    
    template_kpi_id = fields.Many2one(
        'appraisal.kpi',
        string='Original Template KPI',
        ondelete='restrict',
        help='Reference to the original template KPI'
    )
    
    # Planning phase fields
    is_selected = fields.Boolean(
        string='Selected',
        default=True,
        tracking=True,
        help='Employee can select/deselect KPIs during planning'
    )
    
    target = fields.Text(
        string='Target',
        tracking=True,
        help='Employee sets their target for this KPI'
    )
    
    planning_remarks = fields.Text(
        string='Employee Remarks',
        tracking=True,
        help='Employee adds remarks during planning'
    )
    
    # supervisor_planning_remarks = fields.Text(
    #     string='Supervisor Remarks',
    #     tracking=True,
    #     help='Supervisor can add remarks during planning review'
    # )
    
    # appraisal phase fields (will make soon)
    self_score = fields.Float(
        string='Self Score',
        tracking=True,
        help='Employee self-assessment score'
    )
    
    self_remarks = fields.Text(
        string='Self Remarks',
        tracking=True,
        help='Employee remarks during self-appraisal'
    )
    
    supervisor_score = fields.Float(
        string='Supervisor Score',
        tracking=True,
        help='Supervisor evaluation score'
    )
    
    supervisor_remarks = fields.Text(
        string='Supervisor Remarks',
        tracking=True,
        help='Supervisor remarks during evaluation'
    )

    secondary_supervisor_score = fields.Float(
        string='Secondary Supervisor Score',
        tracking=True,
        help='Secondary Supervisor evaluation score (if avialable)'
    )

    secondary_supervisor_score_remarks = fields.Text(
        string='Secondary Supervisor Remarks',  
        tracking=True,
        help='Secondary Supervisor remarks during evaluation (if avialable)'    
    )
    
    reviewer_score = fields.Float(
        string='Reviewer Score',
        tracking=True,
        help='Final reviewer score'
    )
    
    reviewer_remarks = fields.Text(
        string='Reviewer Remarks',
        tracking=True,
        help='Final reviewer remarks'
    )

    is_clone = fields.Boolean(string="Is Employee Clone", default=False) #check if the KPI record is created as a clone for employee editing
    
    # computed fields
    is_planning_complete = fields.Boolean(
        string='Planning Complete',
        compute='_compute_is_planning_complete',
        store=True
    )
    
    final_score = fields.Float(
        string='Final Score',
        compute='_compute_final_score',
        store=True,
        help='Computed based on phase: supervisor_score or reviewer_score if available'
    )
    
    @api.depends('is_selected', 'target', 'planning_remarks')
    def _compute_is_planning_complete(self):
        """Check if planning fields are filled for selected KPIs"""
        for record in self:
            if record.is_selected:
                record.is_planning_complete = bool(record.target and record.planning_remarks)
            else:
                record.is_planning_complete = False
    
    @api.depends('reviewer_score', 'supervisor_score')
    def _compute_final_score(self):
        """Final score is reviewer's score if available, else supervisor's"""
        for record in self:
            if record.reviewer_score:
                record.final_score = record.reviewer_score
            elif record.supervisor_score:
                record.final_score = record.supervisor_score
            else:
                record.final_score = 0.0
    
    # constraints
    @api.constrains('self_score', 'supervisor_score', 'reviewer_score')
    def _check_scores(self):
        """Ensure scores are non-negative"""
        for record in self:
            if record.self_score < 0 or record.supervisor_score < 0 or record.reviewer_score < 0:
                raise ValidationError('Scores cannot be negative.')
    
    @api.constrains('weightage')
    def _check_weightage(self):
        """Ensure weightage is non-negative"""
        for record in self:
            if record.weightage < 0:
                raise ValidationError('Weightage cannot be negative.')
    
    @api.onchange('is_selected')
    def _onchange_is_selected(self):
        """Clear planning fields when deselected"""
        if not self.is_selected:
            self.target = False
            self.planning_remarks = False