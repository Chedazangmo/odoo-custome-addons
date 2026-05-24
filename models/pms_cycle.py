from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta
import re


class PMSCycle(models.Model):
    _name = 'pms.cycle'
    _description = 'Performance Management Cycle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence desc, id desc'
    
    name = fields.Char(
        string='Cycle Name',
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
        default=15,
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
        help='Days allowed for resubmission after HR sets plan to draft'
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

    final_score_selection = fields.Selection([
        ('reviewer', 'Reviewer Score'), #takes reviewer score as the final one
        ('average', 'Average') #takes the average of sup + sec sup (if exists) + rev
    ], string='Final Score', required=True, default='reviewer', tracking=True,
       help="Determines how the final appraisal score is calculated for employees in this cycle.")
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('planning', 'Planning'),
        ('monitoring', 'Monitoring'),
        ('appraisal', 'Appraisal'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True, copy=False)
    
    active = fields.Boolean(string='Active', default=True) #not the state of the cycle but whether the record is active or archived
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    # To check employees for different cycles

    is_manager_in_cycle = fields.Boolean(
        string='Is Manager',
        compute='_compute_is_manager_in_cycle',
        search='_search_is_manager_in_cycle'
    )

    def _compute_is_manager_in_cycle(self):
        is_hr = self.env.user.has_group('hr_employee_evaluation.group_pms_hr_manager')
        appraisals = self.env['pms.appraisal'].search([
            ('cycle_id', 'in', self.ids),
            '|', '|',
            ('supervisor_id.user_id', '=', self.env.uid),
            ('secondary_supervisor_id.user_id', '=', self.env.uid),
            ('reviewer_id.user_id', '=', self.env.uid),
        ])
        involved_cycle_ids = set(appraisals.mapped('cycle_id').ids)
        
        for cycle in self:
            if is_hr:
                cycle.is_manager_in_cycle = True
            else:
                cycle.is_manager_in_cycle = cycle.id in involved_cycle_ids

    def _search_is_manager_in_cycle(self, operator, value):
        if self.env.user.has_group('hr_employee_evaluation.group_pms_hr_manager'):
            return [('id', '!=', False)]  # God Mode for. All cycles to appear
            
        appraisals = self.env['pms.appraisal'].search([
            '|', '|',
            ('supervisor_id.user_id', '=', self.env.uid),
            ('secondary_supervisor_id.user_id', '=', self.env.uid),
            ('reviewer_id.user_id', '=', self.env.uid),
        ])
        
        if not appraisals:
            return [('id', '=', -1)]  # Forces absolute zero records (No ghost cycles)
            
        return [('id', 'in', appraisals.mapped('cycle_id').ids)]

    def action_open_subordinate_plans(self):
        self.ensure_one()
        is_hr = self.env.user.has_group('hr_employee_evaluation.group_pms_hr_manager')
        domain = [('cycle_id', '=', self.id)]
        
        if not is_hr:
            domain.extend([
                '|', '|',
                ('supervisor_id.user_id', '=', self.env.uid),
                ('secondary_supervisor_id.user_id', '=', self.env.uid),
                ('reviewer_id.user_id', '=', self.env.uid),
            ])

        return {
            'name': f'Employee Plans — {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pms.appraisal',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('hr_employee_evaluation.view_employee_plans_all_list').id, 'list'),
                (self.env.ref('hr_employee_evaluation.view_employee_plans_supervisor_form').id, 'form'),
            ],
            'domain': domain,
            'context': {'create': False, 'delete': False},
        }

    def action_open_subordinate_appraisals(self):
        self.ensure_one()
        is_hr = self.env.user.has_group('hr_employee_evaluation.group_pms_hr_manager')
        domain = [
            ('cycle_id', '=', self.id),
            ('state', 'in', [
                'appraisal_draft', 'appraisal_pending_supervisor',
                'appraisal_pending_secondary_supervisor',
                'appraisal_pending_reviewer', 'appraisal_approved',
            ])
        ]
        
        if not is_hr:
            domain.extend([
                '|', '|',
                ('supervisor_id.user_id', '=', self.env.uid),
                ('secondary_supervisor_id.user_id', '=', self.env.uid),
                ('reviewer_id.user_id', '=', self.env.uid),
            ])

        return {
            'name': f'Employee Appraisals — {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pms.appraisal',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('hr_employee_evaluation.view_employee_appraisals_all_list').id, 'list'),
                (self.env.ref('hr_employee_evaluation.view_employee_appraisals_supervisor_form').id, 'form'),
            ],
            'domain': domain,
            'context': {'create': False, 'delete': False},
        }

    
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
    
    
    # @api.model_create_multi
    # def create(self, vals_list):
    #     for vals in vals_list:
    #         if vals.get('sequence', 'New') == 'New':
    #             vals['sequence'] = self.env['ir.sequence'].next_by_code('pms.cycle') or 'New'
            
    #         if vals.get('name'):
    #             if vals.get('start_date'):
    #                 cycle_year = vals['start_date'][:4]
    #             else:
    #                 cycle_year = fields.Date.today().year
                
    #             vals['name'] = f"{vals['name']} - {cycle_year}"
                
    #     return super().create(vals_list)
    
    @api.onchange('name', 'start_date')
    def _onchange_name_date(self):
        for record in self:
            if record.name and record.start_date:
                year = str(record.start_date.year)
                base_name = re.sub(r' - \d{4}$', '', record.name).strip()
                record.name = f"{base_name} - {year}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sequence', 'New') == 'New':
                vals['sequence'] = self.env['ir.sequence'].next_by_code('pms.cycle') or 'New'
            
            if vals.get('name') and vals.get('start_date'):
                year = str(vals['start_date'])[:4]
                base_name = re.sub(r' - \d{4}$', '', vals['name']).strip()
                vals['name'] = f"{base_name} - {year}"
                
        return super().create(vals_list)
    
    def write(self, vals):
        if not self.env.context.get('skip_cycle_edit_check'):
            protected_fields = [
                'cycle_type', 'start_date', 'apply_to', 
                'employee_ids', 'final_score_selection' 
            ]
            if any(field in vals for field in protected_fields):
                for record in self:
                    if record.state != 'draft':
                        raise UserError('Cannot modify cycle configuration after activation.')
        return super().write(vals)
    
    # def write(self, vals):
    #     # Prevent editing fields when not in draft
    #     protected_fields = [
    #         'cycle_type', 'start_date', 'apply_to', 
    #         'employee_ids', 'final_score_selection' 
    #     ]
    #     if any(field in vals for field in protected_fields):
    #         for record in self:
    #             if record.state != 'draft':
    #                 raise UserError('Cannot modify cycle configuration after activation.')
    #     return super().write(vals)
    
    def unlink(self):
        # Prevent deletion of non-draft cycles
        for record in self:
            if record.state != 'draft':
                raise UserError('Cannot delete activated cycles. Cancel them instead.')
        return super().unlink()
    
    def action_activate_cycle(self):
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError('Only draft cycles can be activated.')
            
        # ─── Prevent multiple active cycles of the same category ───
        active_states = ['planning', 'monitoring', 'appraisal']
        if self.cycle_type in ['annual', 'semi_annual']:
            # Check for active Regular cycles
            if self.search_count([
                ('state', 'in', active_states), 
                ('cycle_type', 'in', ['annual', 'semi_annual']), 
                ('id', '!=', self.id)
            ]):
                raise UserError('Cannot activate: A Regular cycle (Annual or Semi-Annual) is already active. Please complete or cancel it first.')
                
        elif self.cycle_type == 'probation':
            # Check for active Probation cycles
            if self.search_count([
                ('state', 'in', active_states), 
                ('cycle_type', '=', 'probation'), 
                ('id', '!=', self.id)
            ]):
                raise UserError('Cannot activate: A Probation cycle is already active. Please complete or cancel it first.')
        # ──────────────────────────────────────────────────────────────────
        
        if not self.start_date or not self.end_date:
            raise UserError('Start date and end date must be set.')
        
        if self.apply_to == 'all':
            # Base domain for all cycles
            domain = [
                ('active', '=', True),
                ('evaluation_group_id', '!=', False)
            ]
            
            # Filter by Employee Tags based on Cycle Type
            if self.cycle_type in ['annual', 'semi_annual']:
                domain.append(('category_ids.name', 'ilike', 'Regular'))
            elif self.cycle_type == 'probation':
                domain.append(('category_ids.name', 'ilike', 'Probation'))

            employees = self.env['hr.employee'].search(domain)
            
            if not employees:
                raise UserError(
                    f"No employees found with an Evaluation Group and the required tag for this cycle type. "
                    f"Please ensure your employees have the correct tags ('Regular' or 'Probation')."
                )
                
            # Force the employee_ids list to populate so we can view them in the UI!
            self.write({'employee_ids': [(6, 0, employees.ids)]})
        else:
            employees = self.employee_ids
            if not employees:
                raise UserError('No employees selected to create appraisals.')
        
        self._validate_employees(employees)
        self._create_employee_appraisals(employees, is_late=False)
        
        self.write({'state': 'planning'})
        
        self.message_post(
            body=f"Cycle activated. {len(employees)} employee appraisals created.",
            message_type='notification'
        )
        return True
    
    # def action_activate_cycle(self):
    #     self.ensure_one()
        
    #     if self.state != 'draft':
    #         raise UserError('Only draft cycles can be activated.')
        
    #     if not self.start_date or not self.end_date:
    #         raise UserError('Start date and end date must be set.')
        
    #     if self.apply_to == 'all':
    #         employees = self.env['hr.employee'].search([
    #             ('active', '=', True),
    #             ('evaluation_group_id', '!=', False)
    #         ])
    #         # Force the employee_ids list to populate so we can view them in the UI!
    #         self.write({'employee_ids': [(6, 0, employees.ids)]})
    #     else:
    #         employees = self.employee_ids
        
    #     if not employees:
    #         raise UserError('No employees found to create appraisals.')
        
    #     self._validate_employees(employees)
    #     self._create_employee_appraisals(employees, is_late=False)
        
    #     self.write({'state': 'planning'})
        
    #     self.message_post(
    #         body=f"Cycle activated. {len(employees)} employee appraisals created.",
    #         message_type='notification'
    #     )
    #     return True

    def _validate_employees(self, employees):
        """Reusable validation for activating cycles and adding late employees"""
        error_messages = []

        # ─── Tag Validation for Manual Selection ───
        invalid_for_regular = self.env['hr.employee']
        invalid_for_probation = self.env['hr.employee']
        
        for e in employees:
            # Extract all tags for the employee and convert to lowercase for safe checking
            tags = [tag.lower() for tag in e.category_ids.mapped('name') if tag]
            has_probation = any('probation' in t for t in tags)
            
            if self.cycle_type in ['annual', 'semi_annual']:
                # Regular cycles can have any tag EXCEPT Probation
                if has_probation:
                    invalid_for_regular |= e
            elif self.cycle_type == 'probation':
                # Probation cycles MUST have the Probation tag
                if not has_probation:
                    invalid_for_probation |= e

        if invalid_for_regular:
            names = "\n".join([f"- {e.name}" for e in invalid_for_regular])
            error_messages.append(
                f"Regular cycles CANNOT include employees on Probation. "
                f"Please remove these employees or update their tags:\n{names}\n"
            )

        if invalid_for_probation:
            names = "\n".join([f"- {e.name}" for e in invalid_for_probation])
            error_messages.append(
                f"Probation cycles can ONLY include employees with the 'Probation' tag. "
                f"Please remove these employees or update their tags:\n{names}\n"
            )
        # ───────────────────────────────────────────

        active_appraisals = self.env['pms.appraisal'].search([
            ('employee_id', 'in', employees.ids),
            ('cycle_id', '!=', self.id),
            ('cycle_id.state', 'not in', ['draft', 'completed', 'cancelled'])
        ])

        if active_appraisals:
            busy_employee_names = list(set(active_appraisals.mapped('employee_id.name')))
            names = "\n".join([f"- {name}" for name in busy_employee_names])
            error_messages.append(f"The following employees already have an active cycle:\n{names}\n")

        employees_missing_supervisor = employees.filtered(lambda e: not e.parent_id)
        employees_missing_reviewer = employees.filtered(lambda e: not e.reviewer_id)
        
        if employees_missing_supervisor:
            names = "\n".join([f"- {e.name}" for e in employees_missing_supervisor])
            error_messages.append(f"The following employees do not have a Supervisor assigned:\n{names}\n")
        
        if employees_missing_reviewer:
            names = "\n".join([f"- {e.name}" for e in employees_missing_reviewer])
            error_messages.append(f"The following employees do not have a Reviewer assigned:\n{names}\n")

        employees_missing_group = employees.filtered(lambda e: not e.evaluation_group_id)
        employees_with_group = employees - employees_missing_group

        if employees_with_group:
            unique_groups = employees_with_group.mapped('evaluation_group_id')
            valid_templates = self.env['appraisal.template'].search([
                ('evaluation_group_id', 'in', unique_groups.ids),
                ('active', '=', True)
            ])
            valid_group_ids = valid_templates.mapped('evaluation_group_id.id')
            employees_missing_template = employees_with_group.filtered(
                lambda e: e.evaluation_group_id.id not in valid_group_ids
            )
        else:
            employees_missing_template = self.env['hr.employee']

        total_template_errors = employees_missing_group | employees_missing_template

        if total_template_errors:
            names = "\n".join([f"- {e.name} (Group: {e.evaluation_group_id.name or 'None'})" for e in total_template_errors])
            error_messages.append(
                f"The following employees do not have a valid Appraisal Template assigned:\n{names}\n"
                "Please ensure they have an Evaluation Group assigned and a valid Template.\n"
            )

        if error_messages:
            full_error = "\n\n".join(error_messages)
            raise UserError(f"Cannot proceed due to configuration errors:\n\n{full_error}")

    def _create_employee_appraisals(self, employees, is_late=False):
        AppraisalObj = self.env['pms.appraisal']
        created_count = 0
        created_appraisals = self.env['pms.appraisal']
        
        for employee in employees:
            template = self.env['appraisal.template'].search([
                ('evaluation_group_id', '=', employee.evaluation_group_id.id),
                ('active', '=', True)
            ], limit=1)
            
            if not template:
                continue
            
            existing = AppraisalObj.search([('cycle_id', '=', self.id), ('employee_id', '=', employee.id)], limit=1)
            if existing:
                continue
            
            # Calculate custom dates if employee is added late
            start_date = fields.Date.today() if is_late else self.start_date
            end_date = start_date + relativedelta(days=self.planning_duration) if is_late else self.planning_deadline
            
            supervisor = employee.parent_id
            sec_supervisor = employee.secondary_manager_id
            reviewer = employee.reviewer_id
            
            appraisal = AppraisalObj.create({
                'cycle_id': self.id,
                'employee_id': employee.id,
                'template_id': template.id,
                'supervisor_id': supervisor.id if supervisor else False,
                'secondary_supervisor_id': sec_supervisor.id if sec_supervisor else False,
                'reviewer_id': reviewer.id if reviewer else False,
                'planning_start_date': start_date,
                'planning_end_date': end_date,
            })
            
            appraisal._clone_template_structure()
            created_appraisals |= appraisal
            created_count += 1
        
        if created_appraisals:
            self._notify_employees(created_appraisals)
        
        return created_count

    def action_open_add_employee_wizard(self):
        self.ensure_one()
        return {
            'name': 'Add Employees to Cycle',
            'type': 'ir.actions.act_window',
            'res_model': 'pms.add.employee.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_cycle_id': self.id}
        }

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
                    
                    #send an email notification
                    appraisal.message_post(
                        body=f"""Dear {appraisal.employee_id.name}, your performance plan for {self.name} is now active.""",
                        subject=f'Performance Plan Active - {self.name}',
                        message_type='notification',
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
            body="Moved to Monitoring phase. Plans are now locked",
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
            'view_mode': 'list,form',
            'domain': [('cycle_id', '=', self.id)],
            'context': {'default_cycle_id': self.id}
        }

    @api.model
    def _cron_auto_move_to_monitoring(self):
        today = fields.Date.today()
        # move state to monitoring after planning deadline has passed
        expired_planning_cycles = self.search([
            ('state', '=', 'planning'),
            ('planning_deadline', '<', today)
        ])
        
        for cycle in expired_planning_cycles:
            cycle.action_move_to_monitoring()



    
    appraisal_start_date = fields.Date(
        string='Appraisal Start Date',
        readonly=True,
        tracking=True,
        help='Date when HR manually moved the cycle to the Appraisal phase.'
    )

    def action_move_to_appraisal(self):
        # Move cycle from monitoring to appraisal phase 
        self.ensure_one()

        if self.state != 'monitoring':
            raise UserError('Only cycles in the Monitoring phase can be moved to Appraisal.')

        approved_appraisals = self.appraisal_ids.filtered(
            lambda a: a.state == 'approved'
        )

        if approved_appraisals:
            approved_appraisals.with_context(skip_edit_check=True).write({'state': 'appraisal_draft'})

        self.write({
            'state': 'appraisal',
            'appraisal_start_date': fields.Date.today()
        })
        
        self.message_post(
            body=f"Moved to Appraisal phase. {len(approved_appraisals)} plans unlocked for employee self-rating.",
            message_type='notification'
        )
        return True
    
    @api.constrains('state', 'cycle_type')
    def _check_concurrent_active_cycles(self):
        active_states = ['planning', 'monitoring', 'appraisal']
        for cycle in self:
            if cycle.state in active_states:
                domain = [('state', 'in', active_states), ('id', '!=', cycle.id)]
                
                if cycle.cycle_type in ['annual', 'semi_annual']:
                    domain.append(('cycle_type', 'in', ['annual', 'semi_annual']))
                    if self.search_count(domain):
                        raise ValidationError('Only one Regular cycle (Annual or Semi-Annual) can be active at a time.')
                        
                elif cycle.cycle_type == 'probation':
                    domain.append(('cycle_type', '=', 'probation'))
                    if self.search_count(domain):
                        raise ValidationError('Only one Probation cycle can be active at a time.')
