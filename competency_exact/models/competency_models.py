# ============================================================
# models/competency_models.py
# ============================================================
#
# Auto-numbering rules
# --------------------
#   Group code : sequential integer "1", "2", "3" …
#                ordered by (sequence, id) within the template.
#                Computed, stored, readonly — never user-editable.
#                Shown read-only in the group form header bar only.
#
#   Line code  : "GROUP_POS.LINE_POS"  e.g. "1.1", "1.2", "2.1"
#                Computed, stored, readonly — never user-editable.
#                Shown read-only in lines table + HTML table.
#
# Both codes recalculate automatically whenever groups or lines
# are reordered, added, or deleted.
#
# Autosave rules
# --------------
#   The template form uses auto_save="1" (set in views.xml).
#   Autosave passes carry context {'autosave': True} so that
#   under-allocation does NOT block the save while the user is
#   still distributing points across groups/lines.
#
# Validation rules (Template level)
# ----------------------------------
#   Over-allocation  : BLOCKED immediately.
#   Under-allocation : Allowed while editing; blocked on manual save.
#   HR Points reduce : Blocked if new value < sum already in groups.
#
# Validation rules (Group level — Competency Lines popup)
# --------------------------------------------------------
#   Line over-allocation  : BLOCKED immediately.
#   Line equality (manual save) : sum of line points MUST equal group
#                                 points; under-allocation blocked on
#                                 deliberate save (allowed on autosave).
# ============================================================

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


# ============================================================
# COMPETENCY FRAMEWORK TEMPLATE
# ============================================================

