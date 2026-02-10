from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)


class EvaluationPlanning(models.Model):
    _name = 'evaluation.planning'
    _description = 'Evaluation Planning'
    _rec_name = 'plan_name'
    _order = 'start_date desc'

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
        help="e.g., '2024 Annual Reviews', 'Q3 Performance Appraisals'"
    )

    plan_type = fields.Selection([
        ('yearly', 'Yearly'),
        ('quarterly', 'Quarterly'),
        ('half_yearly', 'Half-Yearly'),
        ('probation', 'Probation'),
        ('custom', 'Custom')
    ], string='Plan Type', required=True, default='yearly')

    calculation_method = fields.Selection([
        ('calendar', 'Calendar-Based (End of Period)'),
        ('exact', 'Exact Months from Start'),
        ('days', 'Fixed Number of Days')
    ], string='Calculation Method', required=True, default='calendar')

    fixed_days = fields.Integer(string='Fixed Duration (Days)', default=90)
    start_date = fields.Date(string='Start Date', required=True, default=fields.Date.today)
    end_date = fields.Date(string='End Date', required=True)
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

    # === ONCHANGE ===
    @api.onchange('plan_type', 'start_date', 'calculation_method', 'fixed_days')
    def _onchange_plan_type(self):
        """Auto-calculate end date based on plan type"""
        if self.start_date and self.plan_type and self.calculation_method and self.plan_type != 'custom':
            start_date = self.start_date
            end_date = False

            if self.calculation_method == 'days':
                if self.fixed_days > 0:
                    end_date = start_date + timedelta(days=self.fixed_days - 1)
            elif self.calculation_method == 'calendar':
                if self.plan_type == 'yearly':
                    end_date = datetime(start_date.year, 12, 31).date()
                elif self.plan_type == 'half_yearly':
                    if start_date.month <= 6:
                        end_date = datetime(start_date.year, 6, 30).date()
                    else:
                        end_date = datetime(start_date.year, 12, 31).date()
                elif self.plan_type == 'quarterly':
                    quarter = (start_date.month - 1) // 3
                    if quarter == 0:
                        end_date = datetime(start_date.year, 3, 31).date()
                    elif quarter == 1:
                        end_date = datetime(start_date.year, 6, 30).date()
                    elif quarter == 2:
                        end_date = datetime(start_date.year, 9, 30).date()
                    else:
                        end_date = datetime(start_date.year, 12, 31).date()
                elif self.plan_type == 'probation':
                    end_date = start_date + timedelta(days=90 - 1)
            elif self.calculation_method == 'exact':
                if self.plan_type == 'yearly':
                    end_date = start_date + relativedelta(years=1)
                elif self.plan_type == 'half_yearly':
                    end_date = start_date + relativedelta(months=6)
                elif self.plan_type == 'quarterly':
                    end_date = start_date + relativedelta(months=3)
                elif self.plan_type == 'probation':
                    end_date = start_date + relativedelta(months=3)

            if end_date:
                self.end_date = end_date

    # === CONSTRAINTS ===
    @api.constrains('start_date', 'end_date', 'fixed_days')
    def _check_dates(self):
        """Validate date ranges"""
        for plan in self:
            if plan.start_date and plan.end_date:
                if plan.end_date < plan.start_date:
                    raise ValidationError("End date cannot be earlier than start date!")
                if plan.calculation_method == 'days' and plan.fixed_days <= 0:
                    raise ValidationError("Fixed duration must be greater than 0 days!")
                if plan.plan_type == 'probation' and plan.duration_days > 180:
                    raise ValidationError("Probation period cannot exceed 6 months!")

    def action_toggle_activation(self):
        """Toggle between Draft and Active states"""
        for plan in self:
            if plan.state == 'draft':
                # Check if there's already an active plan of same type
                active_plans = self.search([
                    ('plan_type', '=', plan.plan_type),
                    ('state', '=', 'active'),
                    ('id', '!=', plan.id)
                ])

                if active_plans:
                    raise ValidationError(
                        f"Cannot activate '{plan.plan_name}'. "
                        f"There's already an active {plan.plan_type} plan: "
                        f"{active_plans[0].plan_name}"
                    )

                plan.state = 'active'

                # ✅✅✅ ADD THIS LINE TO AUTO-LOAD TEMPLATES ✅✅✅
                created_count = plan._create_performance_plans_for_employees()

                message = f"✅ Plan '{plan.plan_name}' has been activated. Created {created_count} performance plans."

            elif plan.state == 'active':
                plan.state = 'draft'
                message = f"⚠️ Plan '{plan.plan_name}' has been deactivated."

            elif plan.state == 'completed':
                raise ValidationError(f"Cannot modify completed plan: '{plan.plan_name}'")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Status Updated',
                'message': message,
                'sticky': False,
                'type': 'success',
            }
        }
    def _create_performance_plans_for_employees(self):
        """Create performance plans for all eligible employees with auto-template assignment"""
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('user_id', '!=', False),  # Has user account
            ('evaluation_group_id', '!=', False)  # Has evaluation group assigned
        ])

        created_count = 0

        for employee in employees:
            # Check if plan already exists
            existing_plan = self.env['performance.plan'].search([
                ('evaluation_planning_id', '=', self.id),
                ('employee_id', '=', employee.id)
            ], limit=1)

            if not existing_plan:
                # FIND TEMPLATES BASED ON EMPLOYEE'S EVALUATION GROUP
                kpi_template = self.env['kpi.template'].search([
                    ('evaluation_group_id', '=', employee.evaluation_group_id.id),
                    ('active', '=', True)
                ], limit=1)

                competency_template = self.env['competency.template'].search([
                    ('evaluation_group_id', '=', employee.evaluation_group_id.id),
                    ('active', '=', True)
                ], limit=1)

                if not kpi_template or not competency_template:
                    _logger.warning(f"No templates found for employee {employee.name} "
                                    f"in evaluation group {employee.evaluation_group_id.name}")
                    continue

                # CREATE PERFORMANCE PLAN
                performance_plan = self.env['performance.plan'].create({
                    'evaluation_planning_id': self.id,
                    'employee_id': employee.id,
                    'name': f"{self.plan_name} - {employee.name}",
                    'kpi_template_id': kpi_template.id,
                    'competency_template_id': competency_template.id,
                    'first_approver_id': employee.parent_id.id if employee.parent_id else False,
                    'second_approver_id': employee.second_manager_id.id if hasattr(employee,
                                                                                   'second_manager_id') else False,
                    'reviewer_id': employee.reviewer_id.id if hasattr(employee, 'reviewer_id') else False,
                })

                # AUTO-POPULATE TEMPLATE LINES WITH EMPTY TARGET FIELDS
                performance_plan._auto_populate_kpi_lines()
                performance_plan._auto_populate_competency_lines()

                created_count += 1

                # SEND NOTIFICATION TO EMPLOYEE
                self._notify_employee(performance_plan)

        return created_count

    def _notify_employee(self, performance_plan):
        """Send notification to employee about their new performance plan"""
        if performance_plan.employee_id.user_id:
            performance_plan.message_post(
                body=f"""
                   <div style="font-family: Arial, sans-serif; padding: 20px;">
                       <h2 style="color: #875A7B;">🎯 New Performance Plan Assigned</h2>

                       <p>Dear <strong>{performance_plan.employee_id.name}</strong>,</p>

                       <p>A new performance plan has been created for you as part of the evaluation cycle:</p>

                       <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
                           <p><strong>Evaluation Plan:</strong> {self.plan_name}</p>
                           <p><strong>Period:</strong> {self.start_date} to {self.end_date}</p>
                           <p><strong>KPI Template:</strong> {performance_plan.kpi_template_id.name}</p>
                           <p><strong>Competency Template:</strong> {performance_plan.competency_template_id.name}</p>
                       </div>

                       <p>Please set your targets for each KPI and competency by clicking the button below:</p>

                       <div style="text-align: center; margin: 25px 0;">
                           <a href="/web#id={performance_plan.id}&model=performance.plan&view_type=form" 
                              style="background-color: #875A7B; color: white; padding: 12px 24px; 
                                     text-decoration: none; border-radius: 4px; font-weight: bold;">
                              ✏️ Set My Targets
                           </a>
                       </div>
                   </div>
                   """,
                subject=f'Action Required: Set Your Targets - {self.plan_name}',
                partner_ids=performance_plan.employee_id.user_id.partner_id.ids,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

        # === OTHER METHODS (keep your existing) ===

    def action_close_planning(self):
        """Close the evaluation planning"""
        for plan in self:
            if plan.state != 'active':
                raise ValidationError("Only active evaluations can be closed!")

            plan.state = 'closed'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Evaluation Closed',
                'message': f"✅ Evaluation '{self.plan_name}' has been closed and archived.",
                'sticky': False,
                'type': 'success',
            }
        }

    def action_reopen_planning(self):
        """Reopen a closed evaluation"""
        for plan in self:
            if plan.state != 'closed':
                raise ValidationError("Only closed evaluations can be reopened!")

            if plan.end_date < fields.Date.today():
                raise ValidationError(
                    f"Cannot reopen '{plan.plan_name}'. "
                    f"The evaluation end date ({plan.end_date}) has already passed."
                )

            plan.state = 'active'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Evaluation Reopened',
                'message': f"✅ Evaluation '{self.plan_name}' has been reopened.",
                'sticky': False,
                'type': 'warning',
            }
        }
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
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'evaluation.planning',
            'res_id': new_plan.id,
            'views': [(False, 'form')],
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    @api.depends('performance_plan_ids', 'performance_plan_ids.state')
    def _compute_plan_stats(self):
        """Compute statistics from performance plans"""
        for plan in self:
            plan.plans_created = len(plan.performance_plan_ids)
            plan.plans_in_progress = len(plan.performance_plan_ids.filtered(
                lambda p: p.state in ['draft', 'submitted']
            ))
            plan.plans_completed = len(plan.performance_plan_ids.filtered(
                lambda p: p.state == 'approved'
            ))