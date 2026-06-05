from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import re
import logging
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


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
        default='base_salary * eligibility * months_served',
        help=(
            'Python expression. Result is the bonus amount in local currency.\n\n'
            'Available variables:\n'
            '  score          – appraisal score (0–100)\n'
            '  eligibility    – tier eligibility as a ratio (0–1)\n'
            '  base_salary    – employee wage\n'
            '  years_service  – tenure in years\n'
            '  months_served  – months served in current cycle (12 for annual, 6 for semi-annual, 3 for probation)\n\n'
            'Example formulas:\n'
            '  base_salary * eligibility * months_served\n'
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
            'months_served': 12.0,
        }

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        return result

    def action_validate_formula(self):
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
        self.ensure_one()
        active_ratings = self.env['pms.rating.definition'].search([('active', '=', True)])

        if not active_ratings:
            raise UserError(_('No active rating tiers found. Please create rating tiers first.'))

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
        line = self.rating_eligibility_ids.filtered(lambda l: l.rating_id.id == rating_id)
        return line.eligibility_percentage if line else 0.0

    def _sync_rating_eligibility_lines(self):
        self.ensure_one()

        if not self.id:
            _logger.warning("Cannot sync rating eligibility lines for unsaved record")
            return

        active_ratings = self.env['pms.rating.definition'].search([('active', '=', True)])

        if not active_ratings:
            _logger.warning(f"No active rating tiers found for engine {self.name}")
            return

        existing_lines = {line.rating_id.id: line for line in self.rating_eligibility_ids}
        current_rating_ids = set(active_ratings.ids)
        existing_rating_ids = set(existing_lines.keys())

        for rating_id in current_rating_ids - existing_rating_ids:
            try:
                self.env['pms.bonus.engine.rating.eligibility'].create({
                    'engine_id': self.id,
                    'rating_id': rating_id,
                    'eligibility_percentage': 0.0,
                })
                _logger.info(f"Created eligibility line for rating ID {rating_id}")
            except Exception as e:
                _logger.error(f"Error creating eligibility line for rating ID {rating_id}: {e}")

        for rating_id in existing_rating_ids - current_rating_ids:
            if rating_id in existing_lines:
                _logger.info(f"Removing eligibility line for inactive rating ID {rating_id}")
                existing_lines[rating_id].unlink()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record in records:
            try:
                record._sync_rating_eligibility_lines()
            except Exception as e:
                _logger.error(f"Error syncing rating eligibility lines for engine {record.name}: {e}")

        return records

    def write(self, vals):
        result = super().write(vals)

        if 'rating_eligibility_ids' not in vals:
            for record in self:
                try:
                    record._sync_rating_eligibility_lines()
                except Exception as e:
                    _logger.error(f"Error syncing rating eligibility lines for engine {record.name}: {e}")

        return result

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
            return float(result)
        except Exception as exc:
            _logger.error("BonusEngine.calculate_bonus error: %s", exc)
            return fallback


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    pass


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
        'pms.bonus.engine', string='Bonus Formula', required=True,
        domain="[('active', '=', True)]",
    )
    cycle_id = fields.Many2one(
        'pms.cycle', string='Performance Cycle', required=True,
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

    total_bonus_amount = fields.Monetary(
        string='Total Bonus Amount',
        compute='_compute_totals',
        currency_field='currency_id'
    )
    eligible_employee_count = fields.Integer(
        string='Eligible Employees',
        compute='_compute_totals'
    )

    @api.depends('line_ids.bonus_amount')
    def _compute_totals(self):
        for record in self:
            record.total_bonus_amount = sum(record.line_ids.mapped('bonus_amount'))
            record.eligible_employee_count = len(record.line_ids)

    def _get_eligible_employees(self):
        self.ensure_one()

        # Check if cycle is probation type - if yes, return empty
        if self.cycle_id.cycle_type == 'probation':
            _logger.info(f"Cycle {self.cycle_id.name} is probation type - no employees eligible")
            return self.env['hr.employee']

        appraisals = self.env['pms.appraisal'].search([
            ('cycle_id', '=', self.cycle_id.id),
            ('state', '=', 'appraisal_approved')
        ])
        employees = appraisals.mapped('employee_id')

        return employees

    def _get_employee_appraisal(self, employee):
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
        _logger.info("=" * 60)
        _logger.info("CALCULATING MONTHS SERVED (TOTAL CYCLE DURATION)")

        if not cycle:
            _logger.warning("No cycle provided")
            return 0.0

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
        self.ensure_one()
        engine = self.bonus_engine_id

        if not engine:
            raise UserError(_("Please select a bonus engine."))

        self.line_ids.unlink()

        employees = self._get_eligible_employees()

        if not employees:
            return 0, 0, ['No eligible employees found based on selection criteria.']

        calculated, skipped, skipped_list = 0, 0, []

        cycle = self.cycle_id

        if not cycle:
            _logger.warning("No cycle selected for bonus calculation!")
            return 0, 0, ['No cycle selected for bonus calculation.']

        # Check if cycle is probation type - if yes, skip all calculations
        if cycle.cycle_type == 'probation':
            _logger.info(f"Cycle {cycle.name} is probation type - no bonuses calculated")
            return 0, len(employees), [f"Cycle '{cycle.name}' is a probation cycle - no bonuses eligible"]

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

            if appraisal.final_appraisal_score is False or appraisal.final_appraisal_score is None or score < 0:
                skipped += 1
                skipped_list.append(f"{employee.name} (score is unset or negative)")
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
        self.ensure_one()

        if not self.bonus_engine_id:
            raise UserError(_("Please select a bonus formula engine."))

        if not self.cycle_id:
            raise UserError(_("Please select a performance cycle."))

        # Check if cycle is probation type
        if self.cycle_id.cycle_type == 'probation':
            raise UserError(_(
                "Cannot calculate bonuses for probation cycles.\n"
                "Employees in probation periods are not eligible for bonus calculations."
            ))

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

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
            'context': dict(self.env.context, reload_on_create=True, reload_on_write=True),
        }

    def action_recalculate(self):
        """Re-run the bonus formula on existing lines, preserving manual edits."""
        self.ensure_one()

        if not self.bonus_engine_id:
            raise UserError(_("Please select a bonus formula engine."))

        if not self.cycle_id:
            raise UserError(_("Please select a performance cycle."))

        # Check if cycle is probation type
        if self.cycle_id.cycle_type == 'probation':
            raise UserError(_(
                "Cannot calculate bonuses for probation cycles.\n"
                "Employees in probation periods are not eligible for bonus calculations."
            ))

        # If no lines exist yet, fall back to a full fresh calculation
        if not self.line_ids:
            return self.action_calculate()

        engine = self.bonus_engine_id
        recalculated = 0

        for line in self.line_ids:
            try:
                bonus_amount = engine.calculate_bonus(
                    score=line.score,
                    eligibility=line.eligibility_percentage / 100.0,
                    base_salary=line.base_salary,
                    years_service=line.years_service,
                    months_served=line.months_served,
                )
                line.bonus_amount = bonus_amount
                recalculated += 1

                _logger.info(
                    "Recalculated bonus for '%s': score=%s, eligibility=%s%%, "
                    "base_salary=%s, months_served=%s => bonus=%s",
                    line.employee_id.name,
                    line.score,
                    line.eligibility_percentage,
                    line.base_salary,
                    line.months_served,
                    bonus_amount,
                )
            except Exception as e:
                _logger.error(
                    "Recalculate failed for employee '%s': %s",
                    line.employee_id.name, e,
                )

        self.state = 'calculated'

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
            'context': dict(self.env.context, reload_on_create=True, reload_on_write=True),
        }

    def action_export_to_payroll(self):
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

    @api.model
    def _cron_auto_calculate_pending(self):
        """Cron job: auto-calculate all draft calculations with auto_calculate enabled."""
        pending = self.search([
            ('state', '=', 'draft'),
            ('auto_calculate', '=', True),
        ])
        for record in pending:
            try:
                # Skip probation cycles
                if record.cycle_id and record.cycle_id.cycle_type == 'probation':
                    _logger.info(
                        "Auto-calculation skipped for '%s': cycle is probation type.", record.name
                    )
                    continue

                calculated, skipped, _ = record._run_calculation()
                if calculated > 0:
                    record.state = 'calculated'
                    record.auto_calculated_on = fields.Datetime.now()
                    _logger.info(
                        "Auto-calculated bonus '%s': %s employees, %s skipped.",
                        record.name, calculated, skipped,
                    )
                else:
                    _logger.warning(
                        "Auto-calculation skipped for '%s': no eligible employees.", record.name
                    )
            except Exception as exc:
                _logger.error(
                    "Auto-calculation failed for '%s': %s", record.name, exc
                )


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

    bonus_percentage_of_salary = fields.Float(
        string='% of Salary',
        compute='_compute_bonus_pct',
        store=True,
        digits=(5, 2),
    )

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

    @api.depends('bonus_amount', 'base_salary')
    def _compute_bonus_pct(self):
        for r in self:
            r.bonus_percentage_of_salary = (
                (r.bonus_amount / r.base_salary * 100) if r.base_salary > 0 else 0.0
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
    include_analytics = fields.Boolean(string='Include % of Salary', default=False)

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
            'Months Served', 'Base Salary', 'Bonus Amount', 'Currency',
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