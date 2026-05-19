# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

class ResignationPortal(CustomerPortal):

    @http.route(['/my/resignation'], type='http', auth="user", website=True)
    def resignation_portal(self, **kw):
        partner = request.env.user.partner_id
        # Prioritize active student records
        student = request.env['university.student'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        if not student:
            # Fallback to archived only if no active one found
            student = request.env['university.student'].sudo().with_context(active_test=False).search([('partner_id', '=', partner.id)], limit=1)
            
        if not student:
            return request.redirect('/my')
            
        resignation = request.env['university.student.resignation'].sudo().search([
            ('student_id', '=', student.id),
            ('state', 'not in', ['rejected', 'cancelled'])
        ], limit=1)
        
        values = self._prepare_portal_layout_values()
        values.update({
            'student': student,
            'resignation': resignation,
            'page_name': 'resignation',
        })
        return request.render("university_registrar.portal_my_resignation", values)

    @http.route(['/my/resignation/submit'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def resignation_submit(self, **post):
        partner = request.env.user.partner_id
        # Prioritize active student records
        student = request.env['university.student'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        if not student:
            # Fallback to archived only if no active one found
            student = request.env['university.student'].sudo().with_context(active_test=False).search([('partner_id', '=', partner.id)], limit=1)
            
        if not student:
            return request.redirect('/my/resignation')

        # Create resignation in draft
        resignation = request.env['university.student.resignation'].sudo().create({
            'student_id': student.id,
            'reason': post.get('reason', 'Student-initiated resignation'),
        })
        
        # Immediately send OTP
        resignation.action_send_otp()
        
        return request.redirect('/my/resignation')

    @http.route(['/my/resignation/verify'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def resignation_verify(self, **post):
        res_id = post.get('resignation_id')
        otp_code = post.get('otp_code')
        
        resignation = request.env['university.student.resignation'].sudo().browse(int(res_id))
        if resignation and resignation.student_id.partner_id == request.env.user.partner_id:
            try:
                resignation.action_verify_otp(otp_code)
            except Exception as e:
                return request.redirect('/my/resignation?error=%s' % str(e))
                
        return request.redirect('/my/resignation')
