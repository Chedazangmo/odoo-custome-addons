# models/appraisal_competency_score.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_compare


class AppraisalCompetencyScore(models.Model):
    _name        = 'appraisal.competency.score'
    _description = 'Appraisal Competency Score'
    _order       = 'group_sequence, group_id, line_sequence, id'

    appraisal_id = fields.Many2one(
        'pms.appraisal',
        string='Appraisal',
        required=True,
        ondelete='cascade',
        index=True,
    )

    competency_line_id = fields.Many2one(
        'competency.framework.line',
        string='Competency Line',
        required=True,
        ondelete='restrict',
    )


    group_id = fields.Many2one(
        'competency.framework.group',
        string='Competency Group',
        related='competency_line_id.group_id',
        store=True,
        readonly=True,
    )
    group_name = fields.Char(
        string='Group Name',
        related='competency_line_id.group_id.name',
        store=True,
        readonly=True,
    )
    group_sequence = fields.Integer(
        string='Group Sequence',
        related='competency_line_id.group_id.sequence',
        store=True,
        readonly=True,
    )
    group_hr_code = fields.Char(
        string='Group Code',
        related='competency_line_id.group_id.hr_code',
        store=True,
        readonly=True,
    )
    line_name = fields.Char(
        string='Competency',
        related='competency_line_id.name',
        store=True,
        readonly=True,
    )
    line_description = fields.Text(
        string='Targets',
        related='competency_line_id.description',
        store=True,
        readonly=True,
    )
    line_full_code = fields.Char(
        string='Code',
        related='competency_line_id.full_code',
        store=True,
        readonly=True,
    )
    line_points = fields.Float(
        string='Max Points',
        related='competency_line_id.points',
        store=True,
        readonly=True,
    )
    line_sequence = fields.Integer(
        string='Line Sequence',
        related='competency_line_id.sequence',
        store=True,
        readonly=True,
    )
    
    # score fields
    self_score = fields.Float(string='Employee Score', default=0.0)
    self_remarks = fields.Text(string='Employee Remarks')

    supervisor_score = fields.Float(string='Supervisor Score', default=0.0)
    supervisor_remarks = fields.Text(string='Supervisor Remarks')

    secondary_supervisor_score = fields.Float(string='2nd Supervisor Score', default=0.0)
    secondary_supervisor_remarks = fields.Text(string='2nd Supervisor Remarks')

    reviewer_score = fields.Float(string='Reviewer Score', default=0.0)
    reviewer_remarks = fields.Text(string='Reviewer Remarks')


    _unique_appraisal_line = models.Constraint(
        'UNIQUE(appraisal_id, competency_line_id)',
        'Duplicate competency score entry for the same appraisal and line.',
    )

    def _raise_score_error(self, score, label):
        competency = self.line_name or _('this competency')
        max_pts    = self.line_points or 0.0

        if float_compare(score, 0.0, precision_digits=2) < 0:
            raise UserError(_(
                '%(label)s score cannot be negative for competency "%(name)s".'
            ) % {'label': label, 'name': competency})

        if float_compare(score, max_pts, precision_digits=2) > 0:
            raise UserError(_(
                '%(label)s score (%(score).2f) cannot exceed the maximum '
                'points (%(max).2f) for competency "%(name)s".'
            ) % {
                'label': label,
                'score': score,
                'max':   max_pts,
                'name':  competency,
            })

    @api.onchange('self_score')
    def _onchange_self_score(self):
        self._raise_score_error(self.self_score or 0.0, _('Employee'))

    @api.onchange('supervisor_score')
    def _onchange_supervisor_score(self):
        self._raise_score_error(self.supervisor_score or 0.0, _('Supervisor'))

    @api.onchange('secondary_supervisor_score')
    def _onchange_secondary_supervisor_score(self):
        self._raise_score_error(self.secondary_supervisor_score or 0.0, _('2nd Supervisor'))

    @api.onchange('reviewer_score')
    def _onchange_reviewer_score(self):
        self._raise_score_error(self.reviewer_score or 0.0, _('Reviewer'))

    # Score validation constraints 

    @api.constrains('self_score', 'line_points')
    def _check_self_score(self):
        for rec in self:
            if float_compare(rec.self_score, 0.0, precision_digits=2) < 0:
                raise ValidationError(_(
                    'Employee score cannot be negative for competency "%s".'
                ) % rec.line_name)
            if float_compare(rec.self_score, rec.line_points, precision_digits=2) > 0:
                raise ValidationError(_(
                    'Employee score (%(s).2f) cannot exceed max points (%(m).2f) '
                    'for competency "%(n)s".'
                ) % {'s': rec.self_score, 'm': rec.line_points, 'n': rec.line_name})

    @api.constrains('supervisor_score', 'line_points')
    def _check_supervisor_score(self):
        for rec in self:
            if float_compare(rec.supervisor_score, 0.0, precision_digits=2) < 0:
                raise ValidationError(_(
                    'Supervisor score cannot be negative for competency "%s".'
                ) % rec.line_name)
            if float_compare(rec.supervisor_score, rec.line_points, precision_digits=2) > 0:
                raise ValidationError(_(
                    'Supervisor score (%(s).2f) cannot exceed max points (%(m).2f) '
                    'for competency "%(n)s".'
                ) % {'s': rec.supervisor_score, 'm': rec.line_points, 'n': rec.line_name})

    @api.constrains('secondary_supervisor_score', 'line_points')
    def _check_secondary_supervisor_score(self):
        for rec in self:
            if float_compare(rec.secondary_supervisor_score, 0.0, precision_digits=2) < 0:
                raise ValidationError(_(
                    '2nd Supervisor score cannot be negative for competency "%s".'
                ) % rec.line_name)
            if float_compare(rec.secondary_supervisor_score, rec.line_points, precision_digits=2) > 0:
                raise ValidationError(_(
                    '2nd Supervisor score (%(s).2f) cannot exceed max points (%(m).2f) '
                    'for competency "%(n)s".'
                ) % {'s': rec.secondary_supervisor_score, 'm': rec.line_points, 'n': rec.line_name})

    @api.constrains('reviewer_score', 'line_points')
    def _check_reviewer_score(self):
        for rec in self:
            if float_compare(rec.reviewer_score, 0.0, precision_digits=2) < 0:
                raise ValidationError(_(
                    'Reviewer score cannot be negative for competency "%s".'
                ) % rec.line_name)
            if float_compare(rec.reviewer_score, rec.line_points, precision_digits=2) > 0:
                raise ValidationError(_(
                    'Reviewer score (%(s).2f) cannot exceed max points (%(m).2f) '
                    'for competency "%(n)s".'
                ) % {'s': rec.reviewer_score, 'm': rec.line_points, 'n': rec.line_name})