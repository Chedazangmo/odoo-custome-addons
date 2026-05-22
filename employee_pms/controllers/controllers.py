# from odoo import http


# class EmployeePms(http.Controller):
#     @http.route('/employee_pms/employee_pms', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/employee_pms/employee_pms/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('employee_pms.listing', {
#             'root': '/employee_pms/employee_pms',
#             'objects': http.request.env['employee_pms.employee_pms'].search([]),
#         })

#     @http.route('/employee_pms/employee_pms/objects/<model("employee_pms.employee_pms"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('employee_pms.object', {
#             'object': obj
#         })

