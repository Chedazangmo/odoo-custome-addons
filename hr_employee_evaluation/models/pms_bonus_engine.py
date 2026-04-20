from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re


# ─────────────────────────────────────────────────────────────────────────────
# 1. RATING DEFINITION
#    Master list of rating tiers (Outstanding, Commendable, Good …).
#    Shared company-wide; edited from inside the Bonus Engine form.
# ─────────────────────────────────────────────────────────────────────────────

class PMSRatingDefinition(models.Model):
    _name = 'pms.rating.definition'
    _description = 'PMS Rating Definition'
    _order = 'sequence, name'

    name = fields.Char(string='Rating Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    code = fields.Char(
        string='Code', required=True,
        help='Short unique code used in bonus mapping, e.g. OUTSTANDING'
    )
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company, required=True
    )

    _sql_constraints = [
        ('code_company_unique', 'UNIQUE(code, company_id)',
         'Rating code must be unique per company.')
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 2. WEIGHTAGE CONFIGURATION
#    Defines how component scores combine into a final score.
#    Linked to a Bonus Engine; its lines are edited from inside the engine form.
# ─────────────────────────────────────────────────────────────────────────────

class PMSWeightageConfigLine(models.Model):
    _name = 'pms.weightage.config.line'
    _description = 'PMS Weightage Configuration Line'
    _order = 'sequence'

    config_id = fields.Many2one(
        'pms.weightage.config', string='Weightage Config',
        required=True, ondelete='cascade', index=True
    )
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Component Name', required=True)
    code = fields.Char(
        string='Code', required=True,
        help='Token usable in bonus formula, e.g. TARGET_SCORE'
    )
    weight = fields.Float(string='Weight (%)', required=True, default=0.0)
    description = fields.Text(string='Description')

    @api.constrains('weight')
    def _check_weight(self):
        for rec in self:
            if rec.weight < 0 or rec.weight > 100:
                raise ValidationError(
                    f'Weight must be between 0 and 100. Got: {rec.weight}'
                )


class PMSWeightageConfig(models.Model):
    _name = 'pms.weightage.config'
    _description = 'PMS Weightage Configuration'
    _order = 'is_default desc, name'

    name = fields.Char(string='Configuration Name', required=True)
    is_default = fields.Boolean(string='Set as Default', default=False)
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company, required=True
    )
    line_ids = fields.One2many(
        'pms.weightage.config.line', 'config_id',
        string='Weightage Lines', copy=True
    )
    total_weight = fields.Float(
        string='Total Weight (%)',
        compute='_compute_total_weight', store=True
    )

    @api.depends('line_ids.weight')
    def _compute_total_weight(self):
        for rec in self:
            rec.total_weight = sum(rec.line_ids.mapped('weight'))

    @api.constrains('line_ids')
    def _check_total_weight(self):
        for rec in self:
            if rec.line_ids and abs(rec.total_weight - 100.0) > 0.01:
                raise ValidationError(
                    f'Total weightage must equal 100%. '
                    f'Currently: {rec.total_weight:.2f}%'
                )

    @api.constrains('is_default', 'company_id')
    def _check_single_default(self):
        for record in self:
            if record.is_default:
                existing = self.search([
                    ('is_default', '=', True),
                    ('company_id', '=', record.company_id.id),
                    ('id', '!=', record.id),
                ])
                if existing:
                    raise ValidationError(
                        f'"{existing[0].name}" is already the default '
                        f'weightage config. Please unset it first.'
                    )

    def action_set_default(self):
        self.ensure_one()
        self.search([
            ('is_default', '=', True),
            ('company_id', '=', self.company_id.id),
            ('id', '!=', self.id),
        ]).write({'is_default': False})
        self.write({'is_default': True})


# ─────────────────────────────────────────────────────────────────────────────
# 3. BONUS FORMULA TOKEN
#    Child of Bonus Engine (One2many). No separate menu.
#    Each row defines a {TOKEN_NAME} usable in the formula.
# ─────────────────────────────────────────────────────────────────────────────

class PMSBonusFormulaField(models.Model):
    _name = 'pms.bonus.formula.field'
    _description = 'PMS Bonus Formula Token'
    _order = 'token_name'

    bonus_engine_id = fields.Many2one(
        'pms.bonus.engine', string='Bonus Engine',
        required=True, ondelete='cascade', index=True
    )
    name = fields.Char(string='Label', required=True)
    token_name = fields.Char(
        string='Token Name', required=True,
        help='Referenced as {TOKEN_NAME} in the formula'
    )
    field_type = fields.Selection([
        ('numeric', 'Numeric field'),
        ('pool', 'Bonus pool amount'),
        ('constant', 'Constant value'),
    ], string='Type', required=True, default='numeric')
    source_model = fields.Char(
        string='Model', help='e.g. hr.appraisal'
    )
    source_field = fields.Char(
        string='Field', help='e.g. final_score'
    )
    constant_value = fields.Float(string='Constant Value')
    description = fields.Text(string='Notes')

    @api.constrains('token_name')
    def _check_token_name(self):
        pattern = re.compile(r'^[A-Z][A-Z0-9_]*$')
        for rec in self:
            if not pattern.match(rec.token_name):
                raise ValidationError(
                    f'Token "{rec.token_name}" must be uppercase letters, '
                    f'numbers and underscores only, starting with a letter.'
                )


