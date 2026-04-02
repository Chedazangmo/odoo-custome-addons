from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FeedbackResponse(models.Model):
    _name = 'pms.feedback.response'
    _description = 'Feedback Response'
    _order = 'create_date desc'

    name = fields.Char(string='Reference', compute='_compute_display_name_computed', store=True)
    display_name_computed = fields.Char(
        string='Display Name',
        compute='_compute_display_name_computed',
        store=True
    )
    session_id = fields.Many2one('pms.feedback.session', string='Session',
                                  required=True, ondelete='cascade')
    template_id = fields.Many2one(related='session_id.template_id', string='Template',
                                   store=True, readonly=True)
    reviewee_employee_id = fields.Many2one('hr.employee', string='Employee Being Reviewed',
                                            required=True)
    reviewer_employee_id = fields.Many2one('hr.employee', string='Reviewer (You)',
                                            required=True)
    reviewer_display = fields.Char(
        string='Reviewer',
        compute='_compute_reviewer_display'
    )
    allowed_reviewee_ids = fields.Many2many(
        'hr.employee',
        compute='_compute_allowed_reviewees',
        string='Allowed Reviewees'
    )
    is_anonymous = fields.Boolean(string='Submit Anonymously', default=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
    ], string='Status', default='draft')
    submitted_date = fields.Datetime(string='Submitted On', readonly=True)
    answer_ids = fields.One2many('pms.feedback.answer', 'response_id', string='Answers')

    @api.depends('session_id', 'reviewee_employee_id', 'reviewer_employee_id', 'is_anonymous')
    def _compute_display_name_computed(self):
        for rec in self:
            session = rec.session_id.name or ''
            reviewee = rec.reviewee_employee_id.name or ''
            if rec.is_anonymous:
                rec.display_name_computed = f'{session} | Anonymous → {reviewee}'
            else:
                reviewer = rec.reviewer_employee_id.name or ''
                rec.display_name_computed = f'{session} | {reviewer} → {reviewee}'
            rec.name = rec.display_name_computed

    @api.depends('reviewer_employee_id', 'is_anonymous')
    def _compute_reviewer_display(self):
        for rec in self:
            if rec.is_anonymous:
                rec.reviewer_display = 'Anonymous'
            else:
                rec.reviewer_display = rec.reviewer_employee_id.name or ''

    @api.depends('session_id')
    def _compute_allowed_reviewees(self):
        for rec in self:
            if rec.session_id:
                rec.allowed_reviewee_ids = rec.session_id.reviewee_ids
            else:
                rec.allowed_reviewee_ids = self.env['hr.employee']

    @api.onchange('session_id')
    def _onchange_session_id(self):
        if self.session_id and self.session_id.template_id:
            self.answer_ids = [(5, 0, 0)]
            answer_lines = []
            for question in self.session_id.template_id.question_ids:
                answer_lines.append((0, 0, {
                    'question_id': question.id,
                }))
            self.answer_ids = answer_lines

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if record.session_id and record.session_id.template_id and not record.answer_ids:
            for question in record.session_id.template_id.question_ids:
                self.env['pms.feedback.answer'].create({
                    'response_id': record.id,
                    'question_id': question.id,
                })
        return record

    @api.model
    def get_my_employee_id(self):
        employee = self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1
        )
        if employee:
            return {'id': employee.id, 'name': employee.name}
        return {}

    def action_submit(self):
        for rec in self:
            required = rec.answer_ids.filtered(lambda a: a.is_required)
            unanswered = []
            for ans in required:
                if ans.question_type == 'radio' and not ans.radio_answer_id:
                    unanswered.append(ans.question_text)
                elif ans.question_type == 'checkbox' and not ans.checkbox_answer_ids:
                    unanswered.append(ans.question_text)
                elif ans.question_type == 'text' and not ans.text_answer:
                    unanswered.append(ans.question_text)
            if unanswered:
                raise ValidationError(
                    f"Please answer all required questions:\n" +
                    "\n".join(f"• {q}" for q in unanswered)
                )
            rec.state = 'submitted'
            rec.submitted_date = fields.Datetime.now()

    def action_edit(self):
        for rec in self:
            if rec.session_id.state == 'closed':
                raise ValidationError("Cannot edit feedback for a closed session.")
            rec.state = 'draft'


class FeedbackAnswer(models.Model):
    _name = 'pms.feedback.answer'
    _description = 'Feedback Answer'

    response_id = fields.Many2one('pms.feedback.response', string='Response',
                                   required=True, ondelete='cascade')
    question_id = fields.Many2one('pms.feedback.question', string='Question',
                                   required=True)
    question_text = fields.Text(related='question_id.question_text',
                                string='Question', readonly=True)
    question_type = fields.Selection(related='question_id.question_type',
                                     string='Type', readonly=True)
    is_required = fields.Boolean(related='question_id.is_required',
                                 string='Required', readonly=True)
    radio_answer_id = fields.Many2one('pms.feedback.question.option',
                                      string='Selected Option',
                                      domain="[('question_id', '=', question_id)]")
    checkbox_answer_ids = fields.Many2many(
        'pms.feedback.question.option',
        'feedback_answer_checkbox_rel',
        'answer_id',
        'option_id',
        string='Selected Options',
        domain="[('question_id', '=', question_id)]"
    )
    text_answer = fields.Text(string='Text Answer')
    answer_display = fields.Char(string='Your Answer', compute='_compute_answer_display')

    @api.depends('question_type', 'radio_answer_id', 'checkbox_answer_ids', 'text_answer')
    def _compute_answer_display(self):
        for rec in self:
            if rec.question_type == 'radio':
                rec.answer_display = rec.radio_answer_id.option_text if rec.radio_answer_id else ''
            elif rec.question_type == 'checkbox':
                rec.answer_display = ', '.join(
                    rec.checkbox_answer_ids.mapped('option_text')
                ) if rec.checkbox_answer_ids else ''
            elif rec.question_type == 'text':
                rec.answer_display = rec.text_answer or ''
            else:
                rec.answer_display = ''