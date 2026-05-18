from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import re
import logging
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rating Definition (WITHOUT eligibility - pure definition)
# ---------------------------------------------------------------------------
class PMSRatingDefinition(models.Model):
    _name = 'pms.rating.definition'
    _description = 'Rating Definition'
    _order = 'sequence, min_score desc'
    _rec_name = 'name'

    name = fields.Char(string='Rating Name', required=True)
    sequence = fields.Integer(string='Priority', default=10)
    min_score = fields.Float(string='Min Score', required=True, digits=(5, 2))
    max_score = fields.Float(string='Max Score', required=True, digits=(5, 2))
    description = fields.Text(string='Description')
    color = fields.Integer(string='Color Index')
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ('unique_rating_name', 'unique(name, company_id)',
         'Rating name must be unique per company!'),
        ('check_score_range',
         'CHECK(min_score >= 0 AND max_score <= 100 AND min_score <= max_score)',
         'Score range must be between 0–100 and min ≤ max!'),
    ]

    @api.constrains('min_score', 'max_score')
    def _check_overlapping_ranges(self):
        for record in self:
            overlapping = self.search([
                ('id', '!=', record.id),
                ('company_id', '=', record.company_id.id),
                ('min_score', '<', record.max_score),
                ('max_score', '>', record.min_score),
            ])
            if overlapping:
                raise ValidationError(
                    _('Score ranges cannot overlap! "%s" overlaps with: %s')
                    % (record.name, ', '.join(overlapping.mapped('name')))
                )

    @api.model
    def get_rating(self, score):
        return self.search([
            ('min_score', '<=', score),
            ('max_score', '>=', score),
            ('active', '=', True),
        ], limit=1)

    def name_get(self):
        return [
            (r.id, f"{r.name} ({r.min_score:.0f}–{r.max_score:.0f})")
            for r in self
        ]


# ---------------------------------------------------------------------------
# Bonus Engine Rating Eligibility (inherits rating tiers)
# ---------------------------------------------------------------------------
class PMSBonusEngineRatingEligibility(models.Model):
    _name = 'pms.bonus.engine.rating.eligibility'
    _description = 'Bonus Engine Rating Eligibility'
    _order = 'rating_sequence'
    _rec_name = 'rating_name'

    engine_id = fields.Many2one('pms.bonus.engine', string='Bonus Engine', required=True, ondelete='cascade')
    rating_id = fields.Many2one('pms.rating.definition', string='Rating Tier', required=True)
    
    rating_sequence = fields.Integer(string='Sequence', related='rating_id.sequence', store=True)
    rating_name = fields.Char(string='Rating Tier', related='rating_id.name', store=True, readonly=True)
    rating_min_score = fields.Float(string='Min Score', related='rating_id.min_score', store=True, readonly=True)
    rating_max_score = fields.Float(string='Max Score', related='rating_id.max_score', store=True, readonly=True)
    rating_description = fields.Text(string='Description', related='rating_id.description', readonly=True)
    rating_color = fields.Integer(string='Color', related='rating_id.color')
    rating_active = fields.Boolean(string='Active', related='rating_id.active')
    
    eligibility_percentage = fields.Float(
        string='Eligibility (%)',
        required=True,
        default=0.0,
        digits=(5, 2),
        help='The % of base salary used as the bonus multiplier for this tier (0–100).'
    )
    
    company_id = fields.Many2one(
        'res.company', string='Company',
        related='engine_id.company_id', store=True,
    )

    _sql_constraints = [
        ('unique_rating_per_engine', 'unique(engine_id, rating_id)',
         'Each rating can only be configured once per bonus engine!'),
        ('check_eligibility',
         'CHECK(eligibility_percentage >= 0 AND eligibility_percentage <= 100)',
         'Eligibility % must be between 0 and 100!'),
    ]


