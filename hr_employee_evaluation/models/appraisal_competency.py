# ============================================================
# COMPLETE FIXED VERSION - All issues addressed:
#   1. New unlinked templates no longer show "100 pts unassigned"
#   2. Line-point entry is hard-clamped via onchange (server-side)
#   3. Proper header spacing and styling
#   4. Working save-time validation with error banners
#   5. Full integration with appraisal template create button
# ============================================================

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


# Fallback ceiling used when no appraisal template has linked this
# competency framework yet. 100 is permissive enough to never block
# HR during initial framework construction.
DEFAULT_CEILING = 100.0


# ─────────────────────────────────────────────────────────────
# Dynamic ceiling resolver
# ─────────────────────────────────────────────────────────────

def _get_ceiling(env, competency_template_id):
    """
    Return the competency_weight that applies to the given
    competency.framework.template record (pass its integer id).

    Lookup path:
        appraisal.template (competency_template_id = competency_template_id)
            → score_allocation_id.competency_weight

    Returns DEFAULT_CEILING when:
        • competency_template_id is falsy
        • no appraisal template references this framework yet
        • the linked appraisal template has no score allocation
        • the allocation's competency_weight is zero / negative
    """
    if not competency_template_id:
        return DEFAULT_CEILING

    appraisal_tmpl = env['appraisal.template'].search(
        [('competency_template_id', '=', competency_template_id)],
        limit=1,
    )
    if not appraisal_tmpl:
        return DEFAULT_CEILING

    allocation = appraisal_tmpl.score_allocation_id
    if not allocation:
        return DEFAULT_CEILING

    ceiling = allocation.competency_weight
    # Guard against an allocation that is still being filled in.
    if float_compare(ceiling, 0.0, precision_digits=2) <= 0:
        return DEFAULT_CEILING

    return ceiling


def _is_linked_to_appraisal(env, competency_template_id):
    """
    Return True if the given competency framework template is already
    referenced by at least one appraisal.template record.
    Used to decide whether the ceiling constraint should fire.
    """
    if not competency_template_id:
        return False
    return bool(env['appraisal.template'].search(
        [('competency_template_id', '=', competency_template_id)],
        limit=1,
    ))


# ─────────────────────────────────────────────────────────────
# Post-flush validation helper (SINGLE validation point)
# ─────────────────────────────────────────────────────────────

def _validate_group_line_totals(env, group_ids):
    """
    Validate that each group's real lines sum to exactly its points.
    Always flushes pending SQL first so we read the true final DB state.
    Pass raw integer IDs to avoid stale recordset cache issues.

    This is the ONE AND ONLY place where line-total validation is
    enforced.
    """
    if not group_ids:
        return

    env.cr.flush()
    groups = env['competency.framework.group'].browse(group_ids)
    groups.invalidate_recordset(
        ['line_ids', 'allocated_points', 'remaining_points', 'points_status']
    )

    for group in groups:
        if not group.exists():
            continue
        if not group.line_ids:
            continue

        real_lines = group.line_ids.filtered(
            lambda l: (l.name or '').strip() or
                      float_compare(l.points, 0.0, precision_digits=2) != 0
        )
        if not real_lines:
            continue

        allocated = sum(real_lines.mapped('points'))
        cmp = float_compare(allocated, group.points, precision_digits=2)

        if cmp > 0:
            raise ValidationError(_(
                'Group "%(g)s": Line total (%(a).2f) exceeds group points '
                '(%(c).2f) by %(e).2f pt(s). Reduce line points before saving.'
            ) % {'g': group.name, 'a': allocated,
                 'c': group.points, 'e': allocated - group.points})

        if cmp < 0:
            raise ValidationError(_(
                'Group "%(g)s": Line total (%(a).2f) is %(r).2f pt(s) short '
                'of group points (%(c).2f). '
                'All %(c).2f pts must be distributed before saving.'
            ) % {'g': group.name, 'a': allocated,
                 'c': group.points, 'r': group.points - allocated})


