# models/appraisal_template.py

from odoo import models, fields, api
from odoo.exceptions import ValidationError


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

    # ══════════════════════════════════════════════════════════
    # Button — open linked competency template
    # ══════════════════════════════════════════════════════════

    def action_open_competency_template(self):
        """
        Opens the linked competency template form directly.
        Called from the smart button on the appraisal form.
        """
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Competency Template',
            'res_model': 'competency.framework.template',
            'res_id':    self.competency_template_id.id,
            'view_mode': 'form',
            'target':    'current',
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
                raise ValidationError(
                    f"A template for '{rec.evaluation_group_id.name}' "
                    f"already exists. Only one template per evaluation "
                    f"group is allowed."
                )

    @api.constrains('competency_template_id')
    def _check_competency_template_not_already_linked(self):
        """One competency template can only be linked to one appraisal template."""
        for rec in self:
            if not rec.competency_template_id:
                continue
            existing = self.search([
                ('competency_template_id', '=',
                 rec.competency_template_id.id),
                ('id', '!=', rec.id),
            ])
            if existing:
                raise ValidationError(
                    f'Competency template '
                    f'"{rec.competency_template_id.name}" is already '
                    f'linked to "{existing[0].name}". '
                    f'One competency template per appraisal template only.'
                )