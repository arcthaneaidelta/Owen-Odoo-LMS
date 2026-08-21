# -*- coding: utf-8 -*-
from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import ValidationError

class FreezePortal(http.Controller):

    # -------------------------------------------------------------
    # FREEZE
    # -------------------------------------------------------------
    @http.route(['/my/student/freeze'], type='http', auth="user", website=True)
    def portal_my_freeze(self, **kw):
        partner = request.env.user.partner_id
        student = request.env['university.student'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        if not student:
            return request.redirect('/my')

        # Check existing active/pending requests
        existing_request = request.env['university.student.freeze.request'].sudo().search([
            ('student_id', '=', student.id),
            ('state', 'not in', ['completed', 'rejected'])
        ], limit=1)

        values = {
            'student': student,
            'existing_request': existing_request,
            'page_name': 'freeze_request',
        }
        return request.render("university_student.portal_my_freeze_request", values)

    @http.route(['/my/student/freeze/submit'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_freeze_submit(self, **post):
        partner = request.env.user.partner_id
        student = request.env['university.student'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        if not student:
            return request.redirect('/my')

        current_year_name = student.current_academic_year_name
        if not current_year_name:
            current_year = request.env['university.academic_year'].sudo().search([('state', '=', 'active')], limit=1)
            if not current_year:
                return request.render('university_student.freeze_request_form_template', {
                    'student': student, 'error': 'No active academic year found.'
                })
            current_year_name = current_year.name

        level = student.current_level
        reason = post.get('reason')
        reason_details = post.get('reason_details')

        freeze_req = request.env['university.student.freeze.request'].sudo().create({
            'student_id': student.id,
            'academic_year_name': current_year_name,
            'level_to_freeze': level,
            'reason': reason,
            'reason_details': reason_details,
        })
        
        # Automatically generate and send OTP
        try:
            freeze_req.action_send_otp()
        except ValidationError as e:
            return request.redirect('/my/student/freeze?error=' + str(e))

        return request.redirect('/my/student/freeze/otp?req_id=%s' % freeze_req.id)

    @http.route(['/my/student/freeze/otp'], type='http', auth="user", website=True)
    def portal_my_freeze_otp(self, req_id=None, **kw):
        if not req_id:
            return request.redirect('/my/student/freeze')
        
        freeze_req = request.env['university.student.freeze.request'].sudo().browse(int(req_id))
        
        values = {
            'freeze_req': freeze_req,
            'page_name': 'freeze_request',
        }
        return request.render("university_student.portal_my_freeze_otp", values)

    @http.route(['/my/student/freeze/otp_verify'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_freeze_otp_verify(self, **post):
        req_id = post.get('req_id')
        otp_code = post.get('otp_code')
        
        freeze_req = request.env['university.student.freeze.request'].sudo().browse(int(req_id))
        
        try:
            freeze_req.action_verify_otp(otp_code)
            return request.redirect('/my/student/freeze?success=Freeze request submitted successfully.')
        except ValidationError as e:
            return request.redirect('/my/student/freeze/otp?req_id=%s&error=%s' % (req_id, str(e)))

    # -------------------------------------------------------------
    # UNFREEZE
    # -------------------------------------------------------------
    @http.route(['/my/student/unfreeze'], type='http', auth="user", website=True)
    def portal_my_unfreeze(self, **kw):
        partner = request.env.user.partner_id
        student = request.env['university.student'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        if not student:
            return request.redirect('/my')

        # Find active freeze request
        active_freeze = request.env['university.student.freeze.request'].sudo().search([
            ('student_id', '=', student.id),
            ('state', '=', 'active')
        ], limit=1)

        # Check existing pending unfreeze
        existing_unfreeze = request.env['university.student.unfreeze.request'].sudo().search([
            ('student_id', '=', student.id),
            ('state', 'not in', ['completed', 'rejected'])
        ], limit=1)

        values = {
            'student': student,
            'active_freeze': active_freeze,
            'existing_unfreeze': existing_unfreeze,
            'page_name': 'unfreeze_request',
        }
        return request.render("university_student.portal_my_unfreeze_request", values)

    @http.route(['/my/student/unfreeze/submit'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_unfreeze_submit(self, **post):
        partner = request.env.user.partner_id
        student = request.env['university.student'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        if not student:
            return request.redirect('/my')

        freeze_id = post.get('freeze_id')
        reason_details = post.get('reason_details')

        active_freeze = request.env['university.student.freeze.request'].sudo().browse(int(freeze_id))
        
        # Find the appropriate batch for their level
        new_batch = request.env['university.batch'].sudo().search([
            ('program_id', '=', student.program_id.id),
            ('current_level', '=', active_freeze.level_to_freeze),
            ('state', '=', 'active')
        ], limit=1)
        
        current_year_name = new_batch.current_academic_year_name if new_batch else student.current_academic_year_name
        if not current_year_name:
            current_year = request.env['university.academic_year'].sudo().search([('state', '=', 'active')], limit=1)
            if not current_year:
                return request.render('university_student.unfreeze_request_form_template', {
                    'student': student, 'freeze_id': freeze_id, 'error': 'No active academic year found.'
                })
            current_year_name = current_year.name

        # Pre-check eligibility before creating record
        if active_freeze.activation_date:
            from dateutil.relativedelta import relativedelta
            one_year_later = active_freeze.activation_date + relativedelta(years=1)
            if fields.Date.today() < one_year_later:
                error_msg = _(
                    "A freeze request must remain active for at least one year. "
                    "This request was activated on %s. You can only unfreeze after %s."
                ) % (active_freeze.activation_date, one_year_later)
                return request.redirect('/my/student/unfreeze?error=' + error_msg)

        try:
            unfreeze_req = request.env['university.student.unfreeze.request'].sudo().create({
                'student_id': student.id,
                'freeze_request_id': int(freeze_id),
                'academic_year_name': current_year_name,
                'reason_details': reason_details,
            })
        except ValidationError as e:
            return request.redirect('/my/student/unfreeze?error=' + str(e))
        
        try:
            unfreeze_req.action_send_otp()
        except ValidationError as e:
            return request.redirect('/my/student/unfreeze?error=' + str(e))

        return request.redirect('/my/student/unfreeze/otp?req_id=%s' % unfreeze_req.id)

    @http.route(['/my/student/unfreeze/otp'], type='http', auth="user", website=True)
    def portal_my_unfreeze_otp(self, req_id=None, **kw):
        if not req_id:
            return request.redirect('/my/student/unfreeze')
        
        unfreeze_req = request.env['university.student.unfreeze.request'].sudo().browse(int(req_id))
        
        values = {
            'unfreeze_req': unfreeze_req,
            'page_name': 'unfreeze_request',
        }
        return request.render("university_student.portal_my_unfreeze_otp", values)

    @http.route(['/my/student/unfreeze/otp_verify'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_unfreeze_otp_verify(self, **post):
        req_id = post.get('req_id')
        otp_code = post.get('otp_code')
        
        unfreeze_req = request.env['university.student.unfreeze.request'].sudo().browse(int(req_id))
        
        try:
            unfreeze_req.action_verify_otp(otp_code)
            return request.redirect('/my/student/unfreeze?success=Unfreeze request submitted successfully.')
        except ValidationError as e:
            return request.redirect('/my/student/unfreeze/otp?req_id=%s&error=%s' % (req_id, str(e)))