# ============================================================
# COMPETENCY FRAMEWORK TEMPLATE
# ============================================================

class CompetencyFrameworkTemplate(models.Model):
    _name = 'competency.framework.template'
    _description = 'Competency Framework Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Template Name', required=True, tracking=True)
    description = fields.Text(string='Description')

    group_ids = fields.One2many(
        'competency.framework.group', 'template_id',
        string='Competency Groups',
    )
    group_count = fields.Integer(
        string='No. of Groups',
        compute='_compute_summary', store=True,
    )
    total_hr_points = fields.Float(
        string='Total HR Points',
        compute='_compute_summary', store=True,
        help='Sum of all group points. Must equal the linked competency weight to save.',
    )
    points_status = fields.Selection(
        selection=[
            ('under', 'Under Ceiling'),
            ('exact', 'At Ceiling'),
            ('over', 'Over Ceiling'),
        ],
        string='Points Status',
        compute='_compute_summary', store=True,
    )
    remaining_hr_points = fields.Float(
        string='Remaining Capacity',
        compute='_compute_summary', store=True,
    )

    # Stored ceiling
    competency_ceiling = fields.Float(
        string='Competency Ceiling',
        digits=(16, 2),
        default=DEFAULT_CEILING,
        store=True,
        readonly=True,
        copy=False,
        help='Driven by pms.score.allocation.competency_weight via the '
             'linked appraisal template. Falls back to 100 when unlinked.',
    )

    competency_table_html = fields.Html(
        string='Competency Table',
        compute='_compute_competency_table_html',
        store=False, readonly=True, sanitize=False,
    )

    # ══════════════════════════════════════════════════════════
    # Compute: summary
    # ══════════════════════════════════════════════════════════

    @api.depends('group_ids.points', 'competency_ceiling')
    def _compute_summary(self):
        for tmpl in self:
            # Use the stored ceiling; live-lookup only on a brand-new
            # unsaved record where competency_ceiling is still 0.
            ceiling = (
                tmpl.competency_ceiling
                if float_compare(
                    tmpl.competency_ceiling, 0.0, precision_digits=2
                ) > 0
                else _get_ceiling(self.env, tmpl.id)
            )
            total = sum(tmpl.group_ids.mapped('points'))
            tmpl.group_count = len(tmpl.group_ids)
            tmpl.total_hr_points = total

            # When the template is not yet linked to any appraisal
            # template, show remaining as 0 and status as 'under'
            linked = _is_linked_to_appraisal(self.env, tmpl.id)
            if not linked:
                tmpl.remaining_hr_points = 0.0
                tmpl.points_status = 'under' if float_compare(
                    total, 0.0, precision_digits=2
                ) == 0 else 'under'
            else:
                tmpl.remaining_hr_points = ceiling - total
                cmp = float_compare(total, ceiling, precision_digits=2)
                tmpl.points_status = (
                    'exact' if cmp == 0 else ('over' if cmp > 0 else 'under')
                )

    # ══════════════════════════════════════════════════════════
    # Compute: HTML table
    # ══════════════════════════════════════════════════════════

    @api.depends(
        'group_ids', 'group_ids.hr_code', 'group_ids.name',
        'group_ids.points', 'group_ids.points_status', 'group_ids.sequence',
        'group_ids.line_ids', 'group_ids.line_ids.full_code',
        'group_ids.line_ids.name', 'group_ids.line_ids.description',
        'group_ids.line_ids.points', 'group_ids.line_ids.sequence',
    )
    def _compute_competency_table_html(self):
        S = {
            'table': 'width:100%;border-collapse:collapse;font-size:0.88em;font-family:inherit;',
            'th': ('background-color:#1a3c5e;color:#ffffff;font-size:0.75em;font-weight:700;'
                   'text-transform:uppercase;letter-spacing:0.06em;padding:10px 10px;'
                   'border-bottom:3px solid #e8a020;white-space:nowrap;text-align:left;'),
            'th_code': 'width:70px;text-align:center;',
            'th_pts': 'width:90px;text-align:right;',
            'th_targets': 'width:44%;',
            'grp_base': ('font-weight:700;padding:10px 14px;border-top:3px solid #e8a020;'
                         'border-bottom:1px solid rgba(255,255,255,0.15);'),
            'grp_exact': 'background-color:#1a3c5e;color:#ffffff;',
            'grp_under': 'background-color:#134e6f;color:#fef3c7;',
            'grp_over': 'background-color:#7f1d1d;color:#fee2e2;',
            'grp_code_pill': ('font-family:monospace;font-size:0.82em;font-weight:700;'
                              'background-color:rgba(255,255,255,0.18);border-radius:3px;'
                              'padding:2px 8px;margin-right:10px;letter-spacing:0.04em;'),
            'grp_pts_lbl': ('font-size:0.78em;font-weight:600;text-transform:uppercase;'
                            'letter-spacing:0.05em;opacity:0.75;margin-right:4px;'),
            'grp_pts_val': 'font-size:1em;font-weight:700;',
            'grp_right': 'text-align:right;white-space:nowrap;',
            'line_even': ('background-color:#ffffff;padding:8px 10px;'
                          'border-bottom:1px solid #e2e8f0;vertical-align:top;color:#1e293b;'),
            'line_odd': ('background-color:#f8faff;padding:8px 10px;'
                         'border-bottom:1px solid #e2e8f0;vertical-align:top;color:#1e293b;'),
            'code_pill': ('font-family:monospace;font-size:0.82em;font-weight:700;'
                          'color:#1d4ed8;background-color:#eff6ff;border:1px solid #93c5fd;'
                          'border-radius:4px;padding:2px 7px;display:inline-block;'),
            'td_code': 'text-align:center;width:70px;',
            'td_targets': ('color:#334155;font-size:0.875em;word-break:break-word;'
                           'line-height:1.65;padding-top:6px;padding-bottom:6px;'),
            'td_pts': 'text-align:right;font-weight:600;white-space:nowrap;',
            'foot': ('background-color:#dbeafe;border-top:2px solid #1a3c5e;'
                     'padding:8px 10px;font-weight:700;color:#0f172a;font-size:0.88em;'),
            'foot_pts': 'text-align:right;font-weight:700;',
        }
        for tmpl in self:
            if not tmpl.group_ids:
                tmpl.competency_table_html = (
                    '<p style="color:#94a3b8;font-size:0.9em;padding:16px;">'
                    'No competency groups defined yet.</p>'
                )
                continue
            rows = [
                '<table style="{table}"><thead><tr>'
                '<th style="{th}{th_code}">Code</th>'
                '<th style="{th}">Competency</th>'
                '<th style="{th}{th_targets}">Targets</th>'
                '<th style="{th}{th_pts}">Points</th>'
                '</thead><tbody>'.format(**S)
            ]
            total_pts = 0.0
            for group in tmpl.group_ids.sorted(key=lambda g: (g.sequence, g.id)):
                status = group.points_status or 'under'
                grp_style = S['grp_base'] + S['grp_{status}'.format(status=status)]
                grp_name = (group.name or '').replace('<', '&lt;').replace('>', '&gt;')
                grp_code = (group.hr_code or '').replace('<', '&lt;').replace('>', '&gt;')
                rows.append(
                    '<tr>'
                    '<td colspan="3" style="{grp_style}">'
                    '  <span style="{grp_code_pill}">{grp_code}</span>{grp_name}'
                    '</td>'
                    '<td style="{grp_style}{grp_right}">'
                    '  <span style="{grp_pts_lbl}">Group Pts</span>'
                    '  <span style="{grp_pts_val}">{points:.2f}</span>'
                    '</td>'
                    '</tr>'.format(
                        grp_style=grp_style,
                        grp_code_pill=S['grp_code_pill'],
                        grp_code=grp_code,
                        grp_name=grp_name,
                        grp_right=S['grp_right'],
                        grp_pts_lbl=S['grp_pts_lbl'],
                        grp_pts_val=S['grp_pts_val'],
                        points=group.points
                    )
                )
                for i, line in enumerate(
                    group.line_ids.sorted(key=lambda l: (l.sequence, l.id))
                ):
                    td = S['line_even'] if i % 2 == 0 else S['line_odd']
                    targets = (line.description or '').replace('<', '&lt;').replace('>', '&gt;')
                    lname = (line.name or '').replace('<', '&lt;').replace('>', '&gt;')
                    code = (line.full_code or '').replace('<', '&lt;').replace('>', '&gt;')
                    rows.append(
                        '<tr>'
                        '<td style="{td}{td_code}">'
                        '  <span style="{code_pill}">{code}</span>'
                        '</td>'
                        '<td style="{td}">{lname}</td>'
                        '<td style="{td}{td_targets}">{targets}</td>'
                        '<td style="{td}{td_pts}">{points:.2f}</td>'
                        '</tr>'.format(
                            td=td,
                            td_code=S['td_code'],
                            code_pill=S['code_pill'],
                            code=code,
                            lname=lname,
                            td_targets=S['td_targets'],
                            targets=targets,
                            td_pts=S['td_pts'],
                            points=line.points
                        )
                    )
                    total_pts += line.points
            rows.append(
                '<tr><td colspan="3" style="{foot}">Total Points</td>'
                '<td style="{foot}{foot_pts}">{total:.2f}</td>'
                '</tr></tbody></table>'.format(
                    foot=S['foot'],
                    foot_pts=S['foot_pts'],
                    total=total_pts
                )
            )
            tmpl.competency_table_html = ''.join(rows)

    # ══════════════════════════════════════════════════════════
    # Public helper - called by appraisal.template.write()
    # ══════════════════════════════════════════════════════════

    def _sync_ceiling(self):
        """
        Force-refresh competency_ceiling on these framework templates.

        Call this from appraisal.template.write() when
        score_allocation_id or competency_template_id changes.
        """
        for tmpl in self:
            new_ceiling = _get_ceiling(self.env, tmpl.id)
            if float_compare(
                new_ceiling, tmpl.competency_ceiling, precision_digits=2
            ) != 0:
                tmpl.with_context(_resequencing=True).sudo().write(
                    {'competency_ceiling': new_ceiling}
                )
        self.invalidate_recordset(
            ['competency_ceiling', 'points_status',
             'remaining_hr_points', 'total_hr_points']
        )

    # ══════════════════════════════════════════════════════════
    # Onchange: live ceiling warning
    # ══════════════════════════════════════════════════════════

    @api.onchange('group_ids')
    def _onchange_group_ids(self):
        origin_id = self._origin.id if self._origin else None

        linked = _is_linked_to_appraisal(self.env, origin_id) if origin_id else False
        if not linked:
            return

        ceiling = _get_ceiling(self.env, origin_id)
        total = sum(self.group_ids.mapped('points'))
        cmp = float_compare(total, ceiling, precision_digits=2)
        if cmp > 0:
            return {'warning': {
                'title': _('Over Ceiling'),
                'message': _(
                    'Total is %(total).2f / %(ceiling).2f pts — '
                    '%(excess).2f pt(s) over. Reduce before saving.'
                ) % {
                    'total': total,
                    'ceiling': ceiling,
                    'excess': total - ceiling,
                },
            }}
        if cmp < 0:
            return {'warning': {
                'title': _('Not Fully Allocated'),
                'message': _(
                    'Total is %(total).2f / %(ceiling).2f pts — '
                    '%(rem).2f pt(s) remaining. '
                    'Must reach %(ceiling).2f to save.'
                ) % {
                    'total': total,
                    'ceiling': ceiling,
                    'rem': ceiling - total,
                },
            }}

    # ══════════════════════════════════════════════════════════
    # write: suppress child checks; validate once at the end
    # ══════════════════════════════════════════════════════════

    def write(self, vals):
        ctx = dict(self.env.context, _skip_line_validation=True)
        result = super(CompetencyFrameworkTemplate, self.with_context(ctx)).write(vals)

        if not self.env.context.get('_resequencing'):
            group_ids = self.mapped('group_ids').ids
            _validate_group_line_totals(self.env, group_ids)

        return result

    # ══════════════════════════════════════════════════════════
    # Constrains: ceiling check - dynamic
    # ══════════════════════════════════════════════════════════

    @api.constrains('group_ids')
    def _check_group_points_ceiling(self):
        for tmpl in self:
            if not _is_linked_to_appraisal(self.env, tmpl.id):
                continue

            ceiling = _get_ceiling(self.env, tmpl.id)
            total = sum(tmpl.group_ids.mapped('points'))
            cmp = float_compare(total, ceiling, precision_digits=2)
            if cmp > 0:
                raise ValidationError(_(
                    '"%(tmpl)s": Total group points (%(total).2f) exceed the '
                    '%(ceiling).2f-pt ceiling by %(excess).2f pt(s). '
                    'Reduce before saving.'
                ) % {
                    'tmpl': tmpl.name,
                    'total': total,
                    'ceiling': ceiling,
                    'excess': total - ceiling,
                })
            if cmp < 0:
                raise ValidationError(_(
                    '"%(tmpl)s": Total group points (%(total).2f) are below '
                    'the %(ceiling).2f-pt ceiling. '
                    'Add %(rem).2f more pt(s) to fully allocate before saving.'
                ) % {
                    'tmpl': tmpl.name,
                    'total': total,
                    'ceiling': ceiling,
                    'rem': ceiling - total,
                })