class CompetencyFrameworkTemplate(models.Model):
    _name        = 'competency.framework.template'
    _description = 'Competency Framework Template'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'name'

    # ── Fields ────────────────────────────────────────────────

    name = fields.Char(
        string='Template Name',
        required=True,
        tracking=True,
    )

    description = fields.Text(string='Description')

    total_hr_points = fields.Float(
        string='Total HR Points',
        required=True,
        default=0.0,
        tracking=True,
        help=(
            'Total points defined by HR for this framework. '
            'The sum of all competency group points must equal this value.'
        ),
    )

    group_ids = fields.One2many(
        'competency.framework.group',
        'template_id',
        string='Competency Groups',
    )

    group_count = fields.Integer(
        string='No. of Groups',
        compute='_compute_group_count',
        store=True,
    )

    total_group_points = fields.Float(
        string='Total Group Points',
        compute='_compute_total_group_points',
        store=True,
        help='Sum of all competency group points in this template.',
    )

    points_status = fields.Selection(
        selection=[
            ('under', 'Under Allocated'),
            ('exact', 'Fully Allocated'),
            ('over',  'Over Allocated'),
        ],
        string='Points Status',
        compute='_compute_total_group_points',
        store=True,
    )

    remaining_hr_points = fields.Float(
        string='Remaining HR Points',
        compute='_compute_total_group_points',
        store=True,
        help='HR points not yet assigned to any group (total_hr_points - total_group_points).',
    )

    competency_table_html = fields.Html(
        string='Competency Table',
        compute='_compute_competency_table_html',
        store=False,
        readonly=True,
        sanitize=False,
    )

    # ── Computes ──────────────────────────────────────────────

    @api.depends('group_ids')
    def _compute_group_count(self):
        for tmpl in self:
            tmpl.group_count = len(tmpl.group_ids)

    @api.depends('group_ids.points', 'total_hr_points')
    def _compute_total_group_points(self):
        for tmpl in self:
            total = sum(tmpl.group_ids.mapped('points'))
            tmpl.total_group_points  = total
            tmpl.remaining_hr_points = tmpl.total_hr_points - total
            cmp = float_compare(total, tmpl.total_hr_points, precision_digits=2)
            if cmp < 0:
                tmpl.points_status = 'under'
            elif cmp == 0:
                tmpl.points_status = 'exact'
            else:
                tmpl.points_status = 'over'

    # ── HTML competency table (Tab 2) ─────────────────────────

    @api.depends(
        'group_ids',
        'group_ids.hr_code',
        'group_ids.name',
        'group_ids.points',
        'group_ids.allocated_points',
        'group_ids.points_status',
        'group_ids.line_ids',
        'group_ids.line_ids.full_code',
        'group_ids.line_ids.name',
        'group_ids.line_ids.description',
        'group_ids.line_ids.points',
    )
    def _compute_competency_table_html(self):
        S = {
            # ── Table shell ───────────────────────────────────────────
            'table':         'width:100%;border-collapse:collapse;font-size:0.88em;font-family:inherit;',

            # ── Column-header cells ───────────────────────────────────
            'th':            ('background-color:#1a3c5e;color:#ffffff;font-size:0.75em;font-weight:700;'
                              'text-transform:uppercase;letter-spacing:0.06em;padding:10px 10px;'
                              'border-bottom:3px solid #e8a020;white-space:nowrap;text-align:left;'),
            'th_code':       'width:70px;text-align:center;',
            'th_pts':        'width:90px;text-align:right;',
            'th_targets':    'width:44%;',

            # ── Group header row ──────────────────────────────────────
            'grp_base':      ('font-weight:700;padding:10px 14px;'
                              'border-top:3px solid #e8a020;'
                              'border-bottom:1px solid rgba(255,255,255,0.15);'),
            'grp_exact':     'background-color:#1a3c5e;color:#ffffff;',
            'grp_under':     'background-color:#134e6f;color:#fef3c7;',
            'grp_over':      'background-color:#7f1d1d;color:#fee2e2;',

            # ── Group-header sub-elements ─────────────────────────────
            'grp_code_pill': ('font-family:monospace;font-size:0.82em;font-weight:700;'
                              'background-color:rgba(255,255,255,0.18);border-radius:3px;'
                              'padding:2px 8px;margin-right:10px;letter-spacing:0.04em;'),
            'grp_pts_lbl':   ('font-size:0.78em;font-weight:600;text-transform:uppercase;'
                              'letter-spacing:0.05em;opacity:0.75;margin-right:4px;'),
            'grp_pts_val':   'font-size:1em;font-weight:700;',
            'grp_right':     'text-align:right;white-space:nowrap;',

            # ── Competency line rows ───────────────────────────────────
            'line_even':     ('background-color:#ffffff;padding:8px 10px;'
                              'border-bottom:1px solid #e2e8f0;vertical-align:top;color:#1e293b;'),
            'line_odd':      ('background-color:#f8faff;padding:8px 10px;'
                              'border-bottom:1px solid #e2e8f0;vertical-align:top;color:#1e293b;'),
            'code_pill':     ('font-family:monospace;font-size:0.82em;font-weight:700;'
                              'color:#1d4ed8;background-color:#eff6ff;border:1px solid #93c5fd;'
                              'border-radius:4px;padding:2px 7px;display:inline-block;'),
            'td_code':       'text-align:center;width:70px;',
            'td_targets':    ('color:#334155;font-size:0.875em;word-break:break-word;'
                              'line-height:1.65;padding-top:6px;padding-bottom:6px;'),
            'td_pts':        'text-align:right;font-weight:600;white-space:nowrap;',

            # ── Footer row ────────────────────────────────────────────
            'foot':          ('background-color:#dbeafe;border-top:2px solid #1a3c5e;'
                              'padding:8px 10px;font-weight:700;color:#0f172a;font-size:0.88em;'),
            'foot_pts':      'text-align:right;font-weight:700;',
        }

        for tmpl in self:
            if not tmpl.group_ids:
                tmpl.competency_table_html = (
                    '<p style="color:#94a3b8;font-size:0.9em;padding:16px;">'
                    'No competency groups defined yet.</p>'
                )
                continue

            # 4 columns: Code | Competency | Targets | Points
            rows = [
                f'<table style="{S["table"]}"><thead><tr>'
                f'<th style="{S["th"]}{S["th_code"]}">Code</th>'
                f'<th style="{S["th"]}">Competency</th>'
                f'<th style="{S["th"]}{S["th_targets"]}">Targets</th>'
                f'<th style="{S["th"]}{S["th_pts"]}">Points</th>'
                f'</tr></thead><tbody>'
            ]

            total_pts = 0.0

            for group in tmpl.group_ids.sorted(key=lambda g: (g.sequence, g.id)):
                status    = group.points_status or 'under'
                grp_style = S['grp_base'] + S[f'grp_{status}']
                grp_name  = (group.name or '').replace('<', '&lt;').replace('>', '&gt;')
                grp_code  = (group.hr_code or '').replace('<', '&lt;').replace('>', '&gt;')

                rows.append(
                    f'<tr>'
                    f'<td colspan="3" style="{grp_style}">'
                    f'  <span style="{S["grp_code_pill"]}">{grp_code}</span>'
                    f'  {grp_name}'
                    f'</td>'
                    f'<td style="{grp_style}{S["grp_right"]}">'
                    f'  <span style="{S["grp_pts_lbl"]}">Group Pts</span>'
                    f'  <span style="{S["grp_pts_val"]}">{group.points:.2f}</span>'
                    f'</td>'
                    f'</tr>'
                )

                for i, line in enumerate(group.line_ids.sorted(key=lambda l: (l.sequence, l.id))):
                    td      = S['line_even'] if i % 2 == 0 else S['line_odd']
                    targets = (line.description or '').replace('<', '&lt;').replace('>', '&gt;')
                    lname   = (line.name or '').replace('<', '&lt;').replace('>', '&gt;')
                    code    = (line.full_code or '').replace('<', '&lt;').replace('>', '&gt;')
                    rows.append(
                        f'<tr>'
                        f'<td style="{td}{S["td_code"]}"><span style="{S["code_pill"]}">{code}</span></td>'
                        f'<td style="{td}">{lname}</td>'
                        f'<td style="{td}{S["td_targets"]}">{targets}</td>'
                        f'<td style="{td}{S["td_pts"]}">{line.points:.2f}</td>'
                        f'</tr>'
                    )
                    total_pts += line.points

            rows.append(
                f'<tr>'
                f'<td colspan="3" style="{S["foot"]}">Total HR Points</td>'
                f'<td style="{S["foot"]}{S["foot_pts"]}">{total_pts:.2f}</td>'
                f'</tr></tbody></table>'
            )
            tmpl.competency_table_html = ''.join(rows)

    # ── Create override ───────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    # ── Export wizard action ──────────────────────────────────

    def action_open_export_wizard(self):
        """
        Opens the Export to Excel wizard pre-filled with this template.
        Called by the 'Export to Excel' button in the form header via
        type="object" — avoids any XML ID cross-reference between
        competency_views.xml and competency_export_wizard_views.xml.
        """
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      _('Export to Excel'),
            'res_model': 'competency.export.wizard',
            'view_mode': 'form',
            'target':    'new',
            'context': {
                'default_template_id': self.id,
            },
        }

    # ── Onchanges ─────────────────────────────────────────────

    @api.onchange('total_hr_points')
    def _onchange_total_hr_points(self):
        """Warn immediately if user tries to reduce HR points below committed group total."""
        if not self.group_ids:
            return
        total = sum(self.group_ids.mapped('points'))
        if float_compare(total, self.total_hr_points, precision_digits=2) > 0:
            return {
                'warning': {
                    'title': _('Cannot Reduce HR Points'),
                    'message': _(
                        'Groups already have %(total).2f pts assigned. '
                        'Reduce group points to %(hr).2f first.'
                    ) % {'total': total, 'hr': self.total_hr_points},
                }
            }

    @api.onchange('group_ids')
    def _onchange_group_ids(self):
        """
        Scenario A - new empty row added but budget is already exhausted:
            Immediate warning - row addition blocked by JS guard.
        Scenario B - edited points push total over HR ceiling:
            Immediate over-allocation warning.
        """
        hr    = self.total_hr_points
        total = sum(self.group_ids.mapped('points'))

        # Scenario A: budget exhausted, new empty row appended
        new_zero_rows = [g for g in self.group_ids if not g.id and g.points == 0.0]
        if new_zero_rows:
            budget_before = total - sum(r.points for r in new_zero_rows)
            if float_compare(budget_before, hr, precision_digits=2) >= 0:
                return {
                    'warning': {
                        'title': _('No Points Remaining'),
                        'message': _(
                            'All %(hr).2f HR point(s) are fully allocated. '
                            'Increase Total HR Points or reduce an existing group to add a new one.'
                        ) % {'hr': hr},
                    }
                }

        # Scenario B: over-allocation after points entry
        cmp = float_compare(total, hr, precision_digits=2)
        if cmp > 0:
            return {
                'warning': {
                    'title': _('Over-Allocated'),
                    'message': _(
                        'Group points total (%(total).2f) exceeds HR Points (%(hr).2f) '
                        'by %(excess).2f pt(s). Reduce group points before saving.'
                    ) % {'total': total, 'hr': hr, 'excess': total - hr},
                }
            }

    # ── Autosave helper ───────────────────────────────────────

    def _autosave_if_complete(self):
        for tmpl in self:
            if tmpl.id and tmpl.name and tmpl.total_hr_points > 0:
                tmpl.with_context(autosave=True).write({})

    # ── Constraints ───────────────────────────────────────────

    @api.constrains('total_hr_points')
    def _check_total_hr_points_not_negative(self):
        for rec in self:
            if float_compare(rec.total_hr_points, 0.0, precision_digits=2) < 0:
                raise ValidationError(_(
                    'Total HR Points cannot be negative.'
                ))

    @api.constrains('total_hr_points', 'group_ids')
    def _check_total_hr_points_not_below_groups(self):
        for tmpl in self:
            if not tmpl.group_ids:
                continue
            total = sum(tmpl.group_ids.mapped('points'))
            if float_compare(total, tmpl.total_hr_points, precision_digits=2) > 0:
                raise ValidationError(_(
                    '"%(tmpl)s": Cannot reduce Total HR Points to %(hr).2f - '
                    'groups already have %(total).2f pts assigned. '
                    'Reduce group points first.'
                ) % {
                    'tmpl':  tmpl.name,
                    'total': total,
                    'hr':    tmpl.total_hr_points,
                })

    @api.constrains('total_hr_points', 'group_ids')
    def _check_total_hr_points_equals_groups(self):
        autosave = self.env.context.get('autosave', False)

        for tmpl in self:
            if not tmpl.group_ids:
                continue

            total = sum(tmpl.group_ids.mapped('points'))
            cmp   = float_compare(total, tmpl.total_hr_points, precision_digits=2)

            if cmp > 0:
                raise ValidationError(_(
                    '"%(tmpl)s": Group points (%(total).2f) exceed HR Points (%(hr).2f) '
                    'by %(excess).2f pt(s). Reduce group points before saving.'
                ) % {
                    'tmpl':   tmpl.name,
                    'total':  total,
                    'hr':     tmpl.total_hr_points,
                    'excess': total - tmpl.total_hr_points,
                })

            if cmp < 0 and not autosave:
                raise ValidationError(_(
                    '"%(tmpl)s": %(remaining).2f pt(s) still unassigned. '
                    'Distribute all points across groups before saving.'
                ) % {
                    'tmpl':      tmpl.name,
                    'remaining': tmpl.total_hr_points - total,
                })

    _check_hr_points_positive = models.Constraint(
        'CHECK(total_hr_points >= 0)',
        'Total HR Points must be zero or positive.',
    )