# ---------------------------------------------------------------------------
# Bonus Engine
# ---------------------------------------------------------------------------
class PMSBonusEngine(models.Model):
    _name = 'pms.bonus.engine'
    _description = 'Bonus Engine'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(string='Engine Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    description = fields.Text(string='Description')

    formula = fields.Text(
        string='Bonus Formula',
        required=True,
        default='base_salary * eligibility * 0.15',
        help=(
            'Python expression. Result is the bonus amount in local currency.\n\n'
            'Available variables:\n'
            '  score          – appraisal score (0–100)\n'
            '  eligibility    – tier eligibility as a ratio (0–1)\n'
            '  base_salary    – employee wage\n'
            '  years_service  – tenure in years\n'
            '  months_served  – total months of the cycle (12 for annual, 6 for semi-annual, 3 for probation)\n\n'
            'Example formulas:\n'
            '  base_salary * eligibility * 0.15\n'
            '  (score / 100) * base_salary * eligibility * 0.20\n'
            '  base_salary * eligibility * (1 + months_served * 0.005) * 0.10'
        ),
    )

    formula_preview = fields.Char(
        string='Formula Preview', compute='_compute_formula_preview',
    )
    validation_status = fields.Boolean(
        string='Is Valid', compute='_compute_validation', store=False,
    )
    validation_error = fields.Text(
        string='Validation Error', compute='_compute_validation', store=False,
    )

    use_tenure_weight = fields.Boolean(string='Use Tenure Weighting')
    tenure_max_months = fields.Integer(string='Max Tenure Months', default=120)
    tenure_weight = fields.Float(string='Weight Multiplier', default=0.01)

    use_cap = fields.Boolean(string='Apply Maximum Cap')
    max_cap_percent = fields.Float(string='Maximum Cap (% of salary)', default=50.0)

    use_floor = fields.Boolean(string='Apply Minimum Floor')
    min_floor_amount = fields.Monetary(
        string='Minimum Floor Amount', currency_field='currency_id',
    )

    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    rating_eligibility_ids = fields.One2many(
        'pms.bonus.engine.rating.eligibility',
        'engine_id',
        string='Rating Eligibility',
        help='Define eligibility percentages for each rating tier (inherited from Rating Tiers)'
    )

    _ALWAYS_AVAILABLE = {
        'score', 'eligibility', 'base_salary', 'years_service', 'months_served',
    }
    _SAFE_BUILTINS = {
        'abs': abs, 'round': round, 'min': min, 'max': max,
        'int': int, 'float': float,
    }

    @api.depends('formula')
    def _compute_formula_preview(self):
        for r in self:
            r.formula_preview = f"bonus_amount = {r.formula}"

    @api.depends('formula')
    def _compute_validation(self):
        for record in self:
            allowed = record._get_allowed_vars()
            ignored = set(record._SAFE_BUILTINS.keys())
            try:
                tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', record.formula)
                invalid = [t for t in tokens if t not in allowed and t not in ignored]
                if invalid:
                    record.validation_status = False
                    record.validation_error = _(
                        "Unknown variables: %s\nAvailable: %s"
                    ) % (', '.join(sorted(set(invalid))), ', '.join(sorted(allowed)))
                    continue
                sample = record._sample_values()
                ctx = {**sample, **record._SAFE_BUILTINS}
                result = eval(record.formula, {"__builtins__": {}}, ctx)
                if isinstance(result, (int, float)) and result == result:
                    record.validation_status = True
                    record.validation_error = False
                else:
                    record.validation_status = False
                    record.validation_error = _("Formula must evaluate to a finite number.")
            except Exception as exc:
                record.validation_status = False
                record.validation_error = str(exc)

    def _get_allowed_vars(self):
        self.ensure_one()
        return set(self._ALWAYS_AVAILABLE)

    def _sample_values(self):
        self.ensure_one()
        return {
            'score': 85.0,
            'eligibility': 0.75,
            'base_salary': 12000.0,
            'years_service': 5.0,
            'months_served': 6.0,
        }

    def action_validate_formula(self):
        """Validate the bonus formula"""
        self._compute_validation()
        if not self.validation_status:
            raise UserError(_("Formula validation failed:\n%s") % self.validation_error)
        sample = self._sample_values()
        ctx = {**sample, **self._SAFE_BUILTINS}
        result = eval(self.formula, {"__builtins__": {}}, ctx)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Formula valid'),
                'message': _('Sample result with salary=12,000, eligibility=0.75: %.2f') % result,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_sync_rating_tiers(self):
        """Manually sync rating eligibility lines"""
        self.ensure_one()
        self._sync_rating_eligibility_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rating Tiers Synced'),
                'message': _('Rating eligibility lines have been synchronized with the rating tiers.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def get_eligibility_for_rating(self, rating_id):
        """Get eligibility percentage for a specific rating from this engine"""
        line = self.rating_eligibility_ids.filtered(lambda l: l.rating_id.id == rating_id)
        return line.eligibility_percentage if line else 0.0

    def _sync_rating_eligibility_lines(self):
        """Synchronize rating eligibility lines with active rating definitions"""
        self.ensure_one()
        
        active_ratings = self.env['pms.rating.definition'].search([('active', '=', True)])
        
        if not active_ratings:
            _logger.warning(f"No active rating tiers found for engine {self.name}")
            return
        
        existing_ratings = self.rating_eligibility_ids.mapped('rating_id')
        
        new_lines = []
        for rating in active_ratings:
            if rating not in existing_ratings:
                new_lines.append({
                    'engine_id': self.id,
                    'rating_id': rating.id,
                    'eligibility_percentage': 0.0,
                })
        
        if new_lines:
            _logger.info(f"Creating {len(new_lines)} rating eligibility lines for engine {self.name}")
            self.env['pms.bonus.engine.rating.eligibility'].create(new_lines)
        
        for line in self.rating_eligibility_ids:
            if not line.rating_id.active:
                _logger.info(f"Removing eligibility line for inactive rating: {line.rating_name}")
                line.unlink()

    @api.model
    def default_get(self, fields_list):
        """Override default_get to create rating eligibility lines for new records"""
        result = super().default_get(fields_list)
        
        # If we're creating a new record, we need to ensure rating eligibility lines are created
        if 'rating_eligibility_ids' in fields_list or not self._context.get('active_id'):
            active_ratings = self.env['pms.rating.definition'].search([('active', '=', True)])
            if active_ratings:
                rating_eligibility_vals = []
                for rating in active_ratings:
                    rating_eligibility_vals.append({
                        'rating_id': rating.id,
                        'eligibility_percentage': 0.0,
                    })
                result['rating_eligibility_ids'] = [(0, 0, vals) for vals in rating_eligibility_vals]
        
        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Create bonus engine with immediate rating eligibility lines"""
        records = super().create(vals_list)
        
        for record in records:
            # Only create if no lines were provided in vals
            if not record.rating_eligibility_ids:
                active_ratings = self.env['pms.rating.definition'].search([('active', '=', True)])
                rating_eligibility_vals = []
                
                for rating in active_ratings:
                    existing = record.rating_eligibility_ids.filtered(lambda l: l.rating_id.id == rating.id)
                    if not existing:
                        rating_eligibility_vals.append({
                            'engine_id': record.id,
                            'rating_id': rating.id,
                            'eligibility_percentage': 0.0,
                        })
                
                if rating_eligibility_vals:
                    self.env['pms.bonus.engine.rating.eligibility'].create(rating_eligibility_vals)
        
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'rating_eligibility_ids' not in vals:
            for record in self:
                record._sync_rating_eligibility_lines()
        return result

    @api.onchange('name')
    def _onchange_name(self):
        """Ensure rating eligibility lines are shown when creating new record"""
        if not self.id and not self.rating_eligibility_ids:
            active_ratings = self.env['pms.rating.definition'].search([('active', '=', True)])
            if active_ratings:
                for rating in active_ratings:
                    self.rating_eligibility_ids = [(0, 0, {
                        'rating_id': rating.id,
                        'eligibility_percentage': 0.0,
                    })]

    def calculate_bonus(self, score, eligibility, base_salary=0.0, years_service=0.0, months_served=0.0):
        self.ensure_one()
        fallback = base_salary * eligibility * 0.15

        if not self.validation_status:
            _logger.warning("BonusEngine '%s' invalid formula — using fallback.", self.name)
            return fallback

        try:
            ctx = {
                'score': float(score),
                'eligibility': float(eligibility),
                'base_salary': float(base_salary),
                'years_service': float(years_service),
                'months_served': float(months_served),
                **self._SAFE_BUILTINS,
            }
            result = eval(self.formula, {"__builtins__": {}}, ctx)

            if self.use_tenure_weight and months_served > 0:
                tenure_factor = min(months_served, self.tenure_max_months) * self.tenure_weight
                result = result * (1 + tenure_factor)

            if self.use_cap and base_salary > 0:
                max_allowed = base_salary * (self.max_cap_percent / 100.0)
                result = min(result, max_allowed)

            if self.use_floor and result > 0:
                result = max(result, self.min_floor_amount)

            return float(result)
        except Exception as exc:
            _logger.error("BonusEngine.calculate_bonus error: %s", exc)
            return fallback


# ---------------------------------------------------------------------------
# Employee Bonus Fields
# ---------------------------------------------------------------------------
class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    
    latest_bonus_amount = fields.Monetary(
        string='Latest Bonus Amount',
        currency_field='currency_id',
        compute='_compute_latest_bonus',
        help='Most recent bonus amount calculated'
    )
    
    latest_bonus_date = fields.Date(
        string='Latest Bonus Date',
        compute='_compute_latest_bonus',
        help='Date of most recent bonus'
    )
    
    total_bonus_ytd = fields.Monetary(
        string='Total Bonus YTD',
        currency_field='currency_id',
        compute='_compute_bonus_totals',
        help='Total bonus amount for current year'
    )
    
    total_bonus_all_time = fields.Monetary(
        string='Total Bonus All Time',
        currency_field='currency_id',
        compute='_compute_bonus_totals',
        help='Total bonus amount all time'
    )
    
    bonus_count = fields.Integer(
        string='Bonus Count',
        compute='_compute_bonus_totals',
        help='Number of bonus payments received'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    
    def _compute_latest_bonus(self):
        for employee in self:
            if not employee.id:
                employee.latest_bonus_amount = 0.0
                employee.latest_bonus_date = False
                continue
                
            latest_line = self.env['pms.bonus.calculation.line'].search([
                ('employee_id', '=', employee.id),
                ('calculation_state', '=', 'calculated')
            ], order='calculation_date desc', limit=1)
            
            if latest_line:
                employee.latest_bonus_amount = latest_line.bonus_amount
                employee.latest_bonus_date = latest_line.calculation_date
            else:
                employee.latest_bonus_amount = 0.0
                employee.latest_bonus_date = False
    
    def _compute_bonus_totals(self):
        for employee in self:
            if not employee.id:
                employee.total_bonus_ytd = 0.0
                employee.total_bonus_all_time = 0.0
                employee.bonus_count = 0
                continue
                
            bonus_lines = self.env['pms.bonus.calculation.line'].search([
                ('employee_id', '=', employee.id),
                ('calculation_state', '=', 'calculated')
            ])
            
            current_year = fields.Date.today().year
            ytd_total = 0.0
            all_time_total = 0.0
            
            for line in bonus_lines:
                all_time_total += line.bonus_amount
                if line.calculation_date and line.calculation_date.year == current_year:
                    ytd_total += line.bonus_amount
            
            employee.total_bonus_ytd = ytd_total
            employee.total_bonus_all_time = all_time_total
            employee.bonus_count = len(bonus_lines)
    
    def action_view_my_bonus(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('My Bonus - %s') % self.name,
            'res_model': 'pms.bonus.calculation.line',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
            'target': 'current',
        }


# ---------------------------------------------------------------------------
# Bonus Calculation (Simplified - No state workflow)
# ---------------------------------------------------------------------------
class PMSBonusCalculation(models.Model):
    _name = 'pms.bonus.calculation'
    _description = 'Bonus Calculation'
    _rec_name = 'name'

    name = fields.Char(
        string='Calculation Name', required=True,
        default=lambda self: _('New Calculation'),
    )
    date = fields.Date(string='Date', required=True, default=fields.Date.today)
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    bonus_engine_id = fields.Many2one(
        'pms.bonus.engine', string='Bonus Engine', required=True,
        domain="[('active', '=', True)]",
    )
    cycle_id = fields.Many2one(
        'pms.cycle', string='Performance Cycle',
    )
    
    auto_calculate = fields.Boolean(string='Auto-Calculate', default=True)
    auto_calculated_on = fields.Datetime(string='Auto-Calculated On', readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
    ], string='Status', default='draft')

    line_ids = fields.One2many(
        'pms.bonus.calculation.line', 'calculation_id', string='Lines',
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )
    
    employee_ids = fields.Many2many(
        'hr.employee', 
        string='Selected Employees',
        help='Select specific employees to calculate bonus.'
    )
    employee_count = fields.Integer(
        string='Employee Count', 
        compute='_compute_employee_count'
    )
    selection_type = fields.Selection([
        ('all', 'All Eligible Employees'),
        ('selected', 'Select Specific Employees')
    ], string='Employee Selection', default='all')
    
    total_bonus_amount = fields.Monetary(
        string='Total Bonus Amount',
        compute='_compute_totals',
        currency_field='currency_id'
    )
    eligible_employee_count = fields.Integer(
        string='Eligible Employees',
        compute='_compute_totals'
    )
    
    @api.depends('employee_ids')
    def _compute_employee_count(self):
        for record in self:
            record.employee_count = len(record.employee_ids)
    
    @api.depends('line_ids.bonus_amount')
    def _compute_totals(self):
        for record in self:
            record.total_bonus_amount = sum(record.line_ids.mapped('bonus_amount'))
            record.eligible_employee_count = len(record.line_ids)
    
    def action_load_cycle_employees(self):
        """Load employees from the selected cycle with completed appraisals"""
        self.ensure_one()
        if not self.cycle_id:
            raise UserError(_("Please select a performance cycle first."))
        
        appraisals = self.env['pms.appraisal'].search([
            ('cycle_id', '=', self.cycle_id.id),
            ('state', '=', 'appraisal_approved')
        ])
        
        if not appraisals:
            all_appraisals = self.env['pms.appraisal'].search([
                ('cycle_id', '=', self.cycle_id.id),
            ])
            
            if all_appraisals:
                unique_states = set(all_appraisals.mapped('state'))
                raise UserError(_(
                    "No completed appraisals found in cycle '%s'.\n\n"
                    "Found appraisals with states: %s\n\n"
                    "Bonus calculation requires appraisals with state 'appraisal_approved'.\n"
                    "Please complete the appraisals first."
                ) % (self.cycle_id.name, list(unique_states)))
            else:
                raise UserError(_(
                    "No appraisals found in cycle '%s'.\n\n"
                    "Please create and complete appraisals for employees in this cycle first."
                ) % self.cycle_id.name)
        
        employees = appraisals.mapped('employee_id')
        
        self.write({
            'employee_ids': [(6, 0, employees.ids)],
            'selection_type': 'selected'
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Employees Loaded'),
                'message': _('Loaded %s employees with completed appraisals from cycle "%s".') % (
                    len(employees), self.cycle_id.name
                ),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _get_eligible_employees(self):
        """Get eligible employees based on selection type"""
        self.ensure_one()
        
        if self.selection_type == 'selected' and self.employee_ids:
            employees = self.employee_ids
        else:
            appraisals = self.env['pms.appraisal'].search([
                ('cycle_id', '=', self.cycle_id.id),
                ('state', '=', 'appraisal_approved')
            ])
            employees = appraisals.mapped('employee_id')
        
        return employees
    
    def _get_employee_appraisal(self, employee):
        """Get employee's completed appraisal for the cycle"""
        return self.env['pms.appraisal'].search([
            ('employee_id', '=', employee.id),
            ('cycle_id', '=', self.cycle_id.id),
            ('state', '=', 'appraisal_approved')
        ], limit=1)

    def _get_employee_wage(self, employee):
        if 'contract_wage' in self.env['hr.employee']._fields:
            try:
                wage = employee.sudo().contract_wage
                return float(wage) if wage else 0.0
            except Exception as e:
                _logger.warning("contract_wage read failed for '%s': %s", employee.name, e)
                return 0.0

        if 'hr.contract' not in self.env.registry:
            return 0.0
        Contract = self.env['hr.contract'].sudo()
        contract = Contract.search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('company_id', '=', employee.company_id.id),
        ], order='date_start desc', limit=1)
        if not contract:
            contract = Contract.search([
                ('employee_id', '=', employee.id),
                ('company_id', '=', employee.company_id.id),
            ], order='date_start desc', limit=1)
        return float(contract.wage or 0.0) if contract else 0.0

    def _get_years_service(self, employee):
        ref = (
            getattr(employee, 'date_of_join', None)
            or getattr(employee, 'joining_date', None)
            or (employee.create_date.date() if employee.create_date else None)
        )
        if ref:
            return max(0.0, float((fields.Date.today() - ref).days) / 365.25)
        return 0.0

    def _calculate_months_served(self, cycle):
        """
        Calculate months served based on the difference between cycle end date and cycle start date.
        This returns the total duration of the cycle in months.
        
        For annual cycle: returns 12 months
        For semi-annual cycle: returns 6 months  
        For probation cycle: returns 3 months
        
        Args:
            cycle: The PMS cycle object (pms.cycle)
        
        Returns:
            float: Total months of the cycle (12, 6, or 3)
        """
        _logger.info("=" * 60)
        _logger.info("CALCULATING MONTHS SERVED (TOTAL CYCLE DURATION)")
        
        if not cycle:
            _logger.warning("No cycle provided")
            return 0.0
        
        # Get cycle type and determine months
        cycle_type = cycle.cycle_type
        if cycle_type == 'annual':
            months_served = 12
        elif cycle_type == 'semi_annual':
            months_served = 6
        elif cycle_type == 'probation':
            months_served = 3
        else:
            months_served = 12
        
        _logger.info(f"Cycle: {cycle.name}")
        _logger.info(f"Cycle Type: {cycle_type}")
        _logger.info(f"Months Served (Total Cycle Duration): {months_served} months")
        _logger.info("=" * 60)
        
        return float(months_served)

    def _run_calculation(self):
        """Run calculation based on employee selection"""
        self.ensure_one()
        engine = self.bonus_engine_id
        
        if not engine:
            raise UserError(_("Please select a bonus engine."))
        
        self.line_ids.unlink()
        
        employees = self._get_eligible_employees()
        
        if not employees:
            return 0, 0, ['No eligible employees found based on selection criteria.']
        
        calculated, skipped, skipped_list = 0, 0, []
        
        # Get the cycle object
        cycle = self.cycle_id
        
        if not cycle:
            _logger.warning("No cycle selected for bonus calculation!")
            return 0, 0, ['No cycle selected for bonus calculation.']
        
        # Calculate months served based on cycle type (total cycle duration)
        months_served = self._calculate_months_served(cycle)
        
        _logger.info("=" * 60)
        _logger.info("BONUS CALCULATION DEBUG INFO")
        _logger.info(f"Calculation ID: {self.id}")
        _logger.info(f"Calculation Name: {self.name}")
        _logger.info(f"Calculation Date: {self.date}")
        _logger.info(f"Cycle: {cycle.name}")
        _logger.info(f"Cycle Type: {cycle.cycle_type}")
        _logger.info(f"Cycle Start Date: {cycle.start_date}")
        _logger.info(f"Cycle End Date: {cycle.end_date}")
        _logger.info(f"Months Served (Total Cycle Duration): {months_served}")
        _logger.info(f"Number of employees to process: {len(employees)}")
        _logger.info("=" * 60)
        
        for employee in employees:
            appraisal = self._get_employee_appraisal(employee)
            if not appraisal:
                skipped += 1
                skipped_list.append(f"{employee.name} (no completed appraisal found)")
                continue
            
            score = appraisal.final_appraisal_score or 0.0
            
            if score <= 0:
                skipped += 1
                skipped_list.append(f"{employee.name} (score is 0 or unset)")
                continue
            
            rating = self.env['pms.rating.definition'].get_rating(score)
            
            if rating:
                eligibility = engine.get_eligibility_for_rating(rating.id) / 100.0
                rating_id = rating.id
                eligibility_pct = engine.get_eligibility_for_rating(rating.id)
            else:
                eligibility = 0.0
                rating_id = False
                eligibility_pct = 0.0
                skipped += 1
                skipped_list.append(f"{employee.name} (no rating tier found for score {score})")
                continue
            
            if eligibility <= 0:
                skipped += 1
                skipped_list.append(f"{employee.name} ({eligibility_pct}% eligibility)")
                continue
            
            base_salary = self._get_employee_wage(employee)
            years_service = self._get_years_service(employee)
            
            _logger.info(f"Processing Employee: {employee.name}")
            _logger.info(f"  - Score: {score}")
            _logger.info(f"  - Rating: {rating.name if rating else 'None'}")
            _logger.info(f"  - Eligibility %: {eligibility_pct}%")
            _logger.info(f"  - Eligibility ratio: {eligibility}")
            _logger.info(f"  - Base Salary: {base_salary}")
            _logger.info(f"  - Years Service: {years_service}")
            _logger.info(f"  - Months Served (Cycle Duration): {months_served}")
            
            bonus_amount = engine.calculate_bonus(
                score=score,
                eligibility=eligibility,
                base_salary=base_salary,
                years_service=years_service,
                months_served=months_served,
            )
            
            _logger.info(f"  - Bonus Amount: {bonus_amount}")
            _logger.info("-" * 40)
            
            self.env['pms.bonus.calculation.line'].create({
                'calculation_id': self.id,
                'employee_id': employee.id,
                'appraisal_id': appraisal.id,
                'cycle_id': appraisal.cycle_id.id if appraisal.cycle_id else False,
                'score': score,
                'rating_id': rating_id,
                'eligibility_percentage': eligibility_pct,
                'base_salary': base_salary,
                'years_service': years_service,
                'months_served': months_served,
                'bonus_amount': bonus_amount,
            })
            calculated += 1
        
        _logger.info(f"Calculation completed: {calculated} calculated, {skipped} skipped")
        return calculated, skipped, skipped_list

    def action_calculate(self):
        """Run calculation - simplified without state workflow"""
        self.ensure_one()
        
        if not self.bonus_engine_id:
            raise UserError(_("Please select a bonus formula engine."))
        
        if not self.cycle_id:
            raise UserError(_("Please select a performance cycle."))
        
        calculated, skipped, skipped_list = self._run_calculation()

        if calculated == 0:
            names = '\n'.join(skipped_list[:10])
            extra = (
                _('\n… and %s more') % (len(skipped_list) - 10)
                if len(skipped_list) > 10 else ''
            )
            raise UserError(
                _('No eligible employees found.\n\nSkipped:\n%s%s') % (names, extra)
            )

        self.state = 'calculated'
        
        # Calculate months served for display
        months_served = self._calculate_months_served(self.cycle_id)
        
        # Calculate cycle info for display
        cycle_type_names = {
            'annual': 'Annual (12 months)',
            'semi_annual': 'Semi-Annual (6 months)',
            'probation': 'Probation (3 months)'
        }
        cycle_type_display = cycle_type_names.get(self.cycle_id.cycle_type, 'Unknown')
        
        # Show summary in notification
        summary_msg = _(
            '✅ %s employees processed · ⏭️ %s skipped\n\n'
            'Cycle Information:\n'
            '• Cycle: %s\n'
            '• Type: %s\n'
            '• Start Date: %s\n'
            '• End Date: %s\n'
            '• Total Months Served: %s months\n\n'
            '💡 Months served is calculated as the total duration of the cycle.'
        ) % (
            calculated, 
            skipped,
            self.cycle_id.name,
            cycle_type_display,
            self.cycle_id.start_date.strftime('%Y-%m-%d') if self.cycle_id.start_date else 'Not set',
            self.cycle_id.end_date.strftime('%Y-%m-%d') if self.cycle_id.end_date else 'Not set',
            months_served
        )
        
        # Return action to reload the form view with the calculated state
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'flags': {'form': {'action_buttons': True}},
            'context': self.env.context,
        }

    def action_export_to_payroll(self):
        """Export to payroll - available after calculation"""
        self.ensure_one()
        if self.state != 'calculated':
            raise UserError(_('Please run the calculation first before exporting.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Export to Payroll'),
            'res_model': 'pms.bonus.payroll.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_calculation_id': self.id},
        }