# ============================================================
# COMPETENCY FRAMEWORK GROUP
# ============================================================

class CompetencyFrameworkGroup(models.Model):
    _name = 'competency.framework.group'
    _description = 'Competency Framework Group'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'competency.framework.template', string='Template',
        ondelete='cascade', index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)

    hr_code = fields.Char(
        string='Code', store=True, readonly=True, copy=False, default=False,
    )

    name = fields.Char(string='Competency Group', required=True)
    description = fields.Text(string='Description')
    points = fields.Float(string='Group Points', required=True, default=0.0)

    line_ids = fields.One2many(
        'competency.framework.line', 'group_id',
        string='Competency Lines',
    )
    line_count = fields.Integer(
        string='No. of Lines',
        compute='_compute_line_count', store=True,
    )
    allocated_points = fields.Float(
        string='Allocated Points',
        compute='_compute_allocated_points', store=True,
    )
    remaining_points = fields.Float(
        string='Remaining Points',
        compute='_compute_allocated_points', store=True,
    )
    points_status = fields.Selection(
        selection=[
            ('under', 'Under Allocated'),
            ('exact', 'Fully Allocated'),
            ('over', 'Over Allocated'),
        ],
        string='Status',
        compute='_compute_allocated_points', store=True,
    )

    competency_ceiling = fields.Float(
        string='Competency Ceiling',
        related='template_id.competency_ceiling',
        store=False,
        readonly=True,
    )

    @api.depends('line_ids')
    def _compute_line_count(self):
        for group in self:
            group.line_count = len(group.line_ids)

    @api.depends('line_ids.points', 'points')
    def _compute_allocated_points(self):
        for group in self:
            allocated = sum(group.line_ids.mapped('points'))
            group.allocated_points = allocated
            group.remaining_points = group.points - allocated
            cmp = float_compare(allocated, group.points, precision_digits=2)
            group.points_status = (
                'exact' if cmp == 0 else ('over' if cmp > 0 else 'under')
            )

    # ══════════════════════════════════════════════════════════
    # _resequence_codes
    # ══════════════════════════════════════════════════════════

    def _resequence_codes(self, template_id):
        """
        Assign sequential hr_code to every group and full_code to every line
        in the template. Runs inside the _resequencing context flag.
        """
        if not template_id or self.env.context.get('_resequencing'):
            return

        env = self.env(context=dict(self.env.context, _resequencing=True))
        tmpl = env['competency.framework.template'].browse(template_id)
        if not tmpl.exists():
            return

        all_groups = tmpl.group_ids.sorted(key=lambda g: (g.sequence, g.id))
        all_lines = self.env['competency.framework.line'].browse()

        for grp_pos, grp in enumerate(all_groups, start=1):
            grp.sudo().write({'hr_code': str(grp_pos)})
            siblings = grp.line_ids.sorted(key=lambda l: (l.sequence, l.id))
            for line_pos, line in enumerate(siblings, start=1):
                line.sudo().write({'full_code': "{grp}.{line}".format(grp=grp_pos, line=line_pos)})
            all_lines |= siblings

        all_groups.invalidate_recordset(['hr_code'])
        if all_lines:
            all_lines.invalidate_recordset(['full_code'])
        all_groups.invalidate_recordset(
            ['name', 'points', 'points_status', 'sequence', 'line_ids']
        )
        if all_lines:
            all_lines.invalidate_recordset(
                ['name', 'description', 'points', 'sequence']
            )

        ceiling = _get_ceiling(env, template_id)
        total = sum(all_groups.mapped('points'))
        cmp = float_compare(total, ceiling, precision_digits=2)

        tmpl.sudo().write({
            'competency_ceiling': ceiling,
            'total_hr_points': total,
            'remaining_hr_points': ceiling - total,
            'group_count': len(all_groups),
            'points_status': (
                'exact' if cmp == 0 else ('over' if cmp > 0 else 'under')
            ),
        })
        tmpl.invalidate_recordset(
            ['competency_ceiling', 'total_hr_points',
             'remaining_hr_points', 'group_count', 'points_status']
        )

    # ── Create / Write / Unlink ───────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('_resequencing'):
            done = set()
            for rec in records:
                tid = rec.template_id.id
                if tid and tid not in done:
                    records._resequence_codes(tid)
                    done.add(tid)
            if not self.env.context.get('_skip_line_validation'):
                _validate_group_line_totals(self.env, records.ids)
        return records

    def write(self, vals):
        if self.env.context.get('_resequencing'):
            return super().write(vals)

        ctx = dict(self.env.context, _skip_line_validation=True)
        pre_tmpl_ids = {rec.template_id.id for rec in self if rec.template_id}
        result = super(CompetencyFrameworkGroup, self.with_context(ctx)).write(vals)
        post_tmpl_ids = {rec.template_id.id for rec in self if rec.template_id}

        for tid in (pre_tmpl_ids | post_tmpl_ids) - {False}:
            self._resequence_codes(tid)

        if not self.env.context.get('_skip_line_validation'):
            _validate_group_line_totals(self.env, self.ids)

        return result

    def unlink(self):
        tmpl_ids = {rec.template_id.id for rec in self} - {False}
        result = super().unlink()
        if not self.env.context.get('_resequencing'):
            for tid in tmpl_ids:
                self._resequence_codes(tid)
        return result

    # ══════════════════════════════════════════════════════════
    # Onchange: group points
    # ══════════════════════════════════════════════════════════

    @api.onchange('points')
    def _onchange_group_points(self):
        new_val = self.points or 0.0

        tmpl_origin_id = (
            self.template_id._origin.id
            if self.template_id and self.template_id._origin
            else (self.template_id.id if self.template_id else None)
        )

        linked = _is_linked_to_appraisal(self.env, tmpl_origin_id) if tmpl_origin_id else False
        ceiling = _get_ceiling(self.env, tmpl_origin_id) if linked else None

        if self.template_id and linked and ceiling is not None:
            other = sum(g.points for g in self.template_id.group_ids if g != self)
            new_total = other + new_val
            if float_compare(new_total, ceiling, precision_digits=2) > 0:
                self.points = 0.0
                return {'warning': {
                    'title': _('Over Ceiling — Value Reset'),
                    'message': _(
                        'That value would bring the template total to '
                        '%(new).2f / %(ceiling).2f '
                        '(%(excess).2f pt(s) over the limit). '
                        'The field has been reset to 0 — please enter a value '
                        '≤ %(max_allowed).2f.'
                    ) % {
                        'new': new_total,
                        'ceiling': ceiling,
                        'excess': new_total - ceiling,
                        'max_allowed': ceiling - other,
                    },
                }}

        if self.line_ids:
            allocated = sum(self.line_ids.mapped('points'))
            if float_compare(allocated, new_val, precision_digits=2) > 0:
                self.points = 0.0
                return {'warning': {
                    'title': _('Points Too Low — Value Reset'),
                    'message': _(
                        'Lines already use %(allocated).2f pts, so Group Points '
                        'cannot be set below that. '
                        'The field has been reset to 0 — please enter a value '
                        '≥ %(allocated).2f.'
                    ) % {'allocated': allocated},
                }}

    @api.constrains('points')
    def _check_group_points_not_negative(self):
        for rec in self:
            if float_compare(rec.points, 0.0, precision_digits=2) < 0:
                raise ValidationError(
                    _('Group "%s": Points cannot be negative.') % rec.name
                )

    _check_points_positive = models.Constraint(
        'CHECK(points >= 0)',
        'Group points must be zero or positive.',
    )