# ============================================================
# COMPETENCY FRAMEWORK GROUP
# ============================================================

class CompetencyFrameworkGroup(models.Model):
    _name        = 'competency.framework.group'
    _description = 'Competency Framework Group'
    _order       = 'sequence, id'

    # ── Fields ────────────────────────────────────────────────

    template_id = fields.Many2one(
        'competency.framework.template',
        string='Template',
        ondelete='cascade',
        index=True,
    )

    sequence = fields.Integer(string='Sequence', default=10)

    hr_code = fields.Char(
        string='Code',
        compute='_compute_hr_code',
        store=True,
        readonly=True,
        copy=False,
        help='Auto-assigned sequential number based on group order within the template.',
    )

    name        = fields.Char(string='Competency Group', required=True)
    description = fields.Text(string='Description')

    points = fields.Float(
        string='Group Points',
        required=True,
        default=0.0,
    )

    line_ids = fields.One2many(
        'competency.framework.line',
        'group_id',
        string='Competency Lines',
    )

    line_count = fields.Integer(
        string='No. of Lines',
        compute='_compute_line_count',
        store=True,
    )

    allocated_points = fields.Float(
        string='Allocated Points',
        compute='_compute_allocated_points',
        store=True,
    )

    remaining_points = fields.Float(
        string='Remaining Points',
        compute='_compute_allocated_points',
        store=True,
    )

    points_status = fields.Selection(
        selection=[
            ('under', 'Under Allocated'),
            ('exact', 'Fully Allocated'),
            ('over',  'Over Allocated'),
        ],
        string='Status',
        compute='_compute_allocated_points',
        store=True,
    )

    # ── Computes ──────────────────────────────────────────────

    @api.depends('template_id', 'template_id.group_ids', 'sequence')
    def _compute_hr_code(self):
        for tmpl in self.mapped('template_id').filtered('id'):
            for pos, grp in enumerate(
                tmpl.group_ids.sorted(key=lambda g: (g.sequence, g.id)), start=1
            ):
                grp.hr_code = str(pos)

        for grp in self.filtered(lambda g: not g.template_id):
            grp.hr_code = False

    @api.depends('line_ids')
    def _compute_line_count(self):
        for group in self:
            group.line_count = len(group.line_ids)

    @api.depends('line_ids.points', 'points')
    def _compute_allocated_points(self):
        for group in self:
            allocated              = sum(group.line_ids.mapped('points'))
            group.allocated_points = allocated
            group.remaining_points = group.points - allocated
            cmp = float_compare(allocated, group.points, precision_digits=2)
            if cmp < 0:
                group.points_status = 'under'
            elif cmp == 0:
                group.points_status = 'exact'
            else:
                group.points_status = 'over'

    # ── Onchanges ─────────────────────────────────────────────

    @api.onchange('points')
    def _onchange_group_points(self):
        """
        Check 1 - Template HR-points ceiling exceeded.
        Check 2 - Group points reduced below committed line points.
        """
        # Check 1: template ceiling
        if self.template_id and self.template_id.total_hr_points:
            other_points       = sum(g.points for g in self.template_id.group_ids if g != self)
            new_template_total = other_points + (self.points or 0.0)
            hr                 = self.template_id.total_hr_points

            if float_compare(new_template_total, hr, precision_digits=2) > 0:
                return {
                    'warning': {
                        'title': _('Exceeds HR Points'),
                        'message': _(
                            'This would bring the template total to %(new_total).2f, '
                            'exceeding HR Points (%(hr).2f) by %(excess).2f pt(s).'
                        ) % {
                            'new_total': new_template_total,
                            'hr':        hr,
                            'excess':    new_template_total - hr,
                        },
                    }
                }

        # Check 2: line-points floor
        if self.line_ids:
            allocated = sum(self.line_ids.mapped('points'))
            if float_compare(allocated, self.points, precision_digits=2) > 0:
                return {
                    'warning': {
                        'title': _('Group Points Too Low'),
                        'message': _(
                            'Lines already have %(allocated).2f pts assigned. '
                            'Group points cannot be less than %(allocated).2f.'
                        ) % {'allocated': allocated},
                    }
                }

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        """
        Scenario A - new empty line added but group budget is fully committed:
            Immediate warning - line addition blocked by JS guard.
        Scenario B - line points push group total over its ceiling:
            Immediate over-allocation warning.
        """
        group_ceiling = self.points or 0.0
        current_total = sum(self.line_ids.mapped('points'))

        # Scenario A: budget exhausted, new empty row appended
        new_zero_rows = [l for l in self.line_ids if not l.id and l.points == 0.0]
        if new_zero_rows:
            budget_before = current_total - sum(r.points for r in new_zero_rows)
            if float_compare(budget_before, group_ceiling, precision_digits=2) >= 0:
                return {
                    'warning': {
                        'title': _('No Points Remaining'),
                        'message': _(
                            'All %(ceiling).2f pt(s) for "%(group)s" are fully allocated. '
                            'Increase Group Points or reduce an existing line to add a new one.'
                        ) % {
                            'ceiling': group_ceiling,
                            'group':   self.name or '',
                        },
                    }
                }

        # Scenario B: over-allocation after points entry
        cmp = float_compare(current_total, group_ceiling, precision_digits=2)
        if cmp > 0:
            return {
                'warning': {
                    'title': _('Over-Allocated'),
                    'message': _(
                        'Line points (%(total).2f) exceed Group Points (%(ceiling).2f) '
                        'by %(excess).2f pt(s). Reduce line points before saving.'
                    ) % {
                        'total':   current_total,
                        'ceiling': group_ceiling,
                        'excess':  current_total - group_ceiling,
                    },
                }
            }

    # ── Constraints ───────────────────────────────────────────

    @api.constrains('points')
    def _check_group_points_not_negative(self):
        for rec in self:
            if float_compare(rec.points, 0.0, precision_digits=2) < 0:
                raise ValidationError(_(
                    'Group "%s": Points cannot be negative.'
                ) % rec.name)

    @api.constrains('points', 'line_ids')
    def _check_group_points_equal_lines(self):
        """
        On save: sum of line points must equal group points (when lines exist).
        Over-allocation always blocked; under-allocation skipped on autosave.
        """
        autosave = self.env.context.get('autosave', False)

        for group in self:
            if not group.line_ids:
                continue
            allocated = sum(group.line_ids.mapped('points'))
            cmp       = float_compare(allocated, group.points, precision_digits=2)

            if cmp > 0:
                raise ValidationError(_(
                    'Group "%(group)s": Line points (%(allocated).2f) exceed '
                    'Group Points (%(total).2f) by %(excess).2f pt(s). Reduce line points.'
                ) % {
                    'group':     group.name,
                    'allocated': allocated,
                    'total':     group.points,
                    'excess':    allocated - group.points,
                })

            if cmp < 0 and not autosave:
                raise ValidationError(_(
                    'Group "%(group)s": %(remaining).2f pt(s) still unassigned. '
                    'Distribute all points across lines before saving.'
                ) % {
                    'group':     group.name,
                    'remaining': group.points - allocated,
                })

    @api.constrains('points', 'template_id')
    def _check_group_points_vs_template(self):
        """Hard DB guard: block over-allocation at group-save time."""
        for tmpl in self.mapped('template_id').filtered('id'):
            if not tmpl.group_ids:
                continue
            total = sum(tmpl.group_ids.mapped('points'))
            if float_compare(total, tmpl.total_hr_points, precision_digits=2) > 0:
                raise ValidationError(_(
                    'Template "%(tmpl)s": Group points (%(total).2f) exceed '
                    'HR Points (%(hr).2f) by %(excess).2f pt(s). Reduce group points.'
                ) % {
                    'tmpl':   tmpl.name,
                    'total':  total,
                    'hr':     tmpl.total_hr_points,
                    'excess': total - tmpl.total_hr_points,
                })

    _check_points_positive = models.Constraint(
        'CHECK(points >= 0)',
        'Group points must be zero or positive.',
    )


