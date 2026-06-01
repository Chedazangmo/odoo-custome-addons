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
        """
        When the score allocation changes, immediately update the competency
        ceiling on the linked competency template so the "Total Assigned"
        progress fraction reflects the new denominator right away.
        """
        if not self.score_allocation_id:
            return

        origin_id = self._origin.id if self._origin else None
        if origin_id and self.competency_template_id:
            self.competency_template_id._sync_ceiling()

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

    @api.onchange('competency_template_id')
    def _onchange_competency_template(self):
        """
        When the linked competency template changes, sync the ceiling so the
        template's ceiling immediately reflects the current allocation weight.
        """
        if self.competency_template_id and self.score_allocation_id:
            origin_id = self._origin.id if self._origin else None
            if origin_id:
                self.competency_template_id._sync_ceiling()

    # ══════════════════════════════════════════════════════════
    # ORM overrides — keep ceiling in sync on every save
    # ══════════════════════════════════════════════════════════

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if record.competency_template_id:
            record.competency_template_id._sync_ceiling()
        return record

    def write(self, vals):
        result = super().write(vals)
        if any(k in vals for k in ['score_allocation_id', 'competency_template_id']):
            for rec in self:
                if rec.competency_template_id:
                    rec.competency_template_id._sync_ceiling()
                    rec.competency_template_id.invalidate_recordset([
                        'competency_ceiling',
                        'points_status',
                        'total_hr_points',
                        'points_progress',
                    ])
        return result

    # ══════════════════════════════════════════════════════════
    # Button Actions
    # ══════════════════════════════════════════════════════════

    def action_create_competency_template(self):
        self.ensure_one()

        if not self.score_allocation_id:
            raise ValidationError(_(
                'Please select a Score Allocation first before creating a '
                'Competency Template.\n\n'
                'The competency weight will be taken from the Score Allocation.'
            ))

        comp_weight = self.score_allocation_id.competency_weight
        if float_compare(comp_weight, 0.0, precision_digits=2) <= 0:
            raise ValidationError(_(
                'Competency weight in the selected Score Allocation is zero or '
                'negative.\n\nPlease fix the Score Allocation first '
                '(Current weight: %.2f pts)'
            ) % comp_weight)

        # is_skeleton=True tells the allocation constraint to stand down while
        # the template is empty. It is cleared automatically once the user fills
        # the template to exactly the ceiling.
        new_template = self.env['competency.framework.template'].create({
            'name': _('Competencies for %s') % self.name,
            'description': _(
                'Linked to "%(template)s" · Ceiling: %(weight).2f pts (%(allocation)s)'
            ) % {
                'template':   self.name,
                'weight':     comp_weight,
                'allocation': self.score_allocation_id.name,
            },
            'competency_ceiling': comp_weight,
            'is_skeleton': True,
        })

        # Link and persist so _sync_ceiling can walk back via appraisal.template
        self.write({'competency_template_id': new_template.id})
        new_template._sync_ceiling()

        return {
            'type':      'ir.actions.act_window',
            'name':      _('New Competency Template'),
            'res_model': 'competency.framework.template',
            'res_id':    new_template.id,
            'view_mode': 'form',
            'target':    'current',
            'context':   {'form_view_initial_mode': 'edit'},
        }

    def action_open_competency_template(self):
        self.ensure_one()
        if not self.competency_template_id:
            return
        return {
            'type':      'ir.actions.act_window',
            'name':      _('Competency Template'),
            'res_model': 'competency.framework.template',
            'res_id':    self.competency_template_id.id,
            'view_mode': 'form',
            'target':    'current',
        }

    def action_open_score_allocation(self):
        self.ensure_one()
        if not self.score_allocation_id:
            return
        return {
            'type':      'ir.actions.act_window',
            'name':      _('Score Allocation'),
            'res_model': 'pms.score.allocation',
            'res_id':    self.score_allocation_id.id,
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


class AppraisalKRA(models.Model):
    _name = 'appraisal.kra'
    _description = 'Key Result Area'
    _order = 'sequence, id'

    name        = fields.Char(string='KRA Name', required=True)
    template_id = fields.Many2one(
        'appraisal.template', string='Appraisal Template',
        required=True, ondelete='cascade',
    )
    sequence    = fields.Integer(string='Sequence', default=10)
    kpi_ids     = fields.One2many('appraisal.kpi', 'kra_id', string='KPIs')


class AppraisalKPI(models.Model):
    _name = 'appraisal.kpi'
    _description = 'Key Performance Indicator'
    _order = 'kra_id, id'

    name        = fields.Char(string='KPI Name', required=True)
    description = fields.Text(string='Description')
    criteria    = fields.Text(string='Criteria')
    score       = fields.Float(string='Points', required=True, default=0.0)
    kra_id      = fields.Many2one(
        'appraisal.kra', string='KRA',
        required=True, ondelete='cascade',
    )