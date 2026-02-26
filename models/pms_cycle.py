from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta


class PMSCycle(models.Model):
    _name = 'pms.cycle'
    _description = 'Performance Management Cycle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence desc, id desc'
    
    name = fields.Char(
        string='Cycle Name',
        compute='_compute_name',
        store=True,
        readonly=True
    )
    sequence = fields.Char(
        string='Sequence',
        required=True,
        copy=False,
        readonly=True,
        default='New'
    )
    
    cycle_type = fields.Selection([
        ('annual', 'Annual (12 Months)'),
        ('semi_annual', 'Semi-Annual (6 Months)'),
        ('probation', 'Probation (3 Months)')
    ], string='Cycle Type', required=True, tracking=True, default='annual')
    
    start_date = fields.Date(
        string='Start Date',
        required=True,
        tracking=True
    )
    end_date = fields.Date(
        string='End Date',
        compute='_compute_end_date',
        store=True,
        readonly=False,
        tracking=True
    )
    
    planning_duration = fields.Integer(
        string='Planning Duration (Days)',
        required=True,
        default=30,
        tracking=True,
        help='Number of days from start date for planning'
    )
    planning_deadline = fields.Date(
        string='Planning Deadline',
        compute='_compute_planning_deadline',
        store=True,
        readonly=True,
        help='Deadline for employees to complete their planning'
    )
    
    resubmission_days = fields.Integer(
        string='Resubmission Days',
        default=5,
        help='Days allowed for resubmission after rejection'
    )
    
    apply_to = fields.Selection([
        ('all', 'All Employees'),
        ('selected', 'Selected Employees')
    ], string='Apply To', required=True, default='all', tracking=True)
    
    employee_ids = fields.Many2many(
        'hr.employee',
        'pms_cycle_employee_rel',
        'cycle_id',
        'employee_id',
        string='Selected Employees',
        domain="[('active', '=', True), ('evaluation_group_id', '!=', False)]"
    )
    
    appraisal_ids = fields.One2many(
        'pms.appraisal',
        'cycle_id',
        string='Employee Appraisals'
    )
    
    appraisal_count = fields.Integer( #number of employees for a particular cycle
        string='Employee Count',
        compute='_compute_appraisal_count',
        store=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('planning', 'Planning'),
        ('monitoring', 'Monitoring'),
        ('appraisal', 'Appraisal'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True, copy=False)
    
    active = fields.Boolean(string='Active', default=True)
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    
    @api.depends('sequence', 'cycle_type', 'start_date')
    def _compute_name(self):
        """Generate human-readable name from sequence and cycle info"""
        for record in self:
            if record.sequence and record.sequence != 'New':
                # cycle_type_label = dict(record._fields['cycle_type'].selection).get(record.cycle_type, '')
                if record.start_date:
                    record.name = f"{record.sequence}"
            else:
                record.name = 'New Cycle'
    
    @api.depends('cycle_type', 'start_date')
    def _compute_end_date(self):
        # Auto-compute end date based on cycle type
        for record in self:
            if not record.start_date:
                record.end_date = False
                continue
                
            if record.cycle_type == 'annual':
                record.end_date = record.start_date + relativedelta(years=1, days=-1)
            elif record.cycle_type == 'semi_annual':
                record.end_date = record.start_date + relativedelta(months=6, days=-1)
            elif record.cycle_type == 'probation':
                record.end_date = record.start_date + relativedelta(months=3, days=-1)
    
    @api.depends('start_date', 'planning_duration')
    def _compute_planning_deadline(self):
        # Compute planning deadline
        for record in self:
            if record.start_date and record.planning_duration:
                record.planning_deadline = record.start_date + relativedelta(days=record.planning_duration)
            else:
                record.planning_deadline = False
    
    @api.depends('appraisal_ids')
    def _compute_appraisal_count(self):
        for record in self:
            record.appraisal_count = len(record.appraisal_ids)
    
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date:
                if record.end_date <= record.start_date:
                    raise ValidationError('End date must be after start date.')
    
    @api.constrains('planning_duration')
    def _check_planning_duration(self):
        for record in self:
            if record.planning_duration <= 0:
                raise ValidationError('Planning duration must be greater than 0.')
    
    @api.constrains('employee_ids', 'apply_to')
    def _check_selected_employees(self):
        for record in self:
            if record.apply_to == 'selected' and not record.employee_ids:
                raise ValidationError('Please select at least one employee.')
    
    @api.model_create_multi
    def create(self, vals_list):
        # Generate sequence on create
        for vals in vals_list:
            if vals.get('sequence', 'New') == 'New':
                vals['sequence'] = self.env['ir.sequence'].next_by_code('pms.cycle') or 'New'
        return super().create(vals_list)
    
    def write(self, vals):
        # Prevent editing fields when not in draft
        protected_fields = ['cycle_type', 'start_date', 'apply_to', 'employee_ids']
        if any(field in vals for field in protected_fields):
            for record in self:
                if record.state != 'draft':
                    raise UserError('Cannot modify cycle configuration after activation.')
        return super().write(vals)
    
    def unlink(self):
        # Prevent deletion of non-draft cycles
        for record in self:
            if record.state != 'draft':
                raise UserError('Cannot delete activated cycles. Cancel them instead.')
        return super().unlink()
    
    def action_activate_cycle(self):
        # Activate the cycle 
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError('Only draft cycles can be activated.')
        
        # Validate dates
        if not self.start_date or not self.end_date:
            raise UserError('Start date and end date must be set.')
        
        # Get employees to create appraisals for
        if self.apply_to == 'all':
            employees = self.env['hr.employee'].search([
                ('active', '=', True),
                ('evaluation_group_id', '!=', False)
            ])
        else:
            employees = self.employee_ids
        
        if not employees:
            raise UserError('No employees found to create appraisals.')
        
        error_messages = []

        # Check Missing Supervisors
        # Filter employees who do not have a parent_id set
        employees_missing_supervisor = employees.filtered(lambda e: not e.parent_id)
        
        if employees_missing_supervisor:
            names = "\n".join([f"- {e.name}" for e in employees_missing_supervisor])
            error_messages.append(
                f"The following employees do not have a Supervisor assigned:\n{names}"
            )

        # Check Missing Templates for Evaluation Groups        
        employees_missing_group = employees.filtered(lambda e: not e.evaluation_group_id)
        
        employees_with_group = employees - employees_missing_group

        if employees_with_group:
            # Get all unique groups from these employees
            unique_groups = employees_with_group.mapped('evaluation_group_id')
            
            # Find which of these groups actually have an active template
            valid_templates = self.env['appraisal.template'].search([
                ('evaluation_group_id', 'in', unique_groups.ids),
                ('active', '=', True)
            ])
            valid_group_ids = valid_templates.mapped('evaluation_group_id.id')
            
            # Identify employees whose group is NOT in the valid list
            employees_missing_template = employees_with_group.filtered(
                lambda e: e.evaluation_group_id.id not in valid_group_ids
            )
        else:
            employees_missing_template = self.env['hr.employee']

        # Combine both template errors
        total_template_errors = employees_missing_group | employees_missing_template

        if total_template_errors:
            names = "\n".join([f"- {e.name} (Group: {e.evaluation_group_id.name or 'None'})" for e in total_template_errors])
            error_messages.append(
                f"The following employees do not have a valid Appraisal Template assigned:\n{names}\n"
                "Please ensure they have an Evaluation Group and that the Group has an active Template."
            )

        if error_messages:
            full_error = "\n\n".join(error_messages)
            raise UserError(f"Cannot activate cycle due to configuration errors:\n\n{full_error}")


        # Create appraisals for each employee (Validation Passed)
        self._create_employee_appraisals(employees)
        
        # Change state to planning
        self.write({'state': 'planning'})
        
        # Log activity
        self.message_post(
            body=f"Cycle activated. {len(employees)} employee appraisals created.",
            message_type='notification'
        )
        
        return True



    # create a copy of the tenplates for each employee based on their evaluation group 
    def _create_employee_appraisals(self, employees):
        AppraisalObj = self.env['pms.appraisal']
        
        created_count = 0
        skipped_count = 0
        created_appraisals = self.env['pms.appraisal']
        
        for employee in employees:
            # Check if employee has evaluation group
            if not employee.evaluation_group_id:
                skipped_count += 1
                continue
            
            # Find template for this evaluation group
            template = self.env['appraisal.template'].search([
                ('evaluation_group_id', '=', employee.evaluation_group_id.id),
                ('active', '=', True)
            ], limit=1)
            
            if not template:
                skipped_count += 1
                continue
            
            # Check if appraisal already exists for this employee in this cycle
            existing = AppraisalObj.search([
                ('cycle_id', '=', self.id),
                ('employee_id', '=', employee.id)
            ], limit=1)
            
            if existing:
                continue
            
            # Get supervisor (parent_id from hr.employee)
            supervisor = employee.parent_id
            reviewer = employee.reviewer_id
            
            # Create appraisal with deep copy of template
            appraisal_vals = {
                'cycle_id': self.id,
                'employee_id': employee.id,
                'template_id': template.id,
                'supervisor_id': supervisor.id if supervisor else False,
                'reviewer_id': reviewer.id if reviewer else False,
            }
            
            appraisal = AppraisalObj.create(appraisal_vals)
            
            # Clone template KRAs and KPIs
            appraisal._clone_template_structure()
            
            created_appraisals |= appraisal
            created_count += 1
        
        # Send notifications to employees
        if created_appraisals:
            self._notify_employees(created_appraisals)
        
        if skipped_count > 0:
            self.message_post(
                body=f"Note: {skipped_count} employees skipped (no evaluation group or template).",
                message_type='comment'
            )
        
        return created_count
    
    def _notify_employees(self, appraisals):
        # Notify employees that their performance plan is ready
        ActivityType = self.env['mail.activity.type']
        
        # Get or create activity type for PMS notifications
        activity_type = ActivityType.search([
            ('name', '=', 'Performance Plan'),
            ('category', '=', 'default')
        ], limit=1)
        
        if not activity_type:
            # Use default todo activity type
            activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        
        for appraisal in appraisals:
            # Only notify if employee has a user account
            if appraisal.employee_id.user_id:
                try:
                    # Create activity for employee
                    appraisal.activity_schedule(
                        activity_type_id=activity_type.id if activity_type else False,
                        summary=f'New Performance Plan - {self.name}',
                        note=f'Your performance plan for {self.name} is now active. '
                             f'Planning deadline: {self.planning_deadline.strftime("%B %d, %Y")}. '
                             f'Please review and submit your plan before the deadline.',
                        user_id=appraisal.employee_id.user_id.id,
                        date_deadline=self.planning_deadline
                    )
                    
                    # Also send an email notification
                    appraisal.message_post(
                        body=f"""Dear {appraisal.employee_id.name}, your performance plan for {self.name} is now active.""",
                        subject=f'Performance Plan Active - {self.name}',
                        message_type='notification',
                        partner_ids=[appraisal.employee_id.user_id.partner_id.id],
                        subtype_xmlid='mail.mt_comment'
                    )
                except Exception as e:
                    # Log error but don't fail the entire activation
                    self.message_post(
                        body=f"Warning: Could not notify {appraisal.employee_id.name}: {str(e)}",
                        message_type='comment'
                    )
    
    def action_move_to_monitoring(self):
        # Manually move cycle from planning to monitoring phase 
        self.ensure_one()

        if self.state != 'planning':
            raise UserError('Only cycles in the Planning phase can be moved to Monitoring.')

        self.write({'state': 'monitoring'})
        self.message_post(
            body="Moved to Monitoring phase. KPI plans are now locked for monitoring.",
            message_type='notification'
        )
        return True

    def action_move_to_appraisal(self):
        # Move cycle from monitoring to appraisal phase 
        self.ensure_one()

        if self.state != 'monitoring':
            raise UserError('Only cycles in the Monitoring phase can be moved to Appraisal.')

        submitted_appraisals = self.appraisal_ids.filtered(
            lambda a: a.state == 'pending_supervisor'
        )

        self.write({'state': 'appraisal'})
        self.message_post(
            body=f"Moved to Appraisal phase. {len(submitted_appraisals)} plans submitted.",
            message_type='notification'
        )
        return True
    
    def action_complete_cycle(self):
        """Mark cycle as completed"""
        self.ensure_one()
        
        if self.state not in ['planning', 'appraisal']:
            raise UserError('Cannot complete cycle from this state.')
        
        self.write({'state': 'completed'})
        
        return True
    
    def action_cancel_cycle(self):
        """Cancel the cycle"""
        self.ensure_one()
        
        if self.state == 'completed':
            raise UserError('Cannot cancel completed cycles.')
        
        self.write({'state': 'cancelled', 'active': False})
        
        return True
    
    def action_view_appraisals(self):
        self.ensure_one()
        
        return {
            'name': f'Appraisals - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pms.appraisal',
            'view_mode': 'kanban,list,form',
            'domain': [('cycle_id', '=', self.id)],
            'context': {'default_cycle_id': self.id}
        }