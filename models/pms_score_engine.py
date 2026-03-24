from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PMSScoringEngine(models.Model):
    _name = 'pms.scoring.engine'
    _description = 'PMS Scoring Engine'
    _order = 'is_default desc, name'

    name = fields.Char(
        string='Engine Name',
        required=True,
        help='e.g. "Standard 2025", "Executive Scale"'
    )

    is_default = fields.Boolean(
        string='Set as Default',
        default=False,
        help='Default engine is used automatically when no engine is selected on a cycle'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    line_ids = fields.One2many(
        'pms.scoring.engine.line',
        'engine_id',
        string='Score Ranges',
        copy=True
    )

    line_count = fields.Integer(
        string='Range Count',
        compute='_compute_line_count'
    )

    score_min = fields.Float(
        string='Lowest Score',
        compute='_compute_score_bounds',
        help='Lowest score covered by this engine'
    )

    score_max = fields.Float(
        string='Highest Score',
        compute='_compute_score_bounds',
        help='Highest score covered by this engine'
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends('line_ids')
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.line_ids)

    @api.depends('line_ids.min_score', 'line_ids.max_score')
    def _compute_score_bounds(self):
        for record in self:
            if record.line_ids:
                record.score_min = min(record.line_ids.mapped('min_score'))
                record.score_max = max(record.line_ids.mapped('max_score'))
            else:
                record.score_min = 0.0
                record.score_max = 0.0

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('is_default', 'company_id')
    def _check_single_default(self):
        # Only one engine can be default per company at a time.
        for record in self:
            if record.is_default:
                existing = self.search([
                    ('is_default', '=', True),
                    ('company_id', '=', record.company_id.id),
                    ('id', '!=', record.id),
                ])
                if existing:
                    raise ValidationError(
                        f'"{existing[0].name}" is already set as the default scoring engine. '
                        f'Please unset it first before setting a new default.'
                    )

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------

    def write(self, vals):
        result = super().write(vals)
        # When setting is_default=True via the toggle button, auto-unset others
        # in the same company so HR does not have to manually unset the old one.
        if vals.get('is_default'):
            for record in self:
                self.search([
                    ('is_default', '=', True),
                    ('company_id', '=', record.company_id.id),
                    ('id', '!=', record.id),
                ]).write({'is_default': False})
        return result

    # ------------------------------------------------------------------
    # Business Logic
    # ------------------------------------------------------------------

    def get_rating_for_score(self, score):
        """
        Returns the rating label for a given score based on this engine's ranges.
        Uses inclusive lower bound, inclusive upper bound (standard closed intervals).
        If the score falls in a gap between ranges, returns False.
        """
        self.ensure_one()
        line = self.line_ids.filtered(
            lambda l: l.min_score <= score <= l.max_score
        )
        # If multiple somehow match (should be blocked by constraints), take highest min
        if len(line) > 1:
            line = line.sorted('min_score', reverse=True)[0]
        return line.rating if line else False

    @api.model
    def get_default_engine(self, company_id=None):
        """Returns the default scoring engine for the given company."""
        company_id = company_id or self.env.company.id
        return self.search([
            ('is_default', '=', True),
            ('company_id', '=', company_id),
            ('active', '=', True),
        ], limit=1)

    def action_set_default(self):
        """Button action to set this engine as default and unset others."""
        self.ensure_one()
        # Unset all others in same company
        self.search([
            ('is_default', '=', True),
            ('company_id', '=', self.company_id.id),
            ('id', '!=', self.id),
        ]).write({'is_default': False})
        self.write({'is_default': True})


class PMSScoringEngineLine(models.Model):
    _name = 'pms.scoring.engine.line'
    _description = 'PMS Scoring Engine Range Line'
    _order = 'min_score'

    engine_id = fields.Many2one(
        'pms.scoring.engine',
        string='Scoring Engine',
        required=True,
        ondelete='cascade',
        index=True
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    rating = fields.Char(
        string='Rating Label',
        required=True,
        help='e.g. Excellent, Good, Satisfactory, Needs Improvement, Poor'
    )

    min_score = fields.Float(
        string='Min Score',
        required=True,
        default=0.0,
        help='Inclusive lower bound of this range'
    )

    max_score = fields.Float(
        string='Max Score',
        required=True,
        default=0.0,
        help='Inclusive upper bound of this range'
    )


    range_display = fields.Char(
        string='Range',
        compute='_compute_range_display',
        help='Human-readable display of the score range'
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends('min_score', 'max_score')
    def _compute_range_display(self):
        for record in self:
            record.range_display = f'{record.min_score:.1f} – {record.max_score:.1f}'

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('min_score', 'max_score')
    def _check_min_less_than_max(self):
        for record in self:
            if record.min_score < 0:
                raise ValidationError(
                    f'Min score cannot be negative on range "{record.rating}".'
                )
            if record.max_score < 0:
                raise ValidationError(
                    f'Max score cannot be negative on range "{record.rating}".'
                )
            if record.min_score >= record.max_score:
                raise ValidationError(
                    f'Min score must be strictly less than Max score on range "{record.rating}". '
                    f'Got: {record.min_score} – {record.max_score}'
                )

    @api.constrains('min_score', 'max_score', 'engine_id')
    def _check_no_overlap(self):
        # For each line, check no other line in the same engine overlaps its range.
        # Two ranges [a,b] and [c,d] overlap if a < d and c < b.
        for record in self:
            overlapping = self.search([
                ('engine_id', '=', record.engine_id.id),
                ('id', '!=', record.id),
                ('min_score', '<', record.max_score),
                ('max_score', '>', record.min_score),
            ])
            if overlapping:
                names = ', '.join(overlapping.mapped('rating'))
                raise ValidationError(
                    f'The range "{record.rating}" ({record.min_score}–{record.max_score}) '
                    f'overlaps with: {names}. '
                    f'Please adjust the ranges so they do not overlap.'
                )