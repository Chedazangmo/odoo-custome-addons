# models/appraisal_template.py
# ============================================================
# COMPLETE ENHANCED VERSION with Create Template button methods
# ============================================================

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class AppraisalTemplate(models.Model):
    _name        = 'appraisal.template'
    _description = 'Appraisal Template'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'name'

    # ── Basic Info ────────────────────────────────────────────
    name = fields.Char(
        string='Template Name',
        required=True,
        tracking=True,
    )
    evaluation_group_id = fields.Many2one(
        'pms.evaluation.group',
        string='Evaluation Group',
        required=True,
        ondelete='restrict',
        tracking=True,
    )

    # ── Master Score Allocation ───────────────────────────────
    score_allocation_id = fields.Many2one(
        'pms.score.allocation',
        string='Score Allocation',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='Defines the KPI / Competency split (must sum to 100).',
    )

    # Pulled from the allocation for easy display & validation
    kpi_weight = fields.Float(
        string='KPI Weight',
        related='score_allocation_id.kpi_weight',
        readonly=True,
        store=False,
    )
    competency_weight = fields.Float(
        string='Competency Weight',
        related='score_allocation_id.competency_weight',
        readonly=True,
        store=False,
    )
    allocation_grand_total = fields.Float(
        string='Grand Total',
        related='score_allocation_id.grand_total',
        readonly=True,
        store=False,
    )
    allocation_status = fields.Selection(
        string='Allocation Status',
        related='score_allocation_id.allocation_status',
        readonly=True,
        store=False,
    )

    # ── Competency Linkage ────────────────────────────────────
    competency_template_id = fields.Many2one(
        'competency.framework.template',
        string='Competency Template',
        ondelete='restrict',
        tracking=True,
        help='Link a competency framework template.',
    )
    competency_total_hr_points = fields.Float(
        string='Competency HR Points',
        related='competency_template_id.total_hr_points',
        readonly=True,
        store=False,
    )
    competency_group_count = fields.Integer(
        string='Competency Groups',
        related='competency_template_id.group_count',
        readonly=True,
        store=False,
    )
    competency_points_status = fields.Selection(
        string='Competency Status',
        related='competency_template_id.points_status',
        readonly=True,
        store=False,
    )

    # ── KRA / KPI ─────────────────────────────────────────────
    kra_ids = fields.One2many(
        'appraisal.kra',
        'template_id',
        string='Key Result Areas',
    )
    total_kpi_score = fields.Float(
        string='Total KPI Score',
        compute='_compute_total_kpi_score',
        store=True,
        compute_sudo=True,
    )
    kpi_remaining = fields.Float(
        string='KPI Remaining',
        compute='_compute_kpi_status',
        store=False,
    )
    kpi_status = fields.Selection(
        selection=[
            ('under', 'Under Allocated'),
            ('exact', 'Fully Allocated'),
            ('over',  'Over Allocated'),
        ],
        string='KPI Status',
        compute='_compute_kpi_status',
        store=False,
    )

    # ── State / Active ────────────────────────────────────────
    state = fields.Selection(
        [('draft', 'Draft'), ('locked', 'Locked')],
        default='draft',
        tracking=True,
        required=True,
    )
    active = fields.Boolean(default=True)

    # ══════════════════════════════════════════════════════════
    # Computes
    # ══════════════════════════════════════════════════════════

    @api.depends('kra_ids.kpi_ids.score')
    def _compute_total_kpi_score(self):
        for rec in self:
            rec.total_kpi_score = sum(
                kpi.score
                for kra in rec.kra_ids
                for kpi in kra.kpi_ids
            )

    @api.depends('total_kpi_score', 'score_allocation_id.kpi_weight')
    def _compute_kpi_status(self):
        for rec in self:
            weight = rec.score_allocation_id.kpi_weight if rec.score_allocation_id else 0.0
            diff   = weight - rec.total_kpi_score
            rec.kpi_remaining = diff
            cmp = float_compare(rec.total_kpi_score, weight, precision_digits=2)
            rec.kpi_status = (
                'exact' if cmp == 0 else ('over' if cmp > 0 else 'under')
            )

    # ══════════════════════════════════════════════════════════
    # Onchange — live feedback
    # ══════════════════════════════════════════════════════════

    @api.onchange('score_allocation_id')
    def _onchange_score_allocation(self):
        """Warn if the chosen allocation doesn't exactly sum to 100."""
        if not self.score_allocation_id:
            return
        status = self.score_allocation_id.allocation_status
        if status == 'over':
            return {'warning': {
                'title':   _('Allocation Over 100'),
                'message': _(
                    '"%s" sums to more than 100. '
                    'Fix the allocation before saving this template.'
                ) % self.score_allocation_id.name,
            }}
        if status == 'under':
            return {'warning': {
                'title':   _('Allocation Under 100'),
                'message': _(
                    '"%s" sums to less than 100. '
                    'Fix the allocation before saving this template.'
                ) % self.score_allocation_id.name,
            }}

    # ══════════════════════════════════════════════════════════
    # write() — Sync competency template ceiling
    # ══════════════════════════════════════════════════════════
    # KEY FIX: When score_allocation_id or competency_template_id changes,
    # immediately sync the ceiling and invalidate the competency template
    # to force a refresh of all computed fields.
    # ══════════════════════════════════════════════════════════

    def write(self, vals):
        """
        When score_allocation_id or competency_template_id changes,
        sync the competency framework template's ceiling to match the
        allocation's competency_weight.
        
        This fixes the issue where competency templates show a 100-pt
        ceiling instead of respecting the allocation-based weight.
        """
        result = super().write(vals)
        
        # Check if either the allocation or competency template changed
        if any(k in vals for k in ['score_allocation_id', 'competency_template_id']):
            for rec in self:
                # If there's a competency template linked, sync its ceiling
                if rec.competency_template_id:
                    # Sync the ceiling
                    rec.competency_template_id._sync_ceiling()
                    
                    # Force invalidation of all dependent fields to refresh UI
                    rec.competency_template_id.invalidate_recordset([
                        'competency_ceiling',
                        'points_status',
                        'remaining_hr_points',
                        'total_hr_points',
                    ])
        
        return result

    # ══════════════════════════════════════════════════════════
    # Button Actions
    # ══════════════════════════════════════════════════════════

    def action_create_competency_template(self):
        """
        Create a new competency framework template linked to this appraisal template.
        The new template will automatically inherit the competency weight from the
        score allocation as its ceiling.
        """
        self.ensure_one()
        
        # Check if score allocation is selected
        if not self.score_allocation_id:
            raise ValidationError(_(
                'Please select a Score Allocation first before creating a '
                'Competency Template.\n\n'
                'The competency weight will be taken from the Score Allocation.'
            ))
        
        # Check if competency weight is valid
        comp_weight = self.score_allocation_id.competency_weight
        if float_compare(comp_weight, 0.0, precision_digits=2) <= 0:
            raise ValidationError(_(
                'Competency weight in the selected Score Allocation is zero or negative.\n\n'
                'Please fix the Score Allocation first (Current weight: %.2f pts)'
            ) % comp_weight)
        
        # Create a new competency template
        new_template = self.env['competency.framework.template'].create({
            'name': _('Competencies for %s') % self.name,
            'description': _(
                'Auto-created from appraisal template: %(template)s\n'
                'Competency weight: %(weight).2f pts (from Score Allocation: %(allocation)s)\n\n'
                'This template must total exactly %(weight).2f points to match the allocation.'
            ) % {
                'template': self.name,
                'weight': comp_weight,
                'allocation': self.score_allocation_id.name,
            },
            'competency_ceiling': comp_weight,  # Set ceiling directly from allocation
        })
        
        # Link it to this appraisal template
        self.competency_template_id = new_template.id
        
        # Sync the ceiling (ensures all computed fields update properly)
        new_template._sync_ceiling()
        
        # Show success message and open the new template
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Competency Template Created'),
            'res_model': 'competency.framework.template',
            'res_id': new_template.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'form_view_initial_mode': 'edit',
            },
        }

    def action_open_competency_template(self):
        """Open the linked competency template"""
        self.ensure_one()
        if not self.competency_template_id:
            return
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Competency Template'),
            'res_model': 'competency.framework.template',
            'res_id': self.competency_template_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_score_allocation(self):
        """Open the linked score allocation"""
        self.ensure_one()
        if not self.score_allocation_id:
            return
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Score Allocation'),
            'res_model': 'pms.score.allocation',
            'res_id': self.score_allocation_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ══════════════════════════════════════════════════════════
    # Constraints
    # ══════════════════════════════════════════════════════════

    @api.constrains('evaluation_group_id')
    def _check_unique_evaluation_group(self):
        for rec in self:
            existing = self.search([
                ('evaluation_group_id', '=', rec.evaluation_group_id.id),
                ('id', '!=', rec.id),
            ])
            if existing:
                raise ValidationError(_(
                    'A template for "%s" already exists. '
                    'Only one template per evaluation group is allowed.'
                ) % rec.evaluation_group_id.name)

    @api.constrains('competency_template_id')
    def _check_competency_template_not_already_linked(self):
        for rec in self:
            if not rec.competency_template_id:
                continue
            existing = self.search([
                ('competency_template_id', '=', rec.competency_template_id.id),
                ('id', '!=', rec.id),
            ])
            if existing:
                raise ValidationError(_(
                    'Competency template "%s" is already linked to "%s". '
                    'One competency template per appraisal template only.'
                ) % (rec.competency_template_id.name, existing[0].name))

    @api.constrains('score_allocation_id')
    def _check_allocation_is_exact(self):
        """
        The linked score allocation must sum to exactly 100 before
        this template can be saved.
        """
        for rec in self:
            if not rec.score_allocation_id:
                continue
            status = rec.score_allocation_id.allocation_status
            if status != 'exact':
                raise ValidationError(_(
                    'Score allocation "%s" does not sum to 100 '
                    '(current total: %(t).2f). '
                    'Fix the allocation before saving this template.'
                ) % {
                    'name': rec.score_allocation_id.name,
                    't':    rec.score_allocation_id.grand_total,
                })

    @api.constrains('total_kpi_score', 'score_allocation_id')
    def _check_kpi_score_matches_weight(self):
        """
        The sum of all KPI scores must equal the KPI weight defined
        in the linked score allocation before the template can be saved.

        NOTE: Only enforced when the template is in 'locked' state,
        so HR can build the template incrementally while in 'draft'.
        Switch this to check all states if your workflow requires it.
        """
        for rec in self:
            if rec.state != 'locked':
                continue
            if not rec.score_allocation_id:
                continue
            weight = rec.score_allocation_id.kpi_weight
            cmp    = float_compare(rec.total_kpi_score, weight, precision_digits=2)
            if cmp > 0:
                raise ValidationError(_(
                    '"%(tmpl)s": KPI score total (%(score).2f) exceeds '
                    'the KPI weight (%(weight).2f) by %(e).2f pt(s). '
                    'Reduce KPI scores before locking.'
                ) % {
                    'tmpl':   rec.name,
                    'score':  rec.total_kpi_score,
                    'weight': weight,
                    'e':      rec.total_kpi_score - weight,
                })
            if cmp < 0:
                raise ValidationError(_(
                    '"%(tmpl)s": KPI score total (%(score).2f) is '
                    '%(r).2f pt(s) short of the KPI weight (%(weight).2f). '
                    'Distribute all %(weight).2f pts before locking.'
                ) % {
                    'tmpl':   rec.name,
                    'score':  rec.total_kpi_score,
                    'weight': weight,
                    'r':      weight - rec.total_kpi_score,
                })

    @api.constrains('competency_template_id', 'score_allocation_id')
    def _check_competency_score_matches_weight(self):
        """
        The linked competency framework's total_hr_points must equal
        the competency weight from the score allocation.

        Like the KPI check, this is only enforced in 'locked' state
        so HR can build incrementally in draft.
        """
        for rec in self:
            if rec.state != 'locked':
                continue
            if not rec.score_allocation_id or not rec.competency_template_id:
                continue
            c_weight = rec.score_allocation_id.competency_weight
            c_total  = rec.competency_template_id.total_hr_points
            cmp      = float_compare(c_total, c_weight, precision_digits=2)
            if cmp > 0:
                raise ValidationError(_(
                    '"%(tmpl)s": Competency template total (%(ct).2f) exceeds '
                    'the competency weight (%(cw).2f) by %(e).2f pt(s).'
                ) % {
                    'tmpl': rec.name,
                    'ct':   c_total,
                    'cw':   c_weight,
                    'e':    c_total - c_weight,
                })
            if cmp < 0:
                raise ValidationError(_(
                    '"%(tmpl)s": Competency template total (%(ct).2f) is '
                    '%(r).2f pt(s) short of the competency weight (%(cw).2f).'
                ) % {
                    'tmpl': rec.name,
                    'ct':   c_total,
                    'cw':   c_weight,
                    'r':    c_weight - c_total,
                })