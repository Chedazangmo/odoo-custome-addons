from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare

DEFAULT_CEILING = 16.0


def _get_ceiling(env, competency_template_id):
    if not competency_template_id:
        return DEFAULT_CEILING
    appraisal_tmpl = env['appraisal.template'].search(
        [('competency_template_id', '=', competency_template_id)], limit=1,
    )
    if not appraisal_tmpl:
        return DEFAULT_CEILING
    allocation = appraisal_tmpl.score_allocation_id
    if not allocation:
        return DEFAULT_CEILING
    ceiling = allocation.competency_weight
    if float_compare(ceiling, 0.0, precision_digits=2) <= 0:
        return DEFAULT_CEILING
    return ceiling


def _is_linked_to_appraisal(env, competency_template_id):
    if not competency_template_id:
        return False
    return bool(env['appraisal.template'].search(
        [('competency_template_id', '=', competency_template_id)], limit=1,
    ))


_SYSTEM_FIELDS = frozenset({
    'competency_ceiling', 'total_hr_points', 'points_progress',
    'group_count', 'points_status', 'allocation_valid',
    'competency_table_html', 'is_skeleton',
})


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
        string='Total Assigned',
        compute='_compute_summary', store=True,
    )
    points_progress = fields.Char(
        string='Points Progress',
        compute='_compute_summary', store=True,
    )
    points_status = fields.Selection(
        selection=[
            ('under', 'Under Ceiling'),
            ('exact', 'At Ceiling'),
            ('over',  'Over Ceiling'),
        ],
        string='Points Status',
        compute='_compute_summary', store=True,
    )
    competency_ceiling = fields.Float(
        string='Competency Ceiling',
        digits=(16, 2),
        default=DEFAULT_CEILING,
        store=True,
        readonly=True,
        copy=False,
    )
    competency_table_html = fields.Html(
        string='Competency Table',
        compute='_compute_competency_table_html',
        store=False, readonly=True, sanitize=False,
    )
    allocation_valid = fields.Boolean(
        string='Allocation Valid',
        compute='_compute_allocation_valid',
        store=False,
    )
    is_skeleton = fields.Boolean(
        string='Skeleton (no allocation check)',
        default=False,
        store=True,
        copy=False,
    )

    @api.depends('group_ids.points', 'competency_ceiling', 'total_hr_points')
    def _compute_allocation_valid(self):
        for tmpl in self:
            ceiling = _get_ceiling(self.env, tmpl.id)
            total = sum(tmpl.group_ids.mapped('points'))
            tmpl.allocation_valid = (float_compare(total, ceiling, precision_digits=2) == 0)

    @api.depends('group_ids.points', 'competency_ceiling')
    def _compute_summary(self):
        for tmpl in self:
            ceiling = (
                tmpl.competency_ceiling
                if float_compare(tmpl.competency_ceiling, 0.0, precision_digits=2) > 0
                else _get_ceiling(self.env, tmpl.id)
            )
            total = sum(tmpl.group_ids.mapped('points'))
            tmpl.group_count     = len(tmpl.group_ids)
            tmpl.total_hr_points = total
            tmpl.points_progress = '{:.2f} / {:.2f}'.format(total, ceiling)
            cmp = float_compare(total, ceiling, precision_digits=2)
            tmpl.points_status   = 'exact' if cmp == 0 else ('over' if cmp > 0 else 'under')

    @api.depends(
        'group_ids', 'group_ids.hr_code', 'group_ids.name', 'group_ids.description',
        'group_ids.points', 'group_ids.points_status', 'group_ids.sequence',
        'group_ids.line_ids', 'group_ids.line_ids.full_code',
        'group_ids.line_ids.name', 'group_ids.line_ids.description',
        'group_ids.line_ids.points', 'group_ids.line_ids.sequence',
    )
    def _compute_competency_table_html(self):
        S = {
            'table':       'width:100%;border-collapse:collapse;font-size:0.88em;font-family:inherit;',
            'th':          ('background-color:#1a3c5e;color:#ffffff;font-size:0.75em;font-weight:700;'
                            'text-transform:uppercase;letter-spacing:0.06em;padding:10px 10px;'
                            'border-bottom:3px solid #e8a020;white-space:nowrap;text-align:left;'),
            'th_code':     'width:70px;text-align:center;',
            'th_pts':      'width:90px;text-align:right;',
            'th_targets':  'width:44%;',
            'grp_base':    ('font-weight:700;padding:10px 14px;border-top:3px solid #e8a020;'
                            'border-bottom:1px solid rgba(255,255,255,0.15);'),
            'grp_exact':   'background-color:#1a3c5e;color:#ffffff;',
            'grp_under':   'background-color:#134e6f;color:#fef3c7;',
            'grp_over':    'background-color:#7f1d1d;color:#fee2e2;',
            'grp_code':    ('font-family:monospace;font-size:0.82em;font-weight:700;'
                            'background-color:rgba(255,255,255,0.18);border-radius:3px;'
                            'padding:2px 8px;margin-right:10px;letter-spacing:0.04em;'),
            'grp_pts_lbl': ('font-size:0.78em;font-weight:600;text-transform:uppercase;'
                            'letter-spacing:0.05em;opacity:0.75;margin-right:4px;'),
            'grp_pts_val': 'font-size:1em;font-weight:700;',
            'grp_right':   'text-align:right;white-space:nowrap;',
            'grp_desc_base': ('padding:6px 14px 8px 14px;font-size:0.82em;font-style:italic;'
                              'border-bottom:2px solid rgba(232,160,32,0.4);'),
            'grp_desc_exact': 'background-color:#1a3c5e;color:rgba(255,255,255,0.75);',
            'grp_desc_under': 'background-color:#134e6f;color:rgba(254,243,199,0.80);',
            'grp_desc_over':  'background-color:#7f1d1d;color:rgba(254,226,226,0.80);',
            'even':        ('background-color:#ffffff;padding:8px 10px;'
                            'border-bottom:1px solid #e2e8f0;vertical-align:top;color:#1e293b;'),
            'odd':         ('background-color:#f8faff;padding:8px 10px;'
                            'border-bottom:1px solid #e2e8f0;vertical-align:top;color:#1e293b;'),
            'code_pill':   ('font-family:monospace;font-size:0.82em;font-weight:700;'
                            'color:#1d4ed8;background-color:#eff6ff;border:1px solid #93c5fd;'
                            'border-radius:4px;padding:2px 7px;display:inline-block;'),
            'td_code':     'text-align:center;width:70px;',
            'td_targets':  ('color:#334155;font-size:0.875em;word-break:break-word;'
                            'line-height:1.65;padding-top:6px;padding-bottom:6px;'),
            'td_pts':      'text-align:right;font-weight:600;white-space:nowrap;',
            'foot':        ('background-color:#dbeafe;border-top:2px solid #1a3c5e;'
                            'padding:8px 10px;font-weight:700;color:#0f172a;font-size:0.88em;'),
            'foot_pts':    'text-align:right;font-weight:700;',
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
                '<th style="{th}{th_code}">Sl. No</th>'
                '<th style="{th}">Competency</th>'
                '<th style="{th}{th_targets}">Targets</th>'
                '<th style="{th}{th_pts}">Points</th>'
                '<tr></thead><tbody>'.format(**S)
            ]

            total_pts = 0.0

            for group in tmpl.group_ids.sorted(key=lambda g: (g.sequence, g.id)):
                status    = group.points_status or 'under'
                grp_style = S['grp_base'] + S['grp_{}'.format(status)]
                grp_name  = (group.name or '').replace('<', '&lt;').replace('>', '&gt;')
                grp_code  = (group.hr_code or '').replace('<', '&lt;').replace('>', '&gt;')

                rows.append(
                    '<tr>'
                    '<td colspan="3" style="{gs}">'
                    '<span style="{gc}">{code}</span>{name}'
                    '</td>'
                    '<td style="{gs}{gr}">'
                    '<span style="{gl}">Group Points</span>'
                    '<span style="{gv}">{pts:.2f}</span>'
                    '</td>'
                    '</tr>'.format(
                        gs=grp_style, gc=S['grp_code'], gr=S['grp_right'],
                        gl=S['grp_pts_lbl'], gv=S['grp_pts_val'],
                        code=grp_code, name=grp_name, pts=group.points,
                    )
                )

                grp_desc = (group.description or '').strip()
                if grp_desc:
                    grp_desc_escaped = grp_desc.replace('<', '&lt;').replace('>', '&gt;')
                    grp_desc_style = S['grp_desc_base'] + S['grp_desc_{}'.format(status)]
                    rows.append(
                        '<tr>'
                        '<td colspan="4" style="{ds}">'
                        '<span style="font-weight:600;margin-right:6px;font-size:0.80em;'
                        'text-transform:uppercase;letter-spacing:0.05em;opacity:0.70;">'
                        'Targets:</span>{desc}'
                        '</td>'
                        '</tr>'.format(ds=grp_desc_style, desc=grp_desc_escaped)
                    )

                for i, line in enumerate(
                    group.line_ids.sorted(key=lambda l: (l.sequence, l.id))
                ):
                    td      = S['even'] if i % 2 == 0 else S['odd']
                    targets = (line.description or '').replace('<', '&lt;').replace('>', '&gt;')
                    lname   = (line.name or '').replace('<', '&lt;').replace('>', '&gt;')
                    code    = (line.full_code or '').replace('<', '&lt;').replace('>', '&gt;')

                    rows.append(
                        '<tr>'
                        '<td style="{td}{tc}"><span style="{cp}">{code}</span></td>'
                        '<td style="{td}">{name}</td>'
                        '<td style="{td}{tt}">{targets}</td>'
                        '<td style="{td}{tp}">{pts:.2f}</td>'
                        '</tr>'.format(
                            td=td, tc=S['td_code'], cp=S['code_pill'],
                            tt=S['td_targets'], tp=S['td_pts'],
                            code=code, name=lname, targets=targets, pts=line.points,
                        )
                    )
                    total_pts += line.points

            rows.append(
                '<tr>'
                '<td colspan="3" style="{f}">Total Points</td>'
                '<td style="{f}{fp}">{total:.2f}</td>'
                '</tr></tbody></table>'.format(
                    f=S['foot'], fp=S['foot_pts'], total=total_pts,
                )
            )
            tmpl.competency_table_html = ''.join(rows)

    def _sync_ceiling(self):
        for tmpl in self:
            new_ceiling = _get_ceiling(self.env, tmpl.id)
            if float_compare(new_ceiling, tmpl.competency_ceiling, precision_digits=2) != 0:
                tmpl.with_context(_resequencing=True).sudo().write(
                    {'competency_ceiling': new_ceiling}
                )
        self.invalidate_recordset(
            ['competency_ceiling', 'points_status', 'total_hr_points', 'points_progress']
        )
        self._compute_summary()

    def _check_exact_allocation(self):
        for tmpl in self:
            if tmpl.is_skeleton:
                continue
            ceiling = _get_ceiling(self.env, tmpl.id)
            total = sum(tmpl.group_ids.mapped('points'))
            if float_compare(total, ceiling, precision_digits=2) == 0:
                continue
            diff = abs(total - ceiling)
            if total < ceiling:
                raise ValidationError(_(
                    'Cannot save — incomplete allocation\n\n'
                    'Template "%(tmpl)s": %(total).2f / %(ceiling).2f pts.\n'
                    'Still need %(diff).2f more pts to reach exactly %(ceiling).2f.'
                ) % {'tmpl': tmpl.name, 'total': total, 'ceiling': ceiling, 'diff': diff})
            else:
                raise ValidationError(_(
                    'Cannot save — ceiling exceeded\n\n'
                    'Template "%(tmpl)s": %(total).2f / %(ceiling).2f pts.\n'
                    'Reduce by %(diff).2f pts to reach exactly %(ceiling).2f.'
                ) % {'tmpl': tmpl.name, 'total': total, 'ceiling': ceiling, 'diff': diff})

    @api.onchange('group_ids')
    def _onchange_group_ids(self):
        origin_id = self._origin.id if self._origin else None
        ceiling = _get_ceiling(self.env, origin_id) if origin_id else DEFAULT_CEILING
        total   = sum(self.group_ids.mapped('points'))
        cmp     = float_compare(total, ceiling, precision_digits=2)
        if cmp > 0:
            return {'warning': {
                'title':   _('Over Ceiling'),
                'message': _(
                    'Total is %(total).2f / %(ceiling).2f points — '
                    '%(excess).2f point(s) over. Reduce before saving.'
                ) % {'total': total, 'ceiling': ceiling, 'excess': total - ceiling},
            }}
        if cmp < 0:
            return {'warning': {
                'title':   _('Not Fully Allocated'),
                'message': _(
                    'Total is %(total).2f / %(ceiling).2f points — '
                    '%(rem).2f point(s) remaining. '
                    'Must reach %(ceiling).2f to save.'
                ) % {'total': total, 'ceiling': ceiling, 'rem': ceiling - total},
            }}

    @api.constrains('group_ids', 'total_hr_points')
    def _check_template_exact_allocation(self):
        for tmpl in self:
            if tmpl.is_skeleton:
                continue
            ceiling = _get_ceiling(self.env, tmpl.id)
            total   = sum(tmpl.group_ids.mapped('points'))
            if float_compare(total, ceiling, precision_digits=2) == 0:
                continue
            diff = abs(total - ceiling)
            if total < ceiling:
                raise ValidationError(_(
                    'Cannot save — incomplete allocation\n\n'
                    'Template "%(tmpl)s": %(total).2f / %(ceiling).2f pts allocated.\n'
                    'Still need %(diff).2f more pts to reach exactly %(ceiling).2f.'
                ) % {'tmpl': tmpl.name, 'total': total, 'ceiling': ceiling, 'diff': diff})
            else:
                raise ValidationError(_(
                    'Cannot save — ceiling exceeded\n\n'
                    'Template "%(tmpl)s": %(total).2f / %(ceiling).2f pts.\n'
                    'Reduce by %(diff).2f pts to reach exactly %(ceiling).2f.'
                ) % {'tmpl': tmpl.name, 'total': total, 'ceiling': ceiling, 'diff': diff})

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if not record.is_skeleton:
            record._check_exact_allocation()
        return record

    def write(self, vals):
        if self.env.context.get('_resequencing'):
            return super().write(vals)
        if vals and set(vals.keys()).issubset(_SYSTEM_FIELDS):
            return super().write(vals)

        skeletons = self.filtered('is_skeleton')
        if skeletons:
            skeletons.sudo().with_context(_resequencing=True).write({'is_skeleton': False})

        result = super().write(vals)
        for tmpl in self:
            tmpl._check_exact_allocation()
        return result

    def unlink(self):
        return super().unlink()


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
        string='Sl. No',
        compute='_compute_hr_code',
        store=True, readonly=True, copy=False, default=False,
    )
    name        = fields.Char(string='Competency Group', required=True)
    description = fields.Text(string='Description')
    points = fields.Float(
        string='Total Points',
        compute='_compute_points_from_lines',
        store=True, readonly=True, digits=(16, 2),
    )
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
            ('over',  'Over Allocated'),
        ],
        string='Status',
        compute='_compute_allocated_points', store=True,
    )
    competency_ceiling = fields.Float(
        string='Competency Ceiling',
        related='template_id.competency_ceiling',
        store=False, readonly=True,
    )
    template_ceiling = fields.Float(
        string='Template Ceiling',
        related='template_id.competency_ceiling',
        store=False, readonly=True,
    )
    template_total_points = fields.Float(
        string='Template Total Points',
        related='template_id.total_hr_points',
        store=False, readonly=True,
    )
    template_remaining = fields.Float(
        string='Template Remaining Points',
        compute='_compute_template_remaining',
        store=False, readonly=True,
    )

    @api.depends('template_id.competency_ceiling', 'template_id.total_hr_points')
    def _compute_template_remaining(self):
        for group in self:
            ceiling = group.template_id.competency_ceiling or DEFAULT_CEILING
            total   = group.template_id.total_hr_points or 0.0
            group.template_remaining = max(0.0, round(ceiling - total, 2))

    @api.depends('line_ids.points')
    def _compute_points_from_lines(self):
        for group in self:
            group.points = sum(group.line_ids.mapped('points'))

    @api.depends('template_id', 'template_id.group_ids', 'template_id.group_ids.sequence')
    def _compute_hr_code(self):
        tmpl_map = {}
        for group in self:
            tid = group.template_id.id
            if tid not in tmpl_map:
                tmpl_map[tid] = group.template_id.group_ids.sorted(
                    key=lambda g: (g.sequence, g.id)
                )
            siblings = tmpl_map[tid]
            pos = list(siblings.ids).index(group.id) + 1 if group.id in siblings.ids else 0
            group.hr_code = str(pos) if pos else False

    @api.depends('line_ids')
    def _compute_line_count(self):
        for group in self:
            group.line_count = len(group.line_ids)

    @api.depends('line_ids.points', 'points')
    def _compute_allocated_points(self):
        for group in self:
            group.allocated_points = group.points
            group.remaining_points = 0.0
            group.points_status    = 'exact'

    @api.constrains('points')
    def _check_group_points_not_negative(self):
        for rec in self:
            if float_compare(rec.points, 0.0, precision_digits=2) < 0:
                raise ValidationError(
                    _('Group "%s": Points cannot be negative.') % rec.name
                )

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
        return records

    def write(self, vals):
        if self.env.context.get('_resequencing'):
            return super().write(vals)
        return super().write(vals)

    def unlink(self):
        tmpl_ids = {rec.template_id.id for rec in self} - {False}
        result   = super().unlink()
        if not self.env.context.get('_resequencing'):
            for tid in tmpl_ids:
                self._resequence_codes(tid)
        return result

    def _resequence_codes(self, template_id):
        if not template_id or self.env.context.get('_resequencing'):
            return
        env  = self.env(context=dict(self.env.context, _resequencing=True))
        tmpl = env['competency.framework.template'].browse(template_id)
        if not tmpl.exists():
            return
        all_groups = tmpl.group_ids.sorted(key=lambda g: (g.sequence, g.id))
        all_lines  = self.env['competency.framework.line'].browse()
        for grp_pos, grp in enumerate(all_groups, start=1):
            grp.sudo().write({'hr_code': str(grp_pos)})
            siblings = grp.line_ids.sorted(key=lambda l: (l.sequence, l.id))
            for line_pos, line in enumerate(siblings, start=1):
                line.sudo().write({'full_code': '{}.{}'.format(grp_pos, line_pos)})
            all_lines |= siblings
        all_groups.invalidate_recordset(['hr_code'])
        if all_lines:
            all_lines.invalidate_recordset(['full_code'])
        ceiling = _get_ceiling(env, template_id)
        total   = sum(all_groups.mapped('points'))
        cmp     = float_compare(total, ceiling, precision_digits=2)
        tmpl.sudo().write({
            'competency_ceiling': ceiling,
            'total_hr_points':    total,
            'points_progress':    '{:.2f} / {:.2f}'.format(total, ceiling),
            'group_count':        len(all_groups),
            'points_status':      'exact' if cmp == 0 else ('over' if cmp > 0 else 'under'),
        })
        tmpl.invalidate_recordset(
            ['competency_ceiling', 'total_hr_points', 'points_progress',
             'group_count', 'points_status']
        )


