from odoo import models, fields, api


class PMSCycleIntegration(models.Model):
    """Extend pms.cycle to add 360° feedback fields and auto-session creation."""
    _inherit = 'pms.cycle'

    feedback_template_id = fields.Many2one(
        'pms.feedback.template',
        string='360° Feedback Template',
        domain=[('state', '=', 'published')],
        help='Select a published 360° feedback template. A feedback session will be '
             'automatically created when the cycle moves to Appraisal phase.',
        ondelete='set null',
    )

    feedback_session_id = fields.Many2one(
        'pms.feedback.session',
        string='360° Feedback Session',
        readonly=True,
        copy=False,
    )

    def action_move_to_appraisal(self):
        """Override to auto-create feedback session when moving to appraisal."""
        result = super().action_move_to_appraisal()
        if self.feedback_template_id and not self.feedback_session_id:
            self._create_feedback_session()
        return result

    def _create_feedback_session(self):
        """Auto-create a 360° feedback session when appraisal phase starts."""
        self.ensure_one()

        if self.apply_to == 'all':
            reviewees = self.env['hr.employee'].search([
                ('active', '=', True),
                ('evaluation_group_id', '!=', False)
            ])
        else:
            reviewees = self.employee_ids

        reviewer_ids = set()
        for emp in reviewees:
            if emp.parent_id:
                reviewer_ids.add(emp.parent_id.id)
            if emp.secondary_manager_id:
                reviewer_ids.add(emp.secondary_manager_id.id)
            if emp.reviewer_id:
                reviewer_ids.add(emp.reviewer_id.id)
            if emp.evaluation_group_id:
                group_members = self.env['hr.employee'].search([
                    ('evaluation_group_id', '=', emp.evaluation_group_id.id),
                    ('active', '=', True),
                    ('id', '!=', emp.id),
                ])
                reviewer_ids.update(group_members.ids)

        reviewers = self.env['hr.employee'].browse(list(reviewer_ids))

        session = self.env['pms.feedback.session'].create({
            'name': f'360° Feedback - {self.name}',
            'template_id': self.feedback_template_id.id,
            'date_start': fields.Date.today(),
            'date_end': self.end_date,
            'reviewee_ids': [(6, 0, reviewees.ids)],
            'reviewer_ids': [(6, 0, reviewers.ids)],
            'notes': f'Automatically created for Performance Cycle: {self.name}',
        })

        session.action_open()
        self.write({'feedback_session_id': session.id})
        self.message_post(
            body=f'360° Feedback session created and opened: <strong>{session.name}</strong>',
            message_type='notification'
        )

    def action_view_feedback_session(self):
        """Open the linked feedback session."""
        self.ensure_one()
        if not self.feedback_session_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': '360° Feedback Session',
            'res_model': 'pms.feedback.session',
            'res_id': self.feedback_session_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class FeedbackSessionCycleLink(models.Model):
    """Add cycle link to feedback session."""
    _inherit = 'pms.feedback.session'

    cycle_id = fields.Many2one(
        'pms.cycle',
        string='Performance Cycle',
        readonly=True,
        copy=False,
        ondelete='set null',
    )


class PMSAppraisalFeedbackCount(models.Model):
    """Add 360 feedback count to appraisal."""
    _inherit = 'pms.appraisal'

    feedback_response_count = fields.Integer(
        string='360° Feedback',
        compute='_compute_feedback_response_count',
    )

    def _compute_feedback_response_count(self):
        for rec in self:
            if rec.cycle_id and rec.cycle_id.feedback_session_id:
                count = self.env['pms.feedback.response'].search_count([
                    ('session_id', '=', rec.cycle_id.feedback_session_id.id),
                    ('reviewee_employee_id', '=', rec.employee_id.id),
                    ('state', '=', 'submitted'),
                ])
                rec.feedback_response_count = count
            else:
                rec.feedback_response_count = 0