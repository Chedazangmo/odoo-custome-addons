from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class KpiTemplate(models.Model):
    _name = 'kpi.template'
    _description = 'KPI Template Master'

    name = fields.Char(string='Template Name', required=True)
    evaluation_group_id = fields.Many2one(
        'evaluation.group',
        string='Evaluation Group',
        help="Evaluation group this template is designed for"
    )

    total_score = fields.Float(
        string='Total Allowed Score',
        required=True,
        default=80.0,
        help="Maximum total score allowed for all KPIs combined"
    )

    computed_total = fields.Float(
        string='Used Score',
        compute='_compute_current_total',
        store=True,
        help="Sum of scores from all KPI lines"
    )

    remaining_score = fields.Float(
        string='Remaining Score',
        compute='_compute_remaining_score',
        store=True
    )

    allocation_percentage = fields.Float(
        string='Allocation %',
        compute='_compute_allocation_percentage',
        store=True
    )

    score_status = fields.Selection([
        ('under', 'Under Allocated'),
        ('met', 'Perfectly Allocated'),
        ('over', 'Over Allocated')
    ], string='Score Status', compute='_compute_score_status', store=True)

    line_ids = fields.One2many(
        'kpi.template.line',
        'template_id',
        string='KPI Lines',
        copy=True
    )

    @api.depends('line_ids.score')
    def _compute_current_total(self):
        """Compute sum of all KPI line scores"""
        for template in self:
            # Calculate sum of scores from all KPI lines
            total = 0.0
            for line in template.line_ids:
                total += line.score
            template.computed_total = total

    @api.depends('computed_total', 'total_score')
    def _compute_remaining_score(self):
        for template in self:
            template.remaining_score = template.total_score - template.computed_total

    @api.depends('computed_total', 'total_score')
    def _compute_allocation_percentage(self):
        for template in self:
            if template.total_score > 0:
                template.allocation_percentage = (template.computed_total / template.total_score) * 100
            else:
                template.allocation_percentage = 0

    @api.depends('computed_total', 'total_score')
    def _compute_score_status(self):
        for template in self:
            if template.computed_total > template.total_score:
                template.score_status = 'over'
            elif template.computed_total == template.total_score:
                template.score_status = 'met'
            else:
                template.score_status = 'under'

    @api.constrains('line_ids', 'total_score')
    def _check_total_score(self):
        """Validate that sum of KPI scores doesn't exceed total allowed score"""
        for template in self:
            total_lines_score = sum(line.score for line in template.line_ids)
            if total_lines_score > template.total_score:
                raise ValidationError(
                    f"❌ Total score of all KPIs ({total_lines_score}) exceeds "
                    f"the allowed total score ({template.total_score})!"
                )

    def action_validate_template(self):
        """Button to validate template allocation"""
        self.ensure_one()
        total_lines_score = sum(line.score for line in self.line_ids)

        if total_lines_score > self.total_score:
            raise UserError(
                f"❌ Validation Failed: Total ({total_lines_score}) exceeds limit ({self.total_score})"
            )
        elif total_lines_score < self.total_score:
            remaining = self.total_score - total_lines_score
            raise UserError(
                f"⚠️ Template Incomplete: {remaining} points remaining out of {self.total_score}"
            )
        else:
            raise UserError(f"✅ Template is perfectly balanced! All {self.total_score} points allocated.")

    # Debug method - add this to check calculations
    def debug_calculation(self):
        self.ensure_one()
        manual_sum = sum(line.score for line in self.line_ids)
        raise UserError(
            f"Debug Information:\n"
            f"------------------\n"
            f"Template: {self.name}\n"
            f"Total Score (allowed): {self.total_score}\n"
            f"Computed Total (field): {self.computed_total}\n"
            f"Manual Sum of KPI lines: {manual_sum}\n"
            f"Remaining Score (field): {self.remaining_score}\n"
            f"Number of KPI lines: {len(self.line_ids)}\n"
            f"KPI Line Scores: {[line.score for line in self.line_ids]}"
        )