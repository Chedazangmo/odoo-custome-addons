# from odoo import http


# class CollegeErp(http.Controller):
#     @http.route('/college_erp/college_erp', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/college_erp/college_erp/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('college_erp.listing', {
#             'root': '/college_erp/college_erp',
#             'objects': http.request.env['college_erp.college_erp'].search([]),
#         })

#     @http.route('/college_erp/college_erp/objects/<model("college_erp.college_erp"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('college_erp.object', {
#             'object': obj
#         })

