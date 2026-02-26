from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta


class PMSAppraisal(models.Model):
    _name = 'pms.appraisal'
    _description = 'Employee Performance Appraisal'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    
    # ==================== BASIC FIELDS ====================
    name = fields.Char(
        string='Appraisal Name',
        compute='_compute_name',
        store=True,
        readonly=True
    )
    
    cycle_id = fields.Many2one(
        'pms.cycle',
        string='Performance Cycle',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True
    )
    
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True
    )
    
    template_id = fields.Many2one(
        'appraisal.template',
        string='Template Used',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    
    supervisor_id = fields.Many2one(
        'hr.employee',
        string='Supervisor',
        tracking=True,
        help='Direct manager who will review this appraisal'
    )
    
    reviewer_id = fields.Many2one(
        'hr.employee',
        string='Reviewer',
        tracking=True,
        help='Final reviewer (optional)'
    )
    
    # ==================== RELATIONS ====================
    kra_ids = fields.One2many(
        'pms.appraisal.kra',
        'appraisal_id',
        string='Key Result Areas'
    )
    
    # ==================== STATE MACHINE ====================
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_supervisor', 'Pending Supervisor Review'),
        ('pending_reviewer', 'Pending Reviewer Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', required=True, tracking=True, copy=False)
    
    # ==================== DATES & TRACKING ====================
    submitted_date = fields.Datetime(
        string='Submitted Date',
        readonly=True,
        tracking=True
    )
    
    supervisor_review_date = fields.Datetime(
        string='Supervisor Review Date',
        readonly=True,
        tracking=True
    )
    
    reviewer_approval_date = fields.Datetime(
        string='Reviewer Approval Date',
        readonly=True,
        tracking=True
    )
    
    rejection_date = fields.Datetime(
        string='Rejection Date',
        readonly=True,
        tracking=True
    )
    
    resubmission_deadline = fields.Datetime(
        string='Resubmission Deadline',
        readonly=True,
        compute='_compute_resubmission_deadline',
        store=True,
        help='Deadline for resubmission after rejection'
    )
    
    # ==================== COMPUTED FIELDS ====================
    kra_count = fields.Integer(
        string='KRA Count',
        compute='_compute_kra_count',
        store=True
    )
    
    selected_kpi_count = fields.Integer(
        string='Selected KPIs',
        compute='_compute_kpi_counts',
        store=True
    )
    
    total_kpi_count = fields.Integer(
        string='Total KPIs',
        compute='_compute_kpi_counts',
        store=True
    )
    
    planning_progress = fields.Float(
        string='Planning Progress (%)',
        compute='_compute_planning_progress',
        store=True
    )
    
    is_editable = fields.Boolean(
        string='Is Editable',
        compute='_compute_is_editable'
    )
    
    is_past_planning_deadline = fields.Boolean(
        string='Past Planning Deadline',
        compute='_compute_is_past_planning_deadline'
    )
    
    active = fields.Boolean(string='Active', default=True)
    
    company_id = fields.Many2one(
        'res.company',
        related='employee_id.company_id',
        store=True,
        readonly=True
    )
    
    # ==================== COMPUTES ====================
    @api.depends('employee_id', 'cycle_id')
    def _compute_name(self):
        """Generate name from employee and cycle"""
        for record in self:
            if record.employee_id and record.cycle_id:
                record.name = f"{record.employee_id.name} - {record.cycle_id.name}"
            else:
                record.name = 'New Appraisal'
    
    @api.depends('kra_ids')
    def _compute_kra_count(self):
        for record in self:
            record.kra_count = len(record.kra_ids)
    
    @api.depends('kra_ids.kpi_ids', 'kra_ids.kpi_ids.is_selected')
    def _compute_kpi_counts(self):
        for record in self:
            all_kpis = record.kra_ids.mapped('kpi_ids')
            record.total_kpi_count = len(all_kpis)
            record.selected_kpi_count = len(all_kpis.filtered(lambda k: k.is_selected))
    
    @api.depends('kra_ids.kpi_ids', 'kra_ids.kpi_ids.is_selected', 
                 'kra_ids.kpi_ids.target', 'kra_ids.kpi_ids.planning_remarks')
    def _compute_planning_progress(self):
        """Calculate planning completion percentage"""
        for record in self:
            all_kpis = record.kra_ids.mapped('kpi_ids')
            selected_kpis = all_kpis.filtered(lambda k: k.is_selected)
            
            if not selected_kpis:
                record.planning_progress = 0.0
                continue
            
            completed = 0
            for kpi in selected_kpis:
                # Check if target and remarks are filled
                if kpi.target and kpi.planning_remarks:
                    completed += 1
            
            record.planning_progress = (completed / len(selected_kpis)) * 100 if selected_kpis else 0.0
    
    @api.depends('state', 'cycle_id.state', 'cycle_id.planning_deadline', 
                 'rejection_date', 'resubmission_deadline')
    def _compute_is_editable(self):
        """Determine if employee can edit this appraisal"""
        today = fields.Datetime.now()
        
        for record in self:
            # Cannot edit if approved
            if record.state == 'approved':
                record.is_editable = False
                continue
            
            if record.cycle_id.planning_deadline and record.cycle_id.planning_deadline < fields.Date.today():
                # If rejected, check resubmission deadline
                if record.state == 'rejected' and record.resubmission_deadline:
                    record.is_editable = today <= record.resubmission_deadline
                else:
                    record.is_editable = False
                continue
            
            if record.state in ['draft', 'rejected']:
                if record.state == 'rejected' and record.resubmission_deadline:
                    record.is_editable = today <= record.resubmission_deadline
                else:
                    record.is_editable = True
            else:
                record.is_editable = False
    
    @api.depends('cycle_id.planning_deadline')
    def _compute_is_past_planning_deadline(self):
        today = fields.Date.today()
        for record in self:
            record.is_past_planning_deadline = (
                record.cycle_id.planning_deadline and 
                record.cycle_id.planning_deadline < today
            )
    
    @api.depends('rejection_date', 'cycle_id.resubmission_days')
    def _compute_resubmission_deadline(self):
        """Calculate deadline for resubmission after rejection"""
        for record in self:
            if record.rejection_date and record.cycle_id.resubmission_days:
                record.resubmission_deadline = record.rejection_date + timedelta(
                    days=record.cycle_id.resubmission_days
                )
            else:
                record.resubmission_deadline = False
    
    @api.constrains('employee_id', 'cycle_id')
    def _check_unique_employee_cycle(self):
        """One appraisal per employee per cycle"""
        for record in self:
            existing = self.search([
                ('employee_id', '=', record.employee_id.id),
                ('cycle_id', '=', record.cycle_id.id),
                ('id', '!=', record.id)
            ])
            if existing:
                raise ValidationError(
                    f'An appraisal for {record.employee_id.name} in cycle {record.cycle_id.name} already exists.'
                )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Set supervisor from employee on create"""
        for vals in vals_list:
            if 'employee_id' in vals and 'supervisor_id' not in vals:
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                if employee.parent_id:
                    vals['supervisor_id'] = employee.parent_id.id
        
        return super().create(vals_list)
    
    def write(self, vals):
        """Prevent editing when locked"""
        if not self.env.context.get('skip_edit_check'):
            for record in self:
                if not record.is_editable and any(
                    k in vals for k in ['kra_ids', 'state']
                ):
                    if vals.get('state') not in ['pending_supervisor', 'pending_reviewer', 'approved', 'rejected']:
                        raise UserError('This appraisal is locked and cannot be edited.')
        
        return super().write(vals)
    
    # Copy template
    def _clone_template_structure(self):
        """Clone KRAs and KPIs from template"""
        self.ensure_one()
        
        if not self.template_id:
            raise UserError('Template is required to clone structure.')
        
        AppraisalKRAObj = self.env['pms.appraisal.kra']
        AppraisalKPIObj = self.env['pms.appraisal.kpi']
        
        # Clone each KRA
        for template_kra in self.template_id.kra_ids:
            appraisal_kra_vals = {
                'appraisal_id': self.id,
                'name': template_kra.name,
                'sequence': template_kra.sequence,
                'template_kra_id': template_kra.id,
            }
            
            appraisal_kra = AppraisalKRAObj.create(appraisal_kra_vals)
            
            # Clone each KPI for this KRA
            for template_kpi in template_kra.kpi_ids:
                appraisal_kpi_vals = {
                    'kra_id': appraisal_kra.id,
                    'name': template_kpi.name,
                    'description': template_kpi.description,
                    'criteria': template_kpi.criteria,
                    'weightage': template_kpi.score,  # Original score becomes weightage
                    'template_kpi_id': template_kpi.id,
                    'is_selected': True,  # Selected by default
                }
                
                AppraisalKPIObj.create(appraisal_kpi_vals)
        
        return True
    
    def action_submit_for_review(self):
        """Employee submits plan for supervisor review"""
        self.ensure_one()
        
        if self.state not in ['draft', 'rejected']:
            raise UserError('Only draft or rejected appraisals can be submitted.')
        
        if not self.is_editable:
            raise UserError('Cannot submit: appraisal is locked or past deadline.')
        
        # Validate: at least one KPI must be selected
        if self.selected_kpi_count == 0:
            raise UserError('Please select at least one KPI before submitting.')
        
        # Validate: all selected KPIs must have target and remarks
        selected_kpis = self.kra_ids.mapped('kpi_ids').filtered(lambda k: k.is_selected)
        incomplete_kpis = selected_kpis.filtered(lambda k: not k.target or not k.planning_remarks)
        
        if incomplete_kpis:
            raise UserError('All selected KPIs must have Target and Remarks filled.')
        
        self.write({
            'state': 'pending_supervisor',
            'submitted_date': fields.Datetime.now()
        })
        
        # Notify supervisor
        if self.supervisor_id and self.supervisor_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.supervisor_id.user_id.id,
                summary=f'Review appraisal for {self.employee_id.name}'
            )
        
        self.message_post(
            body=f"Plan submitted by {self.employee_id.name} for supervisor review.",
            message_type='notification'
        )
        
        return True
    
    def action_supervisor_approve(self):
        """Supervisor approves the planning"""
        self.ensure_one()
        
        if self.state != 'pending_supervisor':
            raise UserError('Only plans pending supervisor review can be approved.')
        
        # Check if reviewer exists
        if self.reviewer_id:
            new_state = 'pending_reviewer'
            # Notify reviewer
            if self.reviewer_id.user_id:
                self.activity_schedule(
                    activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                    user_id=self.reviewer_id.user_id.id,
                    summary=f'Review appraisal for {self.employee_id.name}'
                )
        else:
            new_state = 'approved'
        
        self.write({
            'state': new_state,
            'supervisor_review_date': fields.Datetime.now()
        })
        
        self.message_post(
            body=f"Planning approved by supervisor {self.supervisor_id.name}.",
            message_type='notification'
        )
        
        return True
    
    def action_supervisor_reject(self):
        """Supervisor rejects the planning"""
        self.ensure_one()
        
        if self.state != 'pending_supervisor':
            raise UserError('Only plans pending supervisor review can be rejected.')
        
        self.write({
            'state': 'rejected',
            'rejection_date': fields.Datetime.now()
        })
        
        # Notify employee
        if self.employee_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.employee_id.user_id.id,
                summary=f'Your appraisal has been rejected. Please revise and resubmit.'
            )
        
        self.message_post(
            body=f"Planning rejected by supervisor {self.supervisor_id.name}. Employee has {self.cycle_id.resubmission_days} days to resubmit.",
            message_type='notification'
        )
        
        return True
    
    def action_reviewer_approve(self):
        """Reviewer gives final approval"""
        self.ensure_one()
        
        if self.state != 'pending_reviewer':
            raise UserError('Only plans pending reviewer approval can be approved.')
        
        self.write({
            'state': 'approved',
            'reviewer_approval_date': fields.Datetime.now()
        })
        
        self.message_post(
            body=f"Planning approved by reviewer {self.reviewer_id.name}. Planning phase complete.",
            message_type='notification'
        )
        
        return True
    
    def action_reviewer_reject(self):
        """Reviewer rejects back to employee"""
        self.ensure_one()
        
        if self.state != 'pending_reviewer':
            raise UserError('Only plans pending reviewer approval can be rejected.')
        
        self.write({
            'state': 'rejected',
            'rejection_date': fields.Datetime.now()
        })
        
        if self.employee_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.employee_id.user_id.id,
                summary=f'Your appraisal has been rejected by reviewer. Please revise and resubmit.'
            )
        
        self.message_post(
            body=f"Planning rejected by reviewer {self.reviewer_id.name}. Employee has {self.cycle_id.resubmission_days} days to resubmit.",
            message_type='notification'
        )
        
        return True