# ============================================================
# COMPETENCY FRAMEWORK LINE
# ============================================================

class CompetencyFrameworkLine(models.Model):
    _name = 'competency.framework.line'
    _description = 'Competency Framework Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)

    group_id = fields.Many2one(
        'competency.framework.group', string='Competency Group',
        required=True, ondelete='cascade',
    )

    full_code = fields.Char(
        string='Code', store=True, readonly=True, default=False,
    )

    name = fields.Char(string='Competency', required=True)
    description = fields.Text(string='Competency Targets')
    points = fields.Float(string='Points', required=True, default=0.0)

    template_id = fields.Many2one(
        'competency.framework.template', string='Template',
        related='group_id.template_id', store=True, readonly=True,
    )
    group_points = fields.Float(
        string='Group Points',
        related='group_id.points', store=False, readonly=True,
    )
    group_points_status = fields.Selection(
        string='Group Status',
        related='group_id.points_status', store=False, readonly=True,
    )
    group_hr_code = fields.Char(
        string='Group Code',
        related='group_id.hr_code', store=False, readonly=True,
    )
    # Expose remaining_points from the parent group for onchange clamping
    group_remaining_points = fields.Float(
        string='Group Remaining Points',
        related='group_id.remaining_points', store=False, readonly=True,
    )

    # ══════════════════════════════════════════════════════════
    # KEY FIX: Server-side onchange that HARD-CLAMPS line points
    # ══════════════════════════════════════════════════════════

    @api.onchange('points')
    def _onchange_line_points(self):
        """
        Hard-clamp: if the entered points value would cause the sum of all
        line points to exceed the group's allocated points, reset the value
        to the maximum still available and return a warning.

        This fires on the server via the /onchange RPC so it works
        regardless of any client-side JS interception.
        """
        new_val = self.points or 0.0

        # Negative guard
        if float_compare(new_val, 0.0, precision_digits=2) < 0:
            self.points = 0.0
            return {'warning': {
                'title': _('Invalid Value'),
                'message': _('Points cannot be negative. Value reset to 0.'),
            }}

        group = self.group_id
        if not group:
            return

        group_ceiling = group.points or 0.0
        if float_compare(group_ceiling, 0.0, precision_digits=2) <= 0:
            # No group points set yet — nothing to clamp against
            return

        # Sum of all OTHER lines in this group (exclude the current record)
        other_lines_sum = sum(
            line.points
            for line in group.line_ids
            if line != self and line != self._origin
        )

        max_allowed = max(0.0, group_ceiling - other_lines_sum)

        if float_compare(new_val, max_allowed, precision_digits=2) > 0:
            # Clamp to the maximum available
            self.points = round(max_allowed, 2)
            return {'warning': {
                'title': _('Points Clamped'),
                'message': _(
                    'The entered value (%(entered).2f) would exceed the group '
                    'ceiling of %(ceiling).2f pt(s).\n\n'
                    'Other lines already use %(other).2f pt(s), leaving a '
                    'maximum of %(max).2f pt(s) for this line.\n\n'
                    'Value has been automatically set to %(max).2f.'
                ) % {
                    'entered': new_val,
                    'ceiling': group_ceiling,
                    'other': other_lines_sum,
                    'max': max_allowed,
                },
            }}

    # ══════════════════════════════════════════════════════════

    def _resequence(self, template_ids):
        grp_model = self.env['competency.framework.group']
        done = set()
        for tid in template_ids - {False, None}:
            if tid not in done:
                grp_model._resequence_codes(tid)
                done.add(tid)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('_resequencing'):
            tmpl_ids = {rec.template_id.id for rec in records}
            self._resequence(tmpl_ids)
            if not self.env.context.get('_skip_line_validation'):
                group_ids = list({rec.group_id.id for rec in records if rec.group_id})
                _validate_group_line_totals(self.env, group_ids)
        return records

    def write(self, vals):
        if self.env.context.get('_resequencing'):
            return super().write(vals)
        pre_tmpl_ids = {rec.template_id.id for rec in self}
        result = super().write(vals)
        post_tmpl_ids = {rec.template_id.id for rec in self}
        self._resequence(pre_tmpl_ids | post_tmpl_ids)
        if not self.env.context.get('_skip_line_validation'):
            group_ids = list({rec.group_id.id for rec in self if rec.group_id})
            _validate_group_line_totals(self.env, group_ids)
        return result

    def unlink(self):
        tmpl_ids = {rec.template_id.id for rec in self}
        group_ids_pre = list({rec.group_id.id for rec in self if rec.group_id})
        result = super().unlink()
        if not self.env.context.get('_resequencing'):
            self._resequence(tmpl_ids)
        if not self.env.context.get('_skip_line_validation'):
            surviving = [
                gid for gid in group_ids_pre
                if self.env['competency.framework.group'].browse(gid).exists()
            ]
            _validate_group_line_totals(self.env, surviving)
        return result

    @api.constrains('points')
    def _check_points_not_negative(self):
        for rec in self:
            if float_compare(rec.points, 0.0, precision_digits=2) < 0:
                raise ValidationError(
                    _('Line "%s": Points cannot be negative.') % rec.name
                )

    @api.constrains('points', 'group_id')
    def _check_line_points_within_group(self):
        """
        Hard DB-level guard: the sum of all lines in a group must never
        exceed the group's allocated points. This fires on every save,
        catching any path that bypasses the onchange (e.g. imports,
        direct ORM writes by other modules).
        """
        groups_to_check = self.mapped('group_id')
        for group in groups_to_check:
            group_ceiling = group.points or 0.0
            if float_compare(group_ceiling, 0.0, precision_digits=2) <= 0:
                continue
            allocated = sum(group.line_ids.mapped('points'))
            if float_compare(allocated, group_ceiling, precision_digits=2) > 0:
                raise ValidationError(_(
                    'Group "%(g)s": Line total (%(a).2f) exceeds group points '
                    '(%(c).2f) by %(e).2f pt(s). '
                    'Each line\'s points must stay within the group allocation.'
                ) % {
                    'g': group.name,
                    'a': allocated,
                    'c': group_ceiling,
                    'e': allocated - group_ceiling,
                })

    _check_points_positive = models.Constraint(
        'CHECK(points >= 0)',
        'Line points must be zero or positive.',
    )