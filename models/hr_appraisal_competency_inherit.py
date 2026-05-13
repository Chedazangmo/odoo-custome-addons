# ============================================================
# models/pms_appraisal_competency_inherit.py
#
# Extends pms.appraisal to:
#   1. Add competency_score_ids (One2many → appraisal.competency.score)
#   2. Add computed totals per rater
#   3. Auto-sync score rows from linked competency template on create
#      and when template_id changes
#
# NOTE: This mixin does NOT re-define write(). The parent pms.appraisal
# write() already handles competency_score_ids filtering via
# _filter_competency_score_commands(). Re-defining write() here would
# cause double execution. Template-change sync is handled via
# _post_write_sync() called from a chained super().write().
# ============================================================

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PmsAppraisalCompetencyInherit(models.Model):
    _inherit = 'pms.appraisal'

    # ── One2many to score rows ────────────────────────────────

    competency_score_ids = fields.One2many(
        'appraisal.competency.score',
        'appraisal_id',
        string='Competency Scores',
    )

    # ── Convenience computed totals ───────────────────────────

    competency_self_total = fields.Float(
        string='Competency Employee Total',
        compute='_compute_competency_totals',
        store=True,
    )
    competency_supervisor_total = fields.Float(
        string='Competency Supervisor Total',
        compute='_compute_competency_totals',
        store=True,
    )
    competency_secondary_total = fields.Float(
        string='Competency 2nd Supervisor Total',
        compute='_compute_competency_totals',
        store=True,
    )
    competency_reviewer_total = fields.Float(
        string='Competency Reviewer Total',
        compute='_compute_competency_totals',
        store=True,
    )
    competency_max_total = fields.Float(
        string='Competency Max Points Total',
        compute='_compute_competency_totals',
        store=True,
    )

    @api.depends(
        'competency_score_ids.self_score',
        'competency_score_ids.supervisor_score',
        'competency_score_ids.secondary_supervisor_score',
        'competency_score_ids.reviewer_score',
        'competency_score_ids.line_points',
    )
    def _compute_competency_totals(self):
        for appraisal in self:
            scores = appraisal.competency_score_ids
            appraisal.competency_self_total       = sum(scores.mapped('self_score'))
            appraisal.competency_supervisor_total = sum(scores.mapped('supervisor_score'))
            appraisal.competency_secondary_total  = sum(scores.mapped('secondary_supervisor_score'))
            appraisal.competency_reviewer_total   = sum(scores.mapped('reviewer_score'))
            appraisal.competency_max_total        = sum(scores.mapped('line_points'))

    # ── Sync helpers ──────────────────────────────────────────

    def _get_competency_template(self):
        """
        Returns the competency.framework.template linked to this appraisal via:
            pms.appraisal.template_id → appraisal.template.competency_template_id
        """
        self.ensure_one()
        appraisal_tmpl = self.template_id
        if not appraisal_tmpl:
            return self.env['competency.framework.template']
        comp_tmpl = getattr(appraisal_tmpl, 'competency_template_id', False)
        return comp_tmpl or self.env['competency.framework.template']

    def _sync_competency_scores(self):
        """
        Idempotent: creates one appraisal.competency.score row per
        competency.framework.line in the linked template.
        Existing rows (with scores already entered) are left untouched.

        Uses sudo() so this works regardless of the calling user's access rights,
        since score rows are system-managed, not user-created.
        """
        Score = self.env['appraisal.competency.score'].sudo()

        for appraisal in self:
            comp_tmpl = appraisal._get_competency_template()
            if not comp_tmpl:
                continue

            # Collect all lines from all groups in the template,
            # ordered by (group.sequence, group.id, line.sequence, line.id)
            # so the display order matches the competency table exactly.
            all_lines = self.env['competency.framework.line'].search([
                ('group_id.template_id', '=', comp_tmpl.id),
            ], order='group_id, sequence, id')

            if not all_lines:
                continue

            existing_line_ids = set(
                appraisal.competency_score_ids.mapped('competency_line_id').ids
            )

            new_vals = [
                {
                    'appraisal_id':       appraisal.id,
                    'competency_line_id': line.id,
                }
                for line in all_lines
                if line.id not in existing_line_ids
            ]

            if new_vals:
                Score.create(new_vals)

    # ── Trigger sync on create ────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Sync after create so the appraisal ID exists in DB
        records._sync_competency_scores()
        return records

    # ── Trigger sync when template changes ───────────────────
    # We override write() ONLY to detect template_id changes.
    # We always call super() first so the parent write() (with its
    # role-based field filtering) runs before we do any post-processing.

    def write(self, vals):
        template_changed = 'template_id' in vals
        result = super().write(vals)
        if template_changed:
            self._sync_competency_scores()
        return result

    # ── Public action (HR manual re-sync button) ──────────────

    def action_sync_competency_scores(self):
        """Re-populate competency score rows from the linked template."""
        self.ensure_one()
        self._sync_competency_scores()
        return {
            'type':    'ir.actions.client',
            'tag':     'display_notification',
            'params': {
                'title':   _('Competency Scores Synced'),
                'message': _('Competency score rows have been refreshed from the template.'),
                'type':    'success',
                'sticky':  False,
            },
        }

    # ── HR reset: also clear competency scores ────────────────

    def action_hr_reset_appraisal_to_draft(self):
        """
        Overrides the base reset to also clear competency scores.
        The base method handles KPI scores and state change.
        """
        self.ensure_one()
        if not self.env.user.has_group('hr_employee_evaluation.group_pms_hr_manager'):
            raise UserError(_('Only HR/Admin can reset an appraisal.'))

        appraisal_states = {
            'appraisal_draft', 'appraisal_pending_supervisor',
            'appraisal_pending_secondary_supervisor',
            'appraisal_pending_reviewer', 'appraisal_approved',
        }
        if self.state not in appraisal_states:
            raise UserError(_('Can only reset records that are in the appraisal phase.'))

        # Clear KPI scores
        self.kra_ids.mapped('kpi_ids').write({
            'self_score':                         0.0,
            'self_remarks':                       False,
            'supervisor_score':                   0.0,
            'supervisor_remarks':                 False,
            'secondary_supervisor_score':         0.0,
            'secondary_supervisor_score_remarks': False,
            'reviewer_score':                     0.0,
            'reviewer_remarks':                   False,
        })

        # Clear competency scores
        if self.competency_score_ids:
            self.competency_score_ids.sudo().write({
                'self_score':                    0.0,
                'self_remarks':                  False,
                'supervisor_score':              0.0,
                'supervisor_remarks':            False,
                'secondary_supervisor_score':    0.0,
                'secondary_supervisor_remarks':  False,
                'reviewer_score':                0.0,
                'reviewer_remarks':              False,
            })

        # FIX: was fields.Datetime.now.strftime(...)
        self.with_context(skip_edit_check=True).write({
            'state':                'appraisal_draft',
            'appraisal_reset_date': fields.Datetime.now(),
        })

        if self.employee_id.user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.employee_id.user_id.id,
                summary=_('Your appraisal has been reset'),
                note=_('HR has reset your appraisal to draft. Please re-enter your self-rating.'),
            )

        self.message_post(
            body=f'Appraisal reset to draft by HR ({self.env.user.name}). All scores cleared.',
            message_type='notification',
        )
        return True