# ─────────────────────────────────────────────────────────────────────────────
# 4. BONUS MAPPING RULE
#    Rating → Eligibility %.  Child of Bonus Engine.
# ─────────────────────────────────────────────────────────────────────────────

class PMSBonusMappingRule(models.Model):
    _name = 'pms.bonus.mapping.rule'
    _description = 'PMS Bonus Mapping Rule'
    _order = 'sequence'

    sequence = fields.Integer(string='Sequence', default=10)
    bonus_engine_id = fields.Many2one(
        'pms.bonus.engine', string='Bonus Engine',
        required=True, ondelete='cascade', index=True
    )
    rating_id = fields.Many2one(
        'pms.rating.definition', string='Rating',
        required=True, ondelete='restrict'
    )
    eligibility_pct = fields.Float(
        string='Eligibility %', required=True, default=0.0
    )
    notes = fields.Text(string='Notes')

    @api.constrains('eligibility_pct')
    def _check_eligibility(self):
        for rec in self:
            if rec.eligibility_pct < 0 or rec.eligibility_pct > 100:
                raise ValidationError(
                    f'Eligibility % must be between 0 and 100. '
                    f'Got: {rec.eligibility_pct}'
                )

    @api.constrains('rating_id', 'bonus_engine_id')
    def _check_unique_rating_per_engine(self):
        for rec in self:
            duplicate = self.search([
                ('bonus_engine_id', '=', rec.bonus_engine_id.id),
                ('rating_id', '=', rec.rating_id.id),
                ('id', '!=', rec.id),
            ])
            if duplicate:
                raise ValidationError(
                    f'Rating "{rec.rating_id.name}" already has a '
                    f'mapping rule in this engine.'
                )


# ─────────────────────────────────────────────────────────────────────────────
# 5. BONUS ENGINE  (main model)
#    One record per company/period. Opened from a SINGLE menu item:
#    Configuration > Bonus Calculation
#
#    Exposes related fields so the form can inline-edit:
#      - rating_definition_ids  → company's rating tiers (Tab 1)
#      - weightage_line_ids     → lines of the linked weightage config (Tab 2)
#      - weightage_total_weight → total % of the linked config (Tab 2)
# ─────────────────────────────────────────────────────────────────────────────

