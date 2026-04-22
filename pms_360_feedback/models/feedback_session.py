from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class FeedbackSession(models.Model):
    _name = 'pms.feedback.session'
    _description = '360 Feedback Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc'

    name = fields.Char(string='Session Name', required=True, tracking=True)
    reference = fields.Char(string='Reference', readonly=True, default='New')
    template_id = fields.Many2one(
        'pms.feedback.template', string='Feedback Template',
        required=True, tracking=True,
        domain=[('state', '=', 'published')],
    )
    date_start = fields.Date(string='Start Date', required=True, tracking=True)
    date_end = fields.Date(string='End Date', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    reviewee_ids = fields.Many2many(
        'hr.employee', 'pms_session_reviewee_rel',
        'session_id', 'employee_id',
        string='Employees Being Reviewed',
        help='Employees who will receive feedback in this session.',
    )
    reviewer_ids = fields.Many2many(
        'hr.employee',
        'feedback_session_reviewer_rel',
        'session_id',
        'employee_id',
        string='Allowed Reviewers',
        help='Leave empty to allow all employees to give feedback'
    )
    response_ids = fields.One2many('pms.feedback.response', 'session_id', string='Responses')
    response_count = fields.Integer(string='Responses', compute='_compute_response_count')
    notes = fields.Text(string='Instructions / Notes')
    created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user, readonly=True)

    @api.depends('response_ids')
    def _compute_response_count(self):
        for rec in self:
            rec.response_count = len(rec.response_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('pms.feedback.session') or 'New'
        return super().create(vals_list)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_start > rec.date_end:
                raise ValidationError(_('End Date must be after Start Date.'))

    def action_open(self):
        for rec in self:
            if not rec.reviewee_ids:
                raise ValidationError(_('Please select at least one employee to be reviewed.'))
            rec.state = 'open'

    def action_close(self):
        self.state = 'closed'

    def action_cancel(self):
        self.state = 'cancelled'

    def action_draft(self):
        self.state = 'draft'

    def action_select_all_employees(self):
        all_employees = self.env['hr.employee'].search([('active', '=', True)])
        self.reviewee_ids = all_employees

    def action_clear_reviewees(self):
        self.reviewee_ids = [(5, 0, 0)]

    def action_view_responses(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Feedback Responses'),
            'res_model': 'pms.feedback.response',
            'view_mode': 'list,form',
            'domain': [('session_id', '=', self.id)],
            'context': {'default_session_id': self.id},
        }

    def action_give_feedback(self):
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_('This feedback session is not open.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Give Feedback'),
            'res_model': 'pms.feedback.response',
            'view_mode': 'form',
            'context': {
                'default_session_id': self.id,
                'default_reviewer_employee_id': self._get_current_employee().id,
            },
            'target': 'new',
        }

    def _get_current_employee(self):
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if not employee:
            raise UserError(_('No employee record linked to your user account.'))
        return employee