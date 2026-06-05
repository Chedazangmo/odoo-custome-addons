from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    ndi_cid = fields.Char(
        string='NDI CID',
        help='Bhutan National Digital Identity — Citizen ID Number (verified).',
        copy=False,
        index=True,
    )
    ndi_verified = fields.Boolean(
        string='NDI Verified',
        default=False,
        help='True when this user has logged in at least once via NDI QR scan.',
        copy=False,
    )
    ndi_last_login = fields.Datetime(
        string='Last NDI Login',
        help='Timestamp of the most recent successful NDI authentication.',
        copy=False,
    )