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

    snapshot_employee_target = fields.Text(  
        string='Employee Submitted Target',
        readonly=True,
        help='See employees target field.'
    )

    snapshot_supervisor_target = fields.Text(  
        string='Supervisor Target',
        readonly=True,
        help='See supervisors edits to the employees target field.'
    )

    snapshot_secondary_target = fields.Text(  
        string='Secondary Supervisor Target',
        readonly=True,
        help='See supervisors edits to the employees target field.'
    )

    snapshot_employee_criteria = fields.Text(
        string='Employee Criteria Snapshot',
        readonly=True
    )

    snapshot_supervisor_criteria = fields.Text(
        string='Supervisor Criteria Snapshot',
        readonly=True
    )

    snapshot_secondary_criteria = fields.Text(
        string='Secondary Criteria Snapshot',
        readonly=True
    )
    
    # computed fields
    is_planning_complete = fields.Boolean(
        string='Planning Complete',
        compute='_compute_is_planning_complete',
        store=True
    )

    
    @api.depends('is_selected', 'target', 'planning_remarks')
    def _compute_is_planning_complete(self):
        """Check if planning fields are filled for selected KPIs"""
        for record in self:
            if record.is_selected:
                record.is_planning_complete = bool(record.target and record.planning_remarks)
            else:
                record.is_planning_complete = False

    # constraints
    @api.constrains('self_score', 'supervisor_score', 'secondary_supervisor_score', 'reviewer_score', 'weightage')
    def _check_scores(self):
        """Ensure scores are non-negative and do not exceed weightage"""
        for record in self:
            scores = [
                ('Self Score', record.self_score),
                ('Supervisor Score', record.supervisor_score),
                ('Secondary Supervisor Score', record.secondary_supervisor_score),
                ('Reviewer Score', record.reviewer_score)
            ]
            for score_name, score_val in scores:
                if score_val < 0:
                    raise ValidationError(f'{score_name} cannot be negative.')
                if score_val > record.weightage:
                    raise ValidationError(f'{score_name} ({score_val}) cannot exceed the KPI Weightage ({record.weightage}).')
    
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