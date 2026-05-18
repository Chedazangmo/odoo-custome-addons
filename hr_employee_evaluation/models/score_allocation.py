# models/score_allocation.py
# ============================================================
# COMPLETE FIXED VERSION with write() method
# ============================================================

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare

GRAND_TOTAL = 100.0


class PmsScoreAllocation(models.Model):
    """
    Master allocation record that HR creates ONCE per evaluation cycle.
    It answers:  "KPI carries X points, Competency carries Y points,
                  and X + Y must equal 100."

    One allocation can be shared across multiple appraisal templates
    (e.g. different job-grade templates all follow the same 70/30 split).
    """
    _name        = 'pms.score.allocation'
    _description = 'Score Allocation (KPI vs Competency)'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'name'

    # ── Identity ──────────────────────────────────────────────
    name = fields.Char(
        string='Allocation Name',
        required=True,
        tracking=True,
        help='e.g. "Standard 70/30 – FY 2025"',
    )
    description = fields.Text(string='Description')
    active      = fields.Boolean(default=True)

    # ── The two master weights ────────────────────────────────
    kpi_weight = fields.Float(
        string='KPI Total Weight',
        required=True,
        default=70.0,
        tracking=True,
        help='Total points available for the KPI section.',
    )
    competency_weight = fields.Float(
        string='Competency Total Weight',
        required=True,
        default=30.0,
        tracking=True,
        help='Total points available for the Competency section.',
    )

    # ── Read-only summary ─────────────────────────────────────
    grand_total = fields.Float(
        string='Grand Total',
        compute='_compute_grand_total',
        store=True,
    )
    allocation_status = fields.Selection(
        selection=[
            ('under', 'Under 100'),
            ('exact', 'Exactly 100'),
            ('over',  'Over 100'),
        ],
        string='Status',
        compute='_compute_grand_total',
        store=True,
    )

    # ── Back-reference: how many templates use this allocation ─
    template_count = fields.Integer(
        string='Templates',
        compute='_compute_template_count',
    )

    # ══════════════════════════════════════════════════════════
    # Computes
    # ══════════════════════════════════════════════════════════

    @api.depends('kpi_weight', 'competency_weight')
    def _compute_grand_total(self):
        for rec in self:
            total = rec.kpi_weight + rec.competency_weight
            rec.grand_total = total
            cmp = float_compare(total, GRAND_TOTAL, precision_digits=2)
            rec.allocation_status = (
                'exact' if cmp == 0 else ('over' if cmp > 0 else 'under')
            )

    def _compute_template_count(self):
        for rec in self:
            rec.template_count = self.env['appraisal.template'].search_count([
                ('score_allocation_id', '=', rec.id),
            ])

    # ══════════════════════════════════════════════════════════
    # write() — Auto-sync competency ceilings when weights change
    # ══════════════════════════════════════════════════════════
    # OPTIONAL ENHANCEMENT:
    # If the competency_weight is updated, sync all linked competency
    # templates' ceilings automatically. This ensures that if you change
    # from 70/30 to 60/40, all existing competency frameworks update
    # from 30-pt ceiling to 40-pt ceiling immediately.
    #
    # This complements the appraisal_template.write() method which syncs
    # when the allocation is first linked to a template.
    # ══════════════════════════════════════════════════════════

    def write(self, vals):
        """
        When competency_weight changes, sync all linked competency templates.
        
        This ensures that if you update an allocation from 70/30 to 60/40,
        all competency frameworks linked via appraisal templates will
        automatically update their ceiling from 30 → 40 pts.
        """
        result = super().write(vals)
        
        # If competency_weight changed, update all linked competency templates
        if 'competency_weight' in vals:
            # Find all appraisal templates using this allocation
            appraisal_tmpls = self.env['appraisal.template'].search([
                ('score_allocation_id', 'in', self.ids)
            ])
            # Trigger sync on each linked competency template
            for tmpl in appraisal_tmpls:
                if tmpl.competency_template_id:
                    tmpl.competency_template_id._sync_ceiling()
        
        return result

    # ══════════════════════════════════════════════════════════
    # Onchange — live feedback while HR is typing
    # ══════════════════════════════════════════════════════════

    @api.onchange('kpi_weight', 'competency_weight')
    def _onchange_weights(self):
        total = (self.kpi_weight or 0.0) + (self.competency_weight or 0.0)
        cmp   = float_compare(total, GRAND_TOTAL, precision_digits=2)
        if cmp > 0:
            return {'warning': {
                'title':   _('Over 100 pts'),
                'message': _(
                    'KPI (%(k).2f) + Competency (%(c).2f) = %(t).2f — '
                    '%(e).2f pt(s) over 100. Adjust before saving.'
                ) % {
                    'k': self.kpi_weight or 0.0,
                    'c': self.competency_weight or 0.0,
                    't': total,
                    'e': total - GRAND_TOTAL,
                },
            }}
        if cmp < 0:
            return {'warning': {
                'title':   _('Under 100 pts'),
                'message': _(
                    'KPI (%(k).2f) + Competency (%(c).2f) = %(t).2f — '
                    '%(r).2f pt(s) short of 100. Adjust before saving.'
                ) % {
                    'k': self.kpi_weight or 0.0,
                    'c': self.competency_weight or 0.0,
                    't': total,
                    'r': GRAND_TOTAL - total,
                },
            }}

    # ══════════════════════════════════════════════════════════
    # Constraints
    # ══════════════════════════════════════════════════════════

    @api.constrains('kpi_weight', 'competency_weight')
    def _check_grand_total(self):
        for rec in self:
            total = rec.kpi_weight + rec.competency_weight
            cmp   = float_compare(total, GRAND_TOTAL, precision_digits=2)
            if cmp > 0:
                raise ValidationError(_(
                    '"%(name)s": KPI (%(k).2f) + Competency (%(c).2f) = %(t).2f '
                    '— %(e).2f pt(s) over 100. Reduce one of the weights.'
                ) % {
                    'name': rec.name,
                    'k': rec.kpi_weight,
                    'c': rec.competency_weight,
                    't': total,
                    'e': total - GRAND_TOTAL,
                })
            if cmp < 0:
                raise ValidationError(_(
                    '"%(name)s": KPI (%(k).2f) + Competency (%(c).2f) = %(t).2f '
                    '— %(r).2f pt(s) short of 100. Adjust before saving.'
                ) % {
                    'name': rec.name,
                    'k': rec.kpi_weight,
                    'c': rec.competency_weight,
                    't': total,
                    'r': GRAND_TOTAL - total,
                })

    @api.constrains('kpi_weight')
    def _check_kpi_weight_positive(self):
        for rec in self:
            if float_compare(rec.kpi_weight, 0.0, precision_digits=2) <= 0:
                raise ValidationError(
                    _('KPI weight must be greater than 0.')
                )

    @api.constrains('competency_weight')
    def _check_competency_weight_positive(self):
        for rec in self:
            if float_compare(rec.competency_weight, 0.0, precision_digits=2) <= 0:
                raise ValidationError(
                    _('Competency weight must be greater than 0.')
                )

    # ══════════════════════════════════════════════════════════
    # Action — jump to linked templates
    # ══════════════════════════════════════════════════════════

    def action_view_templates(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      _('Appraisal Templates'),
            'res_model': 'appraisal.template',
            'view_mode': 'list,form',
            'domain':    [('score_allocation_id', '=', self.id)],
        }