class CompetencyFrameworkLine(models.Model):
    _name = 'competency.framework.line'
    _description = 'Competency Framework Line'
    _order = 'sequence, id'

    sequence    = fields.Integer(string='Sequence', default=10)
    group_id    = fields.Many2one(
        'competency.framework.group', string='Competency Group',
        required=True, ondelete='cascade',
    )
    full_code   = fields.Char(
        string='Sl. No',
        compute='_compute_full_code',
        store=True, readonly=True, default=False,
    )
    name        = fields.Char(string='Competency', required=True)
    description = fields.Text(string='Competency Targets')
    points      = fields.Float(string='Points', required=True, default=0.0)

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
        string='Group Sl. No',
        related='group_id.hr_code', store=False, readonly=True,
    )
    group_remaining_points = fields.Float(
        string='Group Remaining Points',
        related='group_id.remaining_points', store=False, readonly=True,
    )
    template_ceiling = fields.Float(
        string='Template Ceiling',
        related='group_id.template_id.competency_ceiling',
        store=False, readonly=True,
    )
    template_remaining = fields.Float(
        string='Template Remaining',
        related='group_id.template_remaining',
        store=False, readonly=True,
    )

    @api.depends(
        'group_id', 'group_id.hr_code', 'group_id.line_ids',
        'group_id.line_ids.sequence', 'sequence',
    )
    def _compute_full_code(self):
        grp_map = {}
        for line in self:
            gid = line.group_id.id
            if gid not in grp_map:
                grp_map[gid] = line.group_id.line_ids.sorted(
                    key=lambda l: (l.sequence, l.id)
                )
            siblings = grp_map[gid]
            grp_code = line.group_id.hr_code or ''
            pos      = list(siblings.ids).index(line.id) + 1 if line.id in siblings.ids else 0
            line.full_code = '{}.{}'.format(grp_code, pos) if grp_code and pos else False

    def _get_remaining_points_for_template(self):
        if not self.template_id:
            return DEFAULT_CEILING
        ceiling     = self.template_id.competency_ceiling or DEFAULT_CEILING
        other_total = 0.0
        for group in self.template_id.group_ids:
            for ln in group.line_ids:
                if ln.id != self.id:
                    other_total += ln.points or 0.0
        return max(0.0, round(ceiling - other_total, 2))

    @api.onchange('points')
    def _onchange_line_points(self):
        new_val = self.points or 0.0
        if float_compare(new_val, 0.0, precision_digits=2) < 0:
            self.points = 0.0
            return {'warning': {
                'title':   _('Invalid Value'),
                'message': _('Points cannot be negative. Value has been reset to 0.'),
            }}
        if self.group_id and self.template_id:
            remaining   = self._get_remaining_points_for_template()
            max_allowed = remaining
            if float_compare(new_val, max_allowed, precision_digits=2) > 0:
                self.points = max_allowed
                return {'warning': {
                    'title':   _('Ceiling Exceeded — Value Clamped'),
                    'message': _(
                        'Points clamped to %(max).2f.\n\n'
                        'Template ceiling: %(ceiling).2f\n'
                        'Remaining available: %(remaining).2f'
                    ) % {
                        'max':       max_allowed,
                        'ceiling':   self.template_id.competency_ceiling or DEFAULT_CEILING,
                        'remaining': remaining,
                    },
                }}

    @api.constrains('points', 'group_id')
    def _check_line_points_ceiling(self):
        templates_checked = set()
        for line in self:
            if not line.template_id or line.template_id.id in templates_checked:
                continue
            templates_checked.add(line.template_id.id)
            tmpl    = line.template_id
            ceiling = (
                tmpl.competency_ceiling
                if float_compare(tmpl.competency_ceiling, 0.0, precision_digits=2) > 0
                else _get_ceiling(self.env, tmpl.id)
            )
            total_points = sum(
                ln.points or 0.0
                for group in tmpl.group_ids
                for ln in group.line_ids
            )
            if float_compare(total_points, ceiling, precision_digits=2) > 0:
                excess = total_points - ceiling
                raise ValidationError(_(
                    'Ceiling Violation\n\n'
                    'Total competency points (%.2f) exceed the template ceiling of %.2f.\n'
                    'Excess: %.2f points.\n\n'
                    'Please reduce points before saving.'
                ) % (total_points, ceiling, excess))

    @api.constrains('points', 'group_id')
    def _check_line_points_sum_matches_group_total(self):
        groups_checked = set()
        for line in self:
            group = line.group_id
            if not group or group.id in groups_checked:
                continue
            groups_checked.add(group.id)
            total_line_points = sum(group.line_ids.mapped('points'))
            if float_compare(total_line_points, group.points, precision_digits=2) != 0:
                raise ValidationError(_(
                    'Group "%(group)s": sum of line points (%(line_sum).2f) does not equal '
                    'group total (%(group_sum).2f). Please check your data.'
                ) % {
                    'group':     group.name,
                    'line_sum':  total_line_points,
                    'group_sum': group.points,
                })

    @api.constrains('points')
    def _check_points_not_negative(self):
        for rec in self:
            if float_compare(rec.points, 0.0, precision_digits=2) < 0:
                raise ValidationError(
                    _('Line "%s": Points cannot be negative.') % rec.name
                )

    @api.model_create_multi
    def create(self, vals_list):
        processed_vals_list = []
        for vals in vals_list:
            pts      = vals.get('points', 0.0) or 0.0
            group_id = vals.get('group_id')
            if not group_id:
                processed_vals_list.append(vals)
                continue
            group = self.env['competency.framework.group'].browse(group_id)
            if not group.exists() or not group.template_id:
                processed_vals_list.append(vals)
                continue
            tmpl    = group.template_id
            ceiling = (
                tmpl.competency_ceiling
                if float_compare(tmpl.competency_ceiling, 0.0, precision_digits=2) > 0
                else _get_ceiling(self.env, tmpl.id)
            )
            current_total = sum(
                ln.points or 0.0
                for g in tmpl.group_ids
                for ln in g.line_ids
            )
            available = max(0.0, round(ceiling - current_total, 2))
            if float_compare(pts, 0.0, precision_digits=2) == 0 and float_compare(available, 0.0, precision_digits=2) > 0:
                pts = available
                vals = dict(vals, points=pts)
            new_total = current_total + pts
            if float_compare(new_total, ceiling, precision_digits=2) > 0:
                raise ValidationError(_(
                    'Cannot Add Line\n\n'
                    'Cannot add line with %.2f points.\n\n'
                    'Template ceiling:      %.2f\n'
                    'Currently allocated:   %.2f\n'
                    'Available capacity:    %.2f\n\n'
                    'Please reduce points or free up space first.'
                ) % (pts, ceiling, current_total, available))
            processed_vals_list.append(vals)
        records = super().create(processed_vals_list)
        if not self.env.context.get('_resequencing'):
            self._resequence({rec.template_id.id for rec in records})
        return records

    def write(self, vals):
        if self.env.context.get('_resequencing'):
            return super().write(vals)
        if 'points' in vals:
            for line in self:
                new_points = vals['points']
                old_points = line.points
                if float_compare(old_points, new_points, precision_digits=2) == 0:
                    continue
                if not line.template_id:
                    continue
                tmpl    = line.template_id
                ceiling = (
                    tmpl.competency_ceiling
                    if float_compare(tmpl.competency_ceiling, 0.0, precision_digits=2) > 0
                    else _get_ceiling(self.env, tmpl.id)
                )
                other_total = sum(
                    ln.points or 0.0
                    for group in tmpl.group_ids
                    for ln in group.line_ids
                    if ln.id != line.id
                )
                new_total = other_total + new_points
                if float_compare(new_total, ceiling, precision_digits=2) > 0:
                    max_allowed = max(0.0, round(ceiling - other_total, 2))
                    raise ValidationError(_(
                        'Points Violation\n\n'
                        'Cannot set points to %.2f.\n\n'
                        'Template Maximum:               %.2f\n'
                        'Already allocated (other lines): %.2f\n'
                        'Maximum allowed for this line:   %.2f\n\n'
                        'Please enter a lower value.'
                    ) % (new_points, ceiling, other_total, max_allowed))
        pre_tmpl_ids  = {rec.template_id.id for rec in self}
        result        = super().write(vals)
        post_tmpl_ids = {rec.template_id.id for rec in self}
        all_tmpl_ids  = (pre_tmpl_ids | post_tmpl_ids) - {False, None}
        self._resequence(all_tmpl_ids)
        return result

    def unlink(self):
        tmpl_ids = {rec.template_id.id for rec in self}
        result   = super().unlink()
        if not self.env.context.get('_resequencing'):
            self._resequence(tmpl_ids)
        return result

    def _resequence(self, template_ids):
        grp_model = self.env['competency.framework.group']
        done = set()
        for tid in template_ids - {False, None}:
            if tid not in done:
                grp_model._resequence_codes(tid)
                done.add(tid)