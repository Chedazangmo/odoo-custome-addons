# -*- coding: utf-8 -*-
from odoo import models, fields


class FeedbackAnswerOption(models.Model):
    _name = 'pms.feedback.answer.option'
    _description = 'Answer Option for Feedback Question'
    _order = 'sequence asc, id asc'

    question_id = fields.Many2one(
        'pms.feedback.question',
        string='Question',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(string='Order', default=10)
    label = fields.Char(
        string='Answer Label',
        required=True,
        help='The text shown for this answer choice'
    )
    score_value = fields.Float(
        string='Score Value',
        default=0.0,
        help='Numeric value assigned to this answer for scoring purposes'
    )
    is_default = fields.Boolean(
        string='Default Selection',
        default=False
    )
