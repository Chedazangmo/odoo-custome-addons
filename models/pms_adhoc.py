# ============================================================
# models/pms_adhoc_activity.py
#
# Extra-mile / adhoc activity entries attached to a pms.appraisal.
# Rows are created by the employee during appraisal_draft state.
# No scoring system — purely documentary.
# ============================================================

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PmsAdhocActivity(models.Model):
    _name        = 'pms.adhoc.activity'
    _description = 'Adhoc / Extra-Mile Activity'
    _order       = 'completed_date desc, id desc'

    appraisal_id = fields.Many2one(
        'pms.appraisal',
        string='Appraisal',
        required=True,
        ondelete='cascade',
        index=True,
    )

    title = fields.Char(
        string='Activity Title',
        required=True,
        help='What did you do?',
    )

    description = fields.Text(
        string='Description / Impact',
        required=True,
        help='Details and impact of the activity',
    )

    completed_date = fields.Date(
        string='Completed Date',
        required=True,
        help='When was it done?',
    )

    category = fields.Char(
        string='Category',
        help='e.g. Project, Support, Innovation',
    )

    evidence_attachment_ids = fields.Many2many(
        'ir.attachment',
        'pms_adhoc_attachment_rel',
        'adhoc_id',
        'attachment_id',
        string='Evidence Attachments',
    )

    @api.constrains('completed_date')
    def _check_completed_date(self):
        for rec in self:
            if rec.completed_date and rec.appraisal_id.cycle_id:
                cycle = rec.appraisal_id.cycle_id
                if cycle.start_date and rec.completed_date < cycle.start_date:
                    raise ValidationError(_(
                        'Completed date cannot be before the cycle start date (%s).'
                    ) % cycle.start_date)