from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FeedbackTemplate(models.Model):
    _name = 'pms.feedback.template'
    _description = '360 Feedback Question Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Template Name', required=True, tracking=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ], string='Status', default='draft', tracking=True)

    question_ids = fields.One2many('pms.feedback.question', 'template_id', string='Questions')
    question_count = fields.Integer(string='Question Count', compute='_compute_question_count')
    session_count = fields.Integer(string='Sessions', compute='_compute_session_count')
    created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user, readonly=True)

    @api.depends('question_ids')
    def _compute_question_count(self):
        for rec in self:
            rec.question_count = len(rec.question_ids)

    def _compute_session_count(self):
        Session = self.env['pms.feedback.session']
        for rec in self:
            rec.session_count = Session.search_count([('template_id', '=', rec.id)])

    def action_publish(self):
        for rec in self:
            if not rec.question_ids:
                raise ValidationError(_('Please add at least one question before publishing.'))
            rec.state = 'published'

    def action_draft(self):
        self.state = 'draft'

    def action_archive_template(self):
        self.state = 'archived'
        self.active = False

    def action_view_sessions(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Feedback Sessions'),
            'res_model': 'pms.feedback.session',
            'view_mode': 'list,form',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id},
        }


class FeedbackQuestion(models.Model):
    _name = 'pms.feedback.question'
    _description = '360 Feedback Question'
    _order = 'sequence, id'

    template_id = fields.Many2one('pms.feedback.template', string='Template', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    question_text = fields.Text(string='Question', required=True)
    question_type = fields.Selection([
        ('radio', 'Single Choice (Radio Button)'),
        ('checkbox', 'Multiple Choice (Checkboxes)'),
        ('text', 'Open Text'),
    ], string='Answer Type', required=True, default='radio')
    is_required = fields.Boolean(string='Required', default=True)
    option_ids = fields.One2many('pms.feedback.question.option', 'question_id', string='Answer Options')
    option_count = fields.Integer(
        string='Options',
        compute='_compute_option_count',
        store=True,
    )

    @api.depends('option_ids')
    def _compute_option_count(self):
        for rec in self:
            rec.option_count = len(rec.option_ids)




class FeedbackQuestionOption(models.Model):
    _name = 'pms.feedback.question.option'
    _description = '360 Feedback Question Option'
    _rec_name = 'option_text'
    _order = 'sequence, id'

    question_id = fields.Many2one('pms.feedback.question', string='Question', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    option_text = fields.Char(string='Option', required=True)
    value = fields.Char(string='Value', help='Internal value for scoring (optional)')