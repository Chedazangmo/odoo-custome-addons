# from odoo import http


# class HrEmployeeEvaluation(http.Controller):
#     @http.route('/hr_employee_evaluation/hr_employee_evaluation', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hr_employee_evaluation/hr_employee_evaluation/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('hr_employee_evaluation.listing', {
#             'root': '/hr_employee_evaluation/hr_employee_evaluation',
#             'objects': http.request.env['hr_employee_evaluation.hr_employee_evaluation'].search([]),
#         })

#     @http.route('/hr_employee_evaluation/hr_employee_evaluation/objects/<model("hr_employee_evaluation.hr_employee_evaluation"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hr_employee_evaluation.object', {
#             'object': obj
#         })