# ---------------------------------------------------------------------------
# Bonus Calculation Line
# ---------------------------------------------------------------------------
class PMSBonusCalculationLine(models.Model):
    _name = 'pms.bonus.calculation.line'
    _description = 'Bonus Calculation Line'
    _order = 'calculation_date desc, bonus_amount desc'
    _rec_name = 'employee_id'

    calculation_id = fields.Many2one(
        'pms.bonus.calculation', string='Calculation',
        required=True, ondelete='cascade',
    )
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    appraisal_id = fields.Many2one('pms.appraisal', string='Appraisal')
    cycle_id = fields.Many2one(
        'pms.cycle', string='Performance Cycle',
        related='appraisal_id.cycle_id', store=True,
    )
    score = fields.Float(string='Appraisal Score', digits=(5, 2))
    rating_id = fields.Many2one('pms.rating.definition', string='Rating Tier')

    eligibility_percentage = fields.Float(string='Eligibility %', digits=(5, 2))
    base_salary = fields.Monetary(string='Base Salary', currency_field='currency_id')
    years_service = fields.Float(string='Tenure (yrs)', digits=(5, 2))
    months_served = fields.Float(string='Months Served', digits=(5, 2))
    bonus_amount = fields.Monetary(string='Bonus Amount', currency_field='currency_id')

    currency_id = fields.Many2one(
        'res.currency', related='calculation_id.currency_id', store=True,
    )
    company_id = fields.Many2one(
        'res.company', related='calculation_id.company_id', store=True,
    )
    notes = fields.Text(string='Notes')

    calculation_date = fields.Date(
        string='Calculation Date',
        related='calculation_id.date',
        store=True,
    )
    
    calculation_state = fields.Selection(
        string='Calculation State',
        related='calculation_id.state',
        store=True,
    )
    
    calculation_name = fields.Char(
        string='Calculation Name',
        related='calculation_id.name',
        store=True,
    )
    
    bonus_engine_name = fields.Char(
        string='Bonus Engine',
        related='calculation_id.bonus_engine_id.name',
        store=True,
    )
    
    def action_view_bonus_details(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bonus Details'),
            'res_model': 'pms.bonus.calculation.line',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }


