from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class EvaluationPlanning(models.Model):
    _name = 'evaluation.planning'
    _description = 'Planning'
    _rec_name = 'plan_name'
    _order = 'start_date desc'

    _sql_constraints = [
        ('check_dates_valid',
         'CHECK(start_date <= end_date)',
         'End date cannot be earlier than start date!'),

        # New: Ensure only one active plan at a time
        ('unique_active_plan',
         'EXCLUDE (state WITH =) WHERE (state = \'active\')',
         'Only one planning phase can be active at a time!'),
    ]

    # === STATES ===
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
    ], string='Status', default='draft', readonly=True)

    # === BASIC FIELDS ===
    plan_name = fields.Char(
        string='Plan Name',
        required=True,
        help="e.g., '2024 Annual Planning', 'Q3 Planning Cycle'"
    )

    # MANUAL DATE FIELDS ONLY
    start_date = fields.Date(
        string='Planning Start Date',
        required=True,
        default=fields.Date.today,
        help="Start date for the planning period"
    )

    end_date = fields.Date(
        string='Planning End Date',
        required=True,
        help="End date for the planning period"
    )

    description = fields.Text(string='Description')



    # === COMPUTED FIELDS ===
    duration_days = fields.Integer(
        string='Duration (Days)',
        compute='_compute_duration',
        store=True
    )

    is_active = fields.Boolean(
        string='Is Active',
        compute='_compute_is_active',
        store=True
    )

    is_completed = fields.Boolean(
        string='Is Completed',
        compute='_compute_is_completed',
        store=False
    )

    # === PERFORMANCE PLANS ===
    performance_plan_ids = fields.One2many(
        'performance.plan',
        'evaluation_planning_id',
        string='Performance Plans',
        readonly=True
    )

    plans_created = fields.Integer(
        string='Plans Created',
        compute='_compute_plan_stats',
        store=True
    )

    plans_in_progress = fields.Integer(
        string='Plans In Progress',
        compute='_compute_plan_stats',
        store=True
    )

    plans_completed = fields.Integer(
        string='Plans Completed',
        compute='_compute_plan_stats',
        store=True
    )

    # === COMPUTED METHODS ===
    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        """Compute duration in days"""
        for plan in self:
            if plan.start_date and plan.end_date:
                delta = plan.end_date - plan.start_date
                plan.duration_days = delta.days + 1
            else:
                plan.duration_days = 0

    @api.depends('state', 'start_date', 'end_date')
    def _compute_is_active(self):
        """Check if plan is currently active"""
        today = fields.Date.today()
        for plan in self:
            plan.is_active = (
                    plan.state == 'active' and
                    plan.start_date <= today <= plan.end_date
            )

    @api.depends('state')
    def _compute_is_completed(self):
        """Check if plan is completed"""
        for plan in self:
            plan.is_completed = (plan.state == 'completed')

    @api.onchange('start_date', 'end_date')
    def _onchange_dates(self):
        """Validate dates immediately when changed"""
        for plan in self:
            if plan.start_date and plan.end_date:
                if plan.end_date < plan.start_date:
                    warning = {
                        'title': 'Invalid Dates',
                        'message': 'End date cannot be earlier than start date!',
                    }
                    return {'warning': warning}

                # Also update duration immediately
                delta = plan.end_date - plan.start_date
                plan.duration_days = delta.days + 1

    # === CONSTRAINTS ===
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        """Validate date ranges - SIMPLIFIED"""
        for plan in self:
            if plan.start_date and plan.end_date:
                if plan.end_date < plan.start_date:
                    raise ValidationError("End date cannot be earlier than start date!")

    @api.depends('performance_plan_ids', 'performance_plan_ids.state')
    def _compute_plan_stats(self):
        """Compute statistics from performance plans - SAFE VERSION"""
        for plan in self:
            try:
                # Use search_count instead of len() for safety
                plan.plans_created = self.env['performance.plan'].search_count([
                    ('evaluation_planning_id', '=', plan.id)
                ])

                plan.plans_in_progress = self.env['performance.plan'].search_count([
                    ('evaluation_planning_id', '=', plan.id),
                    ('state', 'in', ['draft', 'submitted'])
                ])

                plan.plans_completed = self.env['performance.plan'].search_count([
                    ('evaluation_planning_id', '=', plan.id),
                    ('state', '=', 'approved')
                ])

            except Exception as e:
                _logger.warning(f"Error computing stats for plan {plan.id}: {e}")
                # Set safe defaults if there's an error
                plan.plans_created = 0
                plan.plans_in_progress = 0
                plan.plans_completed = 0

    # === WORKFLOW METHODS ===
    def action_activate(self):
        """Activate the planning cycle (draft → active) - STRICT VERSION"""
        for plan in self:
            # STRICT: Check if ANY other plan is already active
            active_plans = self.search([
                ('state', '=', 'active'),
                ('id', '!=', plan.id)
            ])

            if active_plans:
                active_plan = active_plans[0]
                today = fields.Date.today()

                # Check if active plan is within its period
                if active_plan.start_date <= today <= active_plan.end_date:
                    message = (
                        f"❌ Cannot activate '{plan.plan_name}'.\n\n"
                    f"📋 Plan '{active_plan.plan_name}' is currently active\n"
                    f"📅 Period: {active_plan.start_date} to {active_plan.end_date}\n"
                    f"⏳ Status: Within active period\n\n"
                    f"Please complete or cancel the active plan first."
                    )
                else:
                    # Active plan exists but outside its period
                    message = (
                        f"❌ Cannot activate '{plan.plan_name}'.\n\n"
                        f"📋 Plan '{active_plan.plan_name}' is still marked as active\n"
                        f"📅 Period: {active_plan.start_date} to {active_plan.end_date}\n"
                        f"⏳ Status: Outside planned period\n\n"
                        f"Please complete or cancel the active plan first."
                    )

                raise ValidationError(message)

            if plan.state != 'draft':
                raise ValidationError("Only draft plans can be activated!")

            # Check if we're in the planning period
            today = fields.Date.today()

            if today < plan.start_date:
                days_until_start = (plan.start_date - today).days
                raise ValidationError(
                    f"⏰ Planning starts on {plan.start_date.strftime('%B %d, %Y')}. "
                    f"Please wait {days_until_start} more day{'s' if days_until_start > 1 else ''}."
                )

            if today > plan.end_date:
                raise ValidationError(
                    f"📅 Planning ended on {plan.end_date.strftime('%B %d, %Y')}. "
                    f"Please create a new planning cycle with future dates."
                )

            # VERIFICATION: Check if template module is installed
            if 'kpi.template' not in self.env:
                raise ValidationError("KPI Template module (kpi_form) is not installed!")

            if 'competency.template' not in self.env:
                raise ValidationError("Competency Template module is not installed!")

            # Activate the plan FIRST
            plan.state = 'active'

            # THEN create performance plans
            result = plan._create_performance_plans_for_all_employees()

            # Build success message
            message = (
                f"✅ <b>Plan '{plan.plan_name}' activated successfully!</b><br/><br/>"
                f"📋 Created {result['created']} performance plans<br/>"
                f"⏭️ Skipped {result['skipped']} employees"
            )

            if result['errors']:
                message += f"<br/><br/>⚠️ <b>Issues:</b><br/>" + "<br/>".join(result['errors'][:3])
                if len(result['errors']) > 3:
                    message += f"<br/>... and {len(result['errors']) - 3} more"

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '✅ Activation Complete',
                    'message': message,
                    'sticky': True,
                    'type': 'warning' if result.get('errors') else 'success',
                }
            }

    @api.model
    def create(self, vals):
        """Prevent creating new plan as active if another active exists"""
        if vals.get('state') == 'active':
            active_plans = self.search([('state', '=', 'active')])
            if active_plans:
                active_plan = active_plans[0]
                raise ValidationError(
                    f"Cannot create new plan as active. "
                    f"Plan '{active_plan.plan_name}' is already active. "
                    f"Please complete or cancel it first."
                )
        return super().create(vals)

    def write(self, vals):
        """Prevent activating plan if another is active"""
        if vals.get('state') == 'active':
            # Exclude self from the search
            other_active_plans = self.search([
                ('state', '=', 'active'),
                ('id', 'not in', self.ids)
            ])

            if other_active_plans:
                active_plan = other_active_plans[0]
                raise ValidationError(
                    f"Cannot activate this plan. "
                    f"Plan '{active_plan.plan_name}' is already active. "
                    f"Please complete or cancel it first."
                )

        return super().write(vals)

    @api.constrains('state')
    def _check_only_one_active(self):
        """Ensure only one plan can be active at a time - database level"""
        for plan in self:
            if plan.state == 'active':
                other_active = self.search([
                    ('state', '=', 'active'),
                    ('id', '!=', plan.id)
                ])
                if other_active:
                    raise ValidationError(
                        f"Only one planning phase can be active at a time. "
                        f"Plan '{other_active[0].plan_name}' is already active."
                    )

    def action_view_active_plan(self):
        """View the currently active plan"""
        active_plans = self.search([('state', '=', 'active')], limit=1)

        if not active_plans:
            raise UserError("⚠️ There is no active planning phase.")

        return {
            'type': 'ir.actions.act_window',
            'name': 'Active Planning Phase',
            'res_model': 'evaluation.planning',
            'res_id': active_plans.id,
            'views': [(False, 'form')],
            'target': 'current',
        }
    def action_cancel(self):
        """Cancel/Stop an active planning cycle (Active → Draft) - Read-only mode"""
        for plan in self:
            if plan.state != 'active':
                raise ValidationError("Only active plans can be cancelled!")

            # Count performance plans
            total_plans = len(plan.performance_plan_ids)

            # Mark performance plans as read-only (cancelled state)
            if total_plans > 0:
                cancelled_count = 0
                for perf_plan in plan.performance_plan_ids:
                    try:
                        # Mark as cancelled/archived (read-only)
                        perf_plan.write({
                            'state': 'cancelled',
                            'active': False,  # Hide from normal views
                            'is_cancelled': True,  # Optional flag
                        })
                        cancelled_count += 1

                        # Optional: Add activity log
                        perf_plan.message_post(
                            body=f"Performance plan cancelled because planning '{plan.plan_name}' was cancelled.",
                            subject="Plan Cancelled"
                        )

                    except Exception as e:
                        _logger.error(f"Failed to cancel performance plan {perf_plan.id}: {e}")

                _logger.info(f"Marked {cancelled_count} performance plans as cancelled/read-only")

            # Set plan back to draft (so it can be edited/reactivated)
            plan.state = 'draft'

            # Show notification
            message = (
                f"✅ Plan '{plan.plan_name}' has been cancelled.<br/>"
                f"📋 {total_plans} performance plans have been archived (read-only).<br/>"
                f"📝 Plan is now in draft mode and can be edited/reactivated."
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Plan Cancelled',
                    'message': message,
                    'sticky': True,
                    'type': 'warning',
                }
            }

    def _get_templates_for_employee(self, employee):
        """Get templates for employee's evaluation group - FIXED VERSION"""
        templates = {'kpi': None, 'competency': None}

        if not employee.evaluation_group_id:
            return templates

        # DEBUG: Log what we're searching for
        _logger.info(f"Searching templates for {employee.name}, group ID: {employee.evaluation_group_id.id}")

        # Method 1: Direct search (most reliable)
        try:
            # Search ALL KPI templates first to see what exists
            all_kpi_templates = self.env['kpi.template'].search([])
            _logger.info(f"Total KPI templates in system: {len(all_kpi_templates)}")

            # Now search for specific group
            kpi_template = self.env['kpi.template'].search([
                ('evaluation_group_id', '=', employee.evaluation_group_id.id)
            ], limit=1)

            if kpi_template:
                templates['kpi'] = kpi_template
                _logger.info(f"✓ Found KPI template: {kpi_template.name}")
            else:
                _logger.warning(f"✗ No KPI template found for group ID {employee.evaluation_group_id.id}")

        except Exception as e:
            _logger.error(f"KPI template search error: {str(e)}")

        # Method 2: Alternative search (in case field name is different)
        try:
            if not templates['kpi']:
                # Try searching by name
                kpi_template = self.env['kpi.template'].search([
                    ('name', 'ilike', employee.evaluation_group_id.name)
                ], limit=1)
                if kpi_template:
                    templates['kpi'] = kpi_template
                    _logger.info(f"✓ Found KPI template by name match: {kpi_template.name}")
        except:
            pass

        # Competency template search
        try:
            competency_template = self.env['competency.template'].search([
                ('evaluation_group_id', '=', employee.evaluation_group_id.id)
            ], limit=1)

            if competency_template:
                templates['competency'] = competency_template
                _logger.info(f"✓ Found competency template: {competency_template.name}")
            else:
                _logger.warning(f"✗ No competency template found for group ID {employee.evaluation_group_id.id}")

        except Exception as e:
            _logger.error(f"Competency template search error: {str(e)}")

        return templates
    def _send_plan_notification(self, performance_plan):
        """Send notification to employee about new performance plan"""
        try:
            if performance_plan.employee_id.user_id:
                performance_plan.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=f'New Performance Plan: {self.plan_name}',
                    note=f"""
                    A new performance plan has been assigned to you as part of the evaluation cycle:

                    📋 Evaluation: {self.plan_name}
                    📅 Period: {self.start_date} to {self.end_date}

                    Please set your targets in the performance plan.
                    """,
                    user_id=performance_plan.employee_id.user_id.id
                )
        except Exception as e:
            _logger.warning(f"Failed to send notification: {str(e)}")

    # === OTHER METHODS ===
    def action_complete(self):
        """Mark plan as completed (Active → Completed)"""
        for plan in self:
            if plan.state != 'active':
                raise ValidationError("Only active plans can be marked as completed!")

            plan.state = 'completed'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Plan Completed',
                'message': f"✅ Plan '{self.plan_name}' has been marked as completed.",
                'sticky': False,
                'type': 'success',
            }
        }

    def action_set_to_draft(self):
        """Reset plan to draft state (Completed → Draft)"""
        for plan in self:
            if plan.state != 'completed':
                raise ValidationError("Only completed plans can be reset to draft!")

            plan.state = 'draft'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Plan Reset',
                'message': f"✅ Plan '{self.plan_name}' has been reset to draft.",
                'sticky': False,
                'type': 'info',
            }
        }

    def action_create_copy(self):
        """Create a copy of the current plan"""
        self.ensure_one()

        new_plan = self.copy(default={
            'plan_name': f"{self.plan_name} (Copy)",
            'state': 'draft',
            'performance_plan_ids': False,  # Don't copy performance plans
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'evaluation.planning',
            'res_id': new_plan.id,
            'views': [(False, 'form')],
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_view_performance_plans(self):
        """View all performance plans for this evaluation"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Performance Plans - {self.plan_name}',
            'res_model': 'performance.plan',
            'view_mode': 'list,form',
            'domain': [('evaluation_planning_id', '=', self.id)],
            'context': {
                'default_evaluation_planning_id': self.id,
                'search_default_evaluation_planning_id': self.id,
            }
        }

    def action_check_templates(self):
        """Check if templates are available for all employees"""
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('evaluation_group_id', '!=', False)
        ])

        issues = []
        ready_count = 0

        for employee in employees:
            templates = self._get_templates_for_employee(employee)

            if not templates['kpi']:
                issues.append(f"❌ {employee.name}: No KPI template for group '{employee.evaluation_group_id.name}'")
            elif not templates['competency']:
                issues.append(
                    f"❌ {employee.name}: No competency template for group '{employee.evaluation_group_id.name}'")
            else:
                ready_count += 1

        message = f"✅ {ready_count} employees ready for performance plans<br/>"
        if issues:
            message += f"<br/>⚠️ Issues found:<br/>" + "<br/>".join(issues[:5])
            if len(issues) > 5:
                message += f"<br/>... and {len(issues) - 5} more"

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Template Availability Check',
                'message': message,
                'sticky': True,
                'type': 'warning' if issues else 'success',
            }
        }

    def debug_template_search(self):
        """Debug template search for specific evaluation group"""
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('evaluation_group_id', '!=', False)
        ])

        debug_info = []

        for employee in employees[:5]:  # Check first 5 employees
            debug_info.append(f"<br/><strong>{employee.name}</strong>")
            debug_info.append(f"Evaluation Group: {employee.evaluation_group_id.name}")

            # Check KPI templates
            kpi_templates = self.env['kpi.template'].search([
                ('evaluation_group_id', '!=', False)
            ])
            debug_info.append(f"Total KPI Templates: {len(kpi_templates)}")

            # Check for specific group
            group_kpi_templates = self.env['kpi.template'].search([
                ('evaluation_group_id', '=', employee.evaluation_group_id.id)
            ])
            debug_info.append(f"KPI Templates for this group: {len(group_kpi_templates)}")

            if group_kpi_templates:
                for template in group_kpi_templates:
                    debug_info.append(f"  - {template.name} (ID: {template.id})")

            # Check competency templates
            comp_templates = self.env['competency.template'].search([
                ('evaluation_group_id', '=', employee.evaluation_group_id.id)
            ])
            debug_info.append(f"Competency Templates for this group: {len(comp_templates)}")

            if comp_templates:
                for template in comp_templates:
                    debug_info.append(f"  - {template.name} (ID: {template.id})")

        message = "<br/>".join(debug_info)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Template Debug Info',
                'message': message,
                'sticky': True,
                'type': 'info',
            }
        }

    def debug_template_contents(self):
        """Debug what's inside the templates"""
        debug_info = []

        # Get Project Delivery group
        project_group = self.env['evaluation.group'].search([
            ('name', '=', 'Project Delivery')
        ], limit=1)

        if not project_group:
            debug_info.append("❌ Project Delivery group not found")
            return self._show_debug_message(debug_info)

        # Check KPI template
        kpi_template = self.env['kpi.template'].search([
            ('evaluation_group_id', '=', project_group.id)
        ], limit=1)

        if kpi_template:
            debug_info.append(f"<strong>KPI Template: {kpi_template.name}</strong>")
            debug_info.append(f"ID: {kpi_template.id}")
            debug_info.append(f"Total Score: {kpi_template.total_score}")
            debug_info.append(f"Computed Total: {kpi_template.computed_total}")
            debug_info.append(f"Number of KPI Lines: {len(kpi_template.line_ids)}")

            if kpi_template.line_ids:
                debug_info.append("<strong>KPI Lines:</strong>")
                for i, line in enumerate(kpi_template.line_ids, 1):
                    debug_info.append(f"  {i}. {line.kpi_name} - Score: {line.score}")
            else:
                debug_info.append("⚠️ KPI Template has NO lines!")
        else:
            debug_info.append("❌ No KPI template found")

        # Check competency template
        comp_template = self.env['competency.template'].search([
            ('evaluation_group_id', '=', project_group.id)
        ], limit=1)

        if comp_template:
            debug_info.append(f"<br/><strong>Competency Template: {comp_template.name}</strong>")
            debug_info.append(f"ID: {comp_template.id}")

            # Check what fields exist on competency template
            debug_info.append(f"Fields: {list(comp_template._fields.keys())[:10]}...")

            if hasattr(comp_template, 'line_ids'):
                debug_info.append(f"Number of Competency Lines: {len(comp_template.line_ids)}")
                if comp_template.line_ids:
                    debug_info.append("<strong>Competency Lines:</strong>")
                    for i, line in enumerate(comp_template.line_ids[:5], 1):
                        # Try different possible field names
                        if hasattr(line, 'competency_name'):
                            debug_info.append(f"  {i}. {line.competency_name}")
                        elif hasattr(line, 'name'):
                            debug_info.append(f"  {i}. {line.name}")
                        else:
                            debug_info.append(f"  {i}. Line ID: {line.id}")
                else:
                    debug_info.append("⚠️ Competency Template has NO lines!")
            else:
                debug_info.append("❌ Competency template has no line_ids field!")
        else:
            debug_info.append("<br/>❌ No competency template found")

        return self._show_debug_message(debug_info)

    def test_fixed_population(self):
        """Test method with proper single record creation"""
        # Get first employee WITH evaluation group (not Administrator)
        employee = self.env['hr.employee'].search([
            ('active', '=', True),
            ('evaluation_group_id', '!=', False)
        ], limit=1)

        if not employee:
            raise UserError("No employee found with an evaluation group assigned!")

        # Get templates for employee
        templates = self._get_templates_for_employee(employee)

        if not templates['kpi'] or not templates['competency']:
            raise UserError(f"No templates found for {employee.name} in group '{employee.evaluation_group_id.name}'")

        # Create performance plan
        test_plan = self.env['performance.plan'].create({
            'evaluation_planning_id': self.id,
            'employee_id': employee.id,
            'evaluation_group_id': employee.evaluation_group_id.id,
            'kpi_template_id': templates['kpi'].id,
            'competency_template_id': templates['competency'].id,
            'name': f"TEST-{employee.name}",
        })

        # Auto-populate lines
        test_plan._auto_populate_kpi_lines()
        test_plan._auto_populate_competency_lines()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test Successful',
                'message': f"Created test plan for {employee.name} with {len(test_plan.kpi_line_ids)} KPI lines and {len(test_plan.competency_line_ids)} competency lines.",
                'sticky': True,
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'performance.plan',
                    'res_id': test_plan.id,
                    'views': [[False, 'form']],
                    'target': 'current',
                }
            }
        }

    def _show_debug_message(self, debug_info):
        """Helper to show debug message"""
        message = "<br/>".join(debug_info)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test Results',
                'message': message,
                'sticky': True,
                'type': 'info',
            }
        }

    def _create_performance_plans_for_all_employees(self):
        """Create performance plans for ALL employees who have evaluation groups"""
        # Get all active employees WITH evaluation groups
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('evaluation_group_id', '!=', False)
        ])

        results = {
            'created': 0,
            'skipped': 0,
            'errors': []
        }

        for employee in employees:
            try:
                _logger.info(f"Processing employee: {employee.name}")

                # Check if plan already exists for this employee in this evaluation
                existing_plan = self.env['performance.plan'].search([
                    ('evaluation_planning_id', '=', self.id),
                    ('employee_id', '=', employee.id)
                ], limit=1)

                if existing_plan:
                    results['skipped'] += 1
                    results['errors'].append(f"{employee.name}: Plan already exists for this evaluation")
                    _logger.info(f"Plan already exists for {employee.name}")
                    continue

                # Get templates for employee's evaluation group
                templates = self._get_templates_for_employee(employee)
                _logger.info(
                    f"Templates for {employee.name}: KPI={templates['kpi']}, Competency={templates['competency']}")

                # Validate templates exist
                if not templates['kpi']:
                    results['skipped'] += 1
                    results['errors'].append(
                        f"{employee.name}: No KPI template found for group '{employee.evaluation_group_id.name}'"
                    )
                    _logger.warning(f"No KPI template for {employee.name}")
                    continue

                if not templates['competency']:
                    results['skipped'] += 1
                    results['errors'].append(
                        f"{employee.name}: No competency template found for group '{employee.evaluation_group_id.name}'"
                    )
                    _logger.warning(f"No competency template for {employee.name}")
                    continue

                # Create performance plan with ALL data
                plan_vals = {
                    'evaluation_planning_id': self.id,
                    'employee_id': employee.id,
                    'evaluation_group_id': employee.evaluation_group_id.id,
                    'kpi_template_id': templates['kpi'].id,
                    'competency_template_id': templates['competency'].id,
                    'name': f"PP/{datetime.now().year}/{employee.id:04d}",
                }

                _logger.info(f"Creating plan with values: {plan_vals}")

                plan = self.env['performance.plan'].create(plan_vals)
                _logger.info(f"Plan created with ID: {plan.id}")

                # Auto-populate lines from templates
                _logger.info("Populating KPI lines")
                plan._auto_populate_kpi_lines()

                _logger.info("Populating competency lines")
                plan._auto_populate_competency_lines()

                results['created'] += 1
                _logger.info(f"Successfully created plan for {employee.name}")

                # Send notification to employee
                try:
                    self._send_plan_notification(plan)
                except Exception as e:
                    _logger.warning(f"Failed to send notification: {str(e)}")

            except Exception as e:
                results['skipped'] += 1
                error_msg = f"{employee.name}: {str(e)}"
                results['errors'].append(error_msg)
                _logger.error(f"Failed to create plan for {employee.name}: {str(e)}")
                import traceback
                traceback.print_exc()

        _logger.info(f"Final results: {results}")
        return results

    def debug_project_delivery_templates(self):
        """Debug: Check templates for Project Delivery group"""
        debug_info = []

        # Find the Project Delivery evaluation group
        project_group = self.env['evaluation.group'].search([
            ('name', '=', 'Project Delivery')
        ], limit=1)

        if not project_group:
            debug_info.append("❌ ERROR: 'Project Delivery' evaluation group not found!")
            debug_info.append("Available groups:")
            all_groups = self.env['evaluation.group'].search([])
            for group in all_groups:
                debug_info.append(f"  - {group.name} (ID: {group.id})")
        else:
            debug_info.append(f"✅ Found 'Project Delivery' group (ID: {project_group.id})")

            # Check KPI templates for this group
            kpi_templates = self.env['kpi.template'].search([
                ('evaluation_group_id', '=', project_group.id)
            ])

            debug_info.append(f"KPI Templates found: {len(kpi_templates)}")
            for template in kpi_templates:
                debug_info.append(f"  - {template.name} (ID: {template.id})")
                debug_info.append(f"    Lines: {len(template.line_ids)}")

                # Check if template has lines
                if template.line_ids:
                    debug_info.append(f"    Line scores: {[line.score for line in template.line_ids]}")
                else:
                    debug_info.append("    ⚠️ No KPI lines!")

            # Check competency templates
            if 'competency.template' in self.env:
                comp_templates = self.env['competency.template'].search([
                    ('evaluation_group_id', '=', project_group.id)
                ])

                debug_info.append(f"<br/>Competency Templates found: {len(comp_templates)}")
                for template in comp_templates:
                    debug_info.append(f"  - {template.name} (ID: {template.id})")
                    if hasattr(template, 'line_ids'):
                        debug_info.append(f"    Lines: {len(template.line_ids)}")
            else:
                debug_info.append("<br/>❌ competency.template model not found!")

        message = "<br/>".join(debug_info)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Project Delivery Debug',
                'message': message,
                'sticky': True,
                'type': 'info',
            }
        }

    def test_activation_only(self):
        """Test activation without creating plans"""
        self.ensure_one()

        if self.state == 'draft':
            # Just activate without creating plans
            self.state = 'active'

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Test Activation',
                    'message': f"✅ Plan '{self.plan_name}' activated (test mode). No performance plans created.",
                    'sticky': False,
                    'type': 'success',
                }
            }
        else:
            raise ValidationError(f"Plan is in {self.state} state, not draft")