# from odoo import models, fields

# class PMSAppraisalSubmitWizard(models.TransientModel):
#     _name = 'pms.appraisal.submit.wizard'
#     _description = 'Confirm Submission'

#     message = fields.Html(string='Message', readonly=True)
#     # 1. HARD FIELDS to permanently store the routing data
#     appraisal_id = fields.Many2one('pms.appraisal', string='Appraisal')
#     submit_action = fields.Char(string='Action Name')

#     def action_confirm(self):
#         # 2. Read directly from the database record, NO context to get lost
#         if self.appraisal_id and self.submit_action:
#             getattr(self.appraisal_id.with_context(confirm_submit=True), self.submit_action)()
            
#         # 3. Force Odoo to completely reload the page so the state change is instantly visible
#         return {'type': 'ir.actions.client', 'tag': 'reload'}