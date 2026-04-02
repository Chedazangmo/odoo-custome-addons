# -*- coding: utf-8 -*-
from odoo import models, fields, api


class FeedbackResponseLine(models.Model):
    _name = 'pms.feedback.response.line'
    _description = '360 Feedback Response Line (Answer)'
    _order = 'sequence asc, id asc'

    response_id = fields.Many2one(
        'pms.feedback.response',
        string='Response',
        required=True,
        ondelete='cascade'
    )
    question_id = fields.Many2one(
        'pms.feedback.question',
        string='Question',
        required=True,
        ondelete='restrict'
    )
    # Denormalized fields (snapshot at time of response creation)
    question_text = fields.Text(
        string='Question Text',
        readonly=True
    )
    question_type = fields.Selection([
        ('radio', 'Single Choice (Radio Buttons)'),
        ('checkbox', 'Multiple Choice (Checkboxes)'),
        ('text', 'Open Text'),
        ('rating', 'Rating Scale (1-5)'),
    ], string='Answer Type', readonly=True)
    sequence = fields.Integer(string='Order', default=10)
    section_header = fields.Char(string='Section', readonly=True)

    # Available options (auto-populated from question)
    available_option_ids = fields.Many2many(
        'pms.feedback.answer.option',
        'pms_response_line_available_options_rel',
        'line_id',
        'option_id',
        string='Available Options',
        compute='_compute_available_options',
        store=True
    )

    # Answer fields (only one is used depending on question_type)
    # Radio: single selection
    selected_option_id = fields.Many2one(
        'pms.feedback.answer.option',
        string='Selected Answer',
        domain="[('id', 'in', available_option_ids)]"
    )
    # Checkbox: multiple selection
    selected_option_ids = fields.Many2many(
        'pms.feedback.answer.option',
        'pms_response_line_selected_rel',
        'line_id',
        'option_id',
        string='Selected Answers',
        domain="[('id', 'in', available_option_ids)]"
    )
    # Text answer
    text_answer = fields.Text(string='Text Answer')
    # Rating (1-5)
    rating_value = fields.Selection([
        ('1', '1 - Poor'),
        ('2', '2 - Below Average'),
        ('3', '3 - Average'),
        ('4', '4 - Good'),
        ('5', '5 - Excellent'),
    ], string='Rating')

    # Computed score for reporting
    score_value = fields.Float(
        string='Score',
        compute='_compute_score_value',
        store=True
    )

    @api.depends('question_id')
    def _compute_available_options(self):
        for line in self:
            if line.question_id:
                line.available_option_ids = line.question_id.answer_option_ids
            else:
                line.available_option_ids = False

    @api.depends(
        'selected_option_id', 'selected_option_ids',
        'rating_value', 'question_type'
    )
    def _compute_score_value(self):
        for line in self:
            if line.question_type == 'radio' and line.selected_option_id:
                line.score_value = line.selected_option_id.score_value
            elif line.question_type == 'checkbox' and line.selected_option_ids:
                line.score_value = sum(line.selected_option_ids.mapped('score_value'))
            elif line.question_type == 'rating' and line.rating_value:
                line.score_value = float(line.rating_value)
            else:
                line.score_value = 0.0

    def get_answer_display(self):
        """Return a human-readable summary of the answer"""
        self.ensure_one()
        if self.question_type == 'radio':
            return self.selected_option_id.label if self.selected_option_id else '-'
        elif self.question_type == 'checkbox':
            return ', '.join(self.selected_option_ids.mapped('label')) or '-'
        elif self.question_type == 'text':
            return self.text_answer or '-'
        elif self.question_type == 'rating':
            return dict(self._fields['rating_value'].selection).get(self.rating_value, '-')
        return '-'