# ============================================================
# COMPETENCY FRAMEWORK LINE
# ============================================================

class CompetencyFrameworkLine(models.Model):
    _name        = 'competency.framework.line'
    _description = 'Competency Framework Line'
    _order       = 'sequence, id'

    # ── Fields ────────────────────────────────────────────────

    sequence = fields.Integer(string='Sequence', default=10)

    group_id = fields.Many2one(
        'competency.framework.group',
        string='Competency Group',
        required=True,
        ondelete='cascade',
    )

    full_code = fields.Char(
        string='Code',
        compute='_compute_full_code',
        store=True,
        readonly=True,
    )

    name        = fields.Char(string='Competency', required=True)
    description = fields.Text(string='Competency Targets')
    points      = fields.Float(string='Points', required=True, default=0.0)

    # ── Related fields ────────────────────────────────────────

    template_id = fields.Many2one(
        'competency.framework.template',
        string='Template',
        related='group_id.template_id',
        store=True,
        readonly=True,
    )

    group_points = fields.Float(
        string='Group Points',
        related='group_id.points',
        store=False,
        readonly=True,
    )

    group_points_status = fields.Selection(
        string='Status',
        related='group_id.points_status',
        store=False,
        readonly=True,
    )

    group_hr_code = fields.Char(
        string='Group Code',
        related='group_id.hr_code',
        store=False,
        readonly=True,
    )

    # ── Compute: full_code ────────────────────────────────────

    @api.depends(
        'group_id',
        'group_id.sequence',
        'group_id.hr_code',
        'group_id.template_id',
        'group_id.template_id.group_ids',
        'sequence',
    )
    def _compute_full_code(self):
        template_group_order = {}

        for line in self:
            if not line.group_id:
                line.full_code = False
                continue

            group = line.group_id
            tmpl  = group.template_id

            if tmpl and tmpl.id:
                if tmpl.id not in template_group_order:
                    template_group_order[tmpl.id] = tmpl.group_ids.sorted(
                        key=lambda g: (g.sequence, g.id)
                    )
                ordered_groups = template_group_order[tmpl.id]
            else:
                ordered_groups = self.env['competency.framework.group'].search(
                    [], order='sequence, id'
                )

            grp_pos = next(
                (i for i, g in enumerate(ordered_groups, start=1) if g.id == group.id),
                0,
            )
            if not grp_pos:
                line.full_code = False
                continue

            siblings = self.env['competency.framework.line'].search(
                [('group_id', '=', group.id)],
                order='sequence, id',
            )
            line_pos = next(
                (i for i, s in enumerate(siblings, start=1) if s.id == line.id),
                len(siblings) + 1,
            )

            line.full_code = f"{grp_pos}.{line_pos}"

    # ── Onchange ──────────────────────────────────────────────

    @api.onchange('points')
    def _onchange_line_points(self):
        """Immediately warn when a line's points push the group total over its ceiling."""
        if not self.group_id:
            return

        siblings_total = sum(l.points for l in self.group_id.line_ids if l != self)
        new_total      = siblings_total + (self.points or 0.0)

        if float_compare(new_total, self.group_id.points, precision_digits=2) > 0:
            excess = new_total - self.group_id.points
            return {
                'warning': {
                    'title': _('Exceeds Group Points'),
                    'message': _(
                        'Line total would be %(new_total).2f, exceeding '
                        '"%(group)s" ceiling of %(ceiling).2f by %(excess).2f pt(s). '
                        'Reduce this line\'s points.'
                    ) % {
                        'new_total': new_total,
                        'group':     self.group_id.name,
                        'ceiling':   self.group_id.points,
                        'excess':    excess,
                    },
                }
            }

    # ── Constraints ───────────────────────────────────────────

    @api.constrains('points')
    def _check_points_not_negative(self):
        for rec in self:
            if float_compare(rec.points, 0.0, precision_digits=2) < 0:
                raise ValidationError(_(
                    'Line "%s": Points cannot be negative.'
                ) % rec.name)

    @api.constrains('points', 'group_id')
    def _check_line_points_vs_group(self):
        """Hard DB constraint: over-allocation of a group by its lines is always blocked."""
        for group in self.mapped('group_id'):
            if not group.line_ids:
                continue
            allocated = sum(group.line_ids.mapped('points'))
            if float_compare(allocated, group.points, precision_digits=2) > 0:
                raise ValidationError(_(
                    'Group "%(group)s": Line points (%(allocated).2f) exceed '
                    'Group Points (%(ceiling).2f) by %(excess).2f pt(s). Reduce line points.'
                ) % {
                    'group':     group.name,
                    'allocated': allocated,
                    'ceiling':   group.points,
                    'excess':    allocated - group.points,
                })

    _check_points_positive = models.Constraint(
        'CHECK(points >= 0)',
        'Line points must be zero or positive.',
    )