class PMSBonusEngine(models.Model):
    _name = 'pms.bonus.engine'
    _description = 'PMS Bonus Calculation Engine'
    _order = 'is_default desc, name'

    name = fields.Char(string='Engine Name', required=True)
    is_default = fields.Boolean(string='Set as Default', default=False)
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company, required=True
    )

    # ── Linked configs ────────────────────────────────────────────────
    scoring_engine_id = fields.Many2one(
        'pms.scoring.engine', string='Scoring Engine',
        ondelete='set null',
        help='Maps a numeric final score to a rating label'
    )
    weightage_config_id = fields.Many2one(
        'pms.weightage.config', string='Weightage Configuration',
        ondelete='set null',
        help='Defines component weights that produce the final score'
    )

    # ── Tab 1 proxy: rating definitions for this company ─────────────
    # We use a computed Many2many so the user can manage all company
    # ratings directly from this form without a separate menu.
    rating_definition_ids = fields.Many2many(
        'pms.rating.definition',
        compute='_compute_rating_definition_ids',
        inverse='_inverse_rating_definition_ids',
        string='Rating Definitions',
    )

    @api.depends('company_id')
    def _compute_rating_definition_ids(self):
        for rec in self:
            rec.rating_definition_ids = self.env[
                'pms.rating.definition'
            ].search([('company_id', '=', rec.company_id.id)])

    def _inverse_rating_definition_ids(self):
        # Changes are written directly to pms.rating.definition records;
        # the Many2many widget handles create/unlink automatically.
        pass

    # ── Tab 2 proxy: weightage config lines ───────────────────────────
    weightage_line_ids = fields.One2many(
        related='weightage_config_id.line_ids',
        string='Weightage Components',
        readonly=False,
    )
    weightage_total_weight = fields.Float(
        related='weightage_config_id.total_weight',
        string='Total Weight (%)',
        readonly=True,
    )

    # ── Formula tokens (Tab 4, Step 1) ───────────────────────────────
    formula_field_ids = fields.One2many(
        'pms.bonus.formula.field', 'bonus_engine_id',
        string='Formula Tokens', copy=True
    )
    formula_token_preview = fields.Text(
        string='Token Reference',
        compute='_compute_formula_token_preview'
    )

    # ── Formula (Tab 4, Step 3) ───────────────────────────────────────
    formula = fields.Text(
        string='Bonus Formula',
        required=True,
        default='{FINAL_SCORE} * {ELIGIBILITY_PCT} * {BONUS_POOL} / 100',
        help=(
            'Use {TOKEN_NAME} placeholders.\n'
            'Built-in tokens always available:\n'
            '  {ELIGIBILITY_PCT} — from the rating mapping rule\n'
            '  {RATING_CODE}     — employee rating code\n'
            'Allowed operators: + - * / ( )'
        )
    )

    # ── Mapping rules (Tab 3) ─────────────────────────────────────────
    mapping_rule_ids = fields.One2many(
        'pms.bonus.mapping.rule', 'bonus_engine_id',
        string='Rating → Eligibility Rules', copy=True
    )
    mapping_rule_count = fields.Integer(
        compute='_compute_mapping_rule_count'
    )

    description = fields.Text(string='Notes')

    # ── Computes ──────────────────────────────────────────────────────

    @api.depends('mapping_rule_ids')
    def _compute_mapping_rule_count(self):
        for rec in self:
            rec.mapping_rule_count = len(rec.mapping_rule_ids)

    @api.depends(
        'formula_field_ids',
        'formula_field_ids.token_name',
        'formula_field_ids.name',
        'formula_field_ids.field_type',
    )
    def _compute_formula_token_preview(self):
        for rec in self:
            lines = [
                'Built-in (always available):',
                '  {ELIGIBILITY_PCT}  — eligibility % from mapping rule',
                '  {RATING_CODE}      — employee rating code',
            ]
            if rec.formula_field_ids:
                lines.append('')
                lines.append('Custom tokens:')
                for f in rec.formula_field_ids:
                    type_label = dict(
                        f._fields['field_type'].selection
                    ).get(f.field_type, f.field_type)
                    lines.append(
                        f'  {{{f.token_name}}}  — {f.name} [{type_label}]'
                    )
            rec.formula_token_preview = '\n'.join(lines)

    # ── Constraints ───────────────────────────────────────────────────

    @api.constrains('is_default', 'company_id')
    def _check_single_default(self):
        for record in self:
            if record.is_default:
                existing = self.search([
                    ('is_default', '=', True),
                    ('company_id', '=', record.company_id.id),
                    ('id', '!=', record.id),
                ])
                if existing:
                    raise ValidationError(
                        f'"{existing[0].name}" is already the default '
                        f'bonus engine. Please unset it first.'
                    )

    @api.constrains('formula')
    def _check_formula_syntax(self):
        BUILTIN = {'ELIGIBILITY_PCT', 'RATING_CODE'}
        for rec in self:
            if not rec.formula:
                continue
            used = set(re.findall(r'\{([A-Z][A-Z0-9_]*)\}', rec.formula))
            known = set(rec.formula_field_ids.mapped('token_name')) | BUILTIN
            unknown = used - known
            if unknown:
                raise ValidationError(
                    f'Formula contains unknown token(s): '
                    f'{", ".join("{" + t + "}" for t in unknown)}.\n'
                    f'Add them in the Formula Tokens table first.'
                )

    # ── Actions ───────────────────────────────────────────────────────

    def action_set_default(self):
        self.ensure_one()
        self.search([
            ('is_default', '=', True),
            ('company_id', '=', self.company_id.id),
            ('id', '!=', self.id),
        ]).write({'is_default': False})
        self.write({'is_default': True})

    @api.model
    def get_default_engine(self, company_id=None):
        company_id = company_id or self.env.company.id
        return self.search([
            ('is_default', '=', True),
            ('company_id', '=', company_id),
            ('active', '=', True),
        ], limit=1)

    def get_eligibility_pct(self, rating_code):
        self.ensure_one()
        rule = self.mapping_rule_ids.filtered(
            lambda r: r.rating_id.code == rating_code
        )
        return rule[0].eligibility_pct if rule else 0.0

    def compute_bonus(self, context_values: dict) -> float:
        """
        Evaluates the bonus formula substituting all {TOKEN} values.

        Example:
            engine.compute_bonus({
                'FINAL_SCORE': 83.6,
                'ELIGIBILITY_PCT': 75.0,
                'BONUS_POOL': 50000.0,
            })
            → 83.6 * 75.0 * 50000.0 / 100  →  31350.0
        """
        self.ensure_one()
        if not self.formula:
            raise ValidationError('No formula defined on this bonus engine.')
        expr = self.formula
        for token, value in context_values.items():
            expr = expr.replace(f'{{{token}}}', str(value))
        allowed = re.compile(r'^[\d\s\.\+\-\*\/\(\)]+$')
        if not allowed.match(expr):
            raise ValidationError(
                f'Unsafe expression after token substitution: "{expr}"'
            )
        try:
            return float(eval(expr))  # noqa: S307
        except Exception as e:
            raise ValidationError(
                f'Formula evaluation failed: {e}\nExpression: "{expr}"'
            ) from e