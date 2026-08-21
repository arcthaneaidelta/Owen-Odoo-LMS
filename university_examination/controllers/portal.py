# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

class AbsenceRequestPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        student = request.env['university.student'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        if student:
            count = request.env['examination.absence.request'].sudo().search_count([('student_id', '=', student.id)])
            values['absence_request_count'] = count
        return values

    @http.route(['/my/absence_requests'], type='http', auth="user", website=True)
    def portal_my_absence_requests(self, **kw):
        partner = request.env.user.partner_id
        student = request.env['university.student'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        if not student:
            student = request.env['university.student'].sudo().with_context(active_test=False).search([('partner_id', '=', partner.id)], limit=1)
            
        if not student:
            return request.redirect('/my')
            
        requests = request.env['examination.absence.request'].sudo().search([
            ('student_id', '=', student.id)
        ])
        
        cycles = request.env['examination.cycle'].sudo().search([
            ('batch_id', '=', student.batch_id.id),
            ('state', '=', 'active')
        ])
        
        # Get active curriculum subjects
        subjects = []
        if student.batch_id and student.batch_id.curriculum_id:
            curr = student.batch_id.curriculum_id
            if curr.state != 'active' and curr.parent_id:
                curr = curr.parent_id
            subjects = curr.line_ids.mapped('subject_id')
        
        values = self._prepare_portal_layout_values()
        values.update({
            'student': student,
            'absence_requests': requests,
            'cycles': cycles,
            'subjects': subjects,
            'page_name': 'absence_requests',
        })
        return request.render("university_examination.portal_my_absence_requests", values)

    @http.route(['/my/absence_requests/submit'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def absence_request_submit(self, **post):
        partner = request.env.user.partner_id
        student = request.env['university.student'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        if not student:
            student = request.env['university.student'].sudo().with_context(active_test=False).search([('partner_id', '=', partner.id)], limit=1)
            
        if not student:
            return request.redirect('/my/absence_requests')

        cycle_id = int(post.get('cycle_id')) if post.get('cycle_id') else False
        subject_id = int(post.get('subject_id')) if post.get('subject_id') else False
        reason = post.get('reason', '')

        if cycle_id and subject_id and reason:
            request.env['examination.absence.request'].sudo().create({
                'student_id': student.id,
                'cycle_id': cycle_id,
                'subject_id': subject_id,
                'reason': reason,
                'state': 'submitted'
            })
        
        return request.redirect('/my/absence_requests')
