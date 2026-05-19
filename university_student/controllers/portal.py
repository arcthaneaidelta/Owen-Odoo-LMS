# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import base64

class StudentPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        # We MUST call super() so we get the standard counter variables, 
        # BUT because we hid the document count templates in the XML view, 
        # the JS will fail if we pass the count values without the dom node.
        # So we just get the super values and then "0" out the counts
        # for modules we hid, to prevent the JS error "Cannot set properties of null"
        values = super()._prepare_home_portal_values(counters)
        
        partner = request.env.user.partner_id
        Student = request.env['university.student']
        student_count = Student.sudo().search_count([('partner_id', '=', partner.id)])
        
        if student_count:
            values['student_profile_count'] = student_count
            
        # Prevent JS null errors by popping/zeroing hidden counters
        if 'quotation_count' in values:
            values['quotation_count'] = 0
        if 'order_count' in values:
            values['order_count'] = 0
        if 'invoice_count' in values:
            values['invoice_count'] = 0
        if 'bill_count' in values:
            values['bill_count'] = 0

        return values

    @http.route(['/my/student_profile'], type='http', auth="user", website=True)
    def portal_my_student_profile(self, **kw):
        partner = request.env.user.partner_id
        student = request.env['university.student'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        
        if not student:
            return request.redirect('/my')

        # Use _prepare_portal_layout_values from CustomerPortal, this is REQUIRED
        # for the standard Odoo portal layout to render correctly
        values = self._prepare_portal_layout_values()
        values.update({
            'student': student,
            'page_name': 'student_profile',
        })
        
        return request.render("university_student.portal_my_student_profile", values)

    @http.route(['/my/student_profile/update'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_student_profile_update(self, **post):
        partner = request.env.user.partner_id
        student = request.env['university.student'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        
        if not student:
            return request.redirect('/my')

        # Allowed fields to update
        update_vals = {}
        
        if 'phone' in post:
            update_vals['phone'] = post.get('phone')
        if 'phone_whatsapp' in post:
            update_vals['phone_whatsapp'] = post.get('phone_whatsapp')
        
        # Updating Name directly on student (which may trigger _compute_display_name_ar on backend, but let's just let user input English Name as mostly AR name comes from admission)
        if 'name_en' in post:
            update_vals['name_en'] = post.get('name_en')

        # Documents processing
        # request.httprequest.files returns a MultiDict
        if 'photo' in request.httprequest.files and request.httprequest.files.get('photo'):
            photo_file = request.httprequest.files.get('photo')
            if photo_file.filename:
                update_vals['photo'] = base64.b64encode(photo_file.read())
                update_vals['photo_filename'] = photo_file.filename
                
        if 'national_id_scan' in request.httprequest.files and request.httprequest.files.get('national_id_scan'):
            nid_file = request.httprequest.files.get('national_id_scan')
            if nid_file.filename:
                update_vals['national_id_scan'] = base64.b64encode(nid_file.read())

        if update_vals:
            student.write(update_vals)
            # Update partner as well for standard Odoo sync
            if 'phone' in update_vals:
                partner.sudo().write({'phone': update_vals['phone']})
            if 'name_en' in update_vals:
                # Decide if we overwrite partner name. Usually it's arabic display name
                pass
                
        return request.redirect('/my/student_profile?updated=1')