# ---------------------------------------------------------------------------
# Payroll Export Wizard
# ---------------------------------------------------------------------------
class PMSBonusPayrollExportWizard(models.TransientModel):
    _name = 'pms.bonus.payroll.export.wizard'
    _description = 'Bonus Payroll Export Wizard'

    calculation_id = fields.Many2one(
        'pms.bonus.calculation', string='Bonus Calculation', required=True,
    )
    export_format = fields.Selection([
        ('csv', 'CSV'),
        ('text', 'Text'),
    ], string='Export Format', default='csv')

    def action_export(self):
        self.ensure_one()
        return self._export_csv() if self.export_format == 'csv' else self._export_text()

    def _export_csv(self):
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        headers = [
            'Employee', 'Department', 'Job',
            'Appraisal Score', 'Rating Tier', 'Eligibility %',
            'Tenure (yrs)', 'Months Served', 'Base Salary', 'Bonus Amount', 'Currency',
        ]
        writer.writerow(headers)
        for line in self.calculation_id.line_ids:
            row = [
                line.employee_id.name,
                line.employee_id.department_id.name if line.employee_id.department_id else '',
                line.employee_id.job_id.name if line.employee_id.job_id else '',
                line.score,
                line.rating_id.name if line.rating_id else '',
                line.eligibility_percentage,
                round(line.years_service, 1),
                round(line.months_served, 1),
                line.base_salary,
                line.bonus_amount,
                self.calculation_id.currency_id.name,
            ]
            writer.writerow(row)
        attachment = self.env['ir.attachment'].create({
            'name': f'bonus_{self.calculation_id.name}_{fields.Date.today()}.csv',
            'type': 'binary',
            'raw': output.getvalue().encode('utf-8-sig'),
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def _export_text(self):
        calc = self.calculation_id
        sym = calc.currency_id.symbol
        lines = [
            '=' * 70,
            'BONUS PAYROLL EXPORT',
            f'Calculation : {calc.name}',
            f'Date        : {calc.date}',
            '=' * 70, '',
            'EMPLOYEE DETAILS:',
            '-' * 70,
        ]
        for line in calc.line_ids:
            emp = line.employee_id
            lines += [
                f"\n{emp.name}",
                f"  Department : {emp.department_id.name if emp.department_id else 'N/A'}",
                f"  Score      : {line.score:.1f}",
                f"  Rating     : {line.rating_id.name if line.rating_id else 'N/A'}",
                f"  Eligibility: {line.eligibility_percentage:.0f}%",
                f"  Tenure     : {line.years_service:.1f} yrs",
                f"  Months     : {line.months_served:.1f} months",
                f"  Base salary: {sym} {line.base_salary:,.2f}",
                f"  Bonus      : {sym} {line.bonus_amount:,.2f}",
            ]
        lines += ['', '=' * 70]
        attachment = self.env['ir.attachment'].create({
            'name': f'bonus_{calc.name}_{fields.Date.today()}.txt',
            'type': 'binary',
            'raw': '\n'.join(lines).encode('utf-8'),
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }