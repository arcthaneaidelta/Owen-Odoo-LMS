from odoo import http
from odoo.http import request

class ExaminationController(http.Controller):
    
    @http.route('/examination/grade_entry', type='http', auth='public', website=True)
    def grade_entry_portal(self, token=None, **kw):
        # Implementation for OTP secured link
        return request.render('university_examination.grade_entry_template', {})
