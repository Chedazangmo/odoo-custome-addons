# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FeedbackQuestion(models.Model):
    _name = 'pms.feedback.question'
    _description = '360 Feedback Question'
    _order = 'sequence asc, id asc'

    template_id = fields.Many2one(
        'pms.feedback.template',
        string='Template',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(
        string='Order',
        default=10,
        help='Drag and drop to reorder questions'
    )
    question_text = fields.Text(
        string='Question',
        required=True,
        help='The feedback question to be answered'
    )
    question_type = fields.Selection([
        ('radio', 'Single Choice (Radio Buttons)'),
        ('checkbox', 'Multiple Choice (Checkboxes)'),
        ('text', 'Open Text'),
        ('rating', 'Rating Scale (1-5)'),
    ], string='Answer Type', required=True, default='radio')

    is_required = fields.Boolean(
        string='Required',
        default=True
    )
    answer_option_ids = fields.One2many(
        'pms.feedback.answer.option',
        'question_id',
        string='Answer Options'
    )
    hint_text = fields.Char(
        string='Hint / Placeholder',
        help='Optional hint shown to the respondent'
    )
    section_header = fields.Char(
        string='Section Header',
        help='Optional section grouping for this question'
    )

    @api.constrains('question_type', 'answer_option_ids')
    def _check_answer_options(self):
        for q in self:
            if q.question_type in ('radio', 'checkbox') and not q.answer_option_ids:
                raise ValidationError(_(
                    'Question "%s" requires at least one answer option for radio/checkbox type.'
                ) % q.question_text)
