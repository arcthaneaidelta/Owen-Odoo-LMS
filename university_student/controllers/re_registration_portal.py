# -*- coding: utf-8 -*-
"""
Portal controller for the annual re-registration flow.

Routes
------
GET  /my/student/re-register
    → Redirects to the token-based form URL for the student's active re-registration.
      If the student has no pending re-registration, shows an info page.

GET  /re-register/form/<token>?step=N
    → Shows step N of the multi-step re-registration form.
      Validates: token exists, token not expired, state is draft/submitted.

POST /re-register/form/<token>/save
    → Saves step data to student.re_registration_draft_data JSON.
    → On final step, applies data to the student record.
"""
import base64
import json

from odoo import http, _
from odoo.http import request


TOTAL_STEPS = 4  # Personal | Guardians (RO) | Documents | Medical


class ReRegistrationPortal(http.Controller):

    # ──────────────────────────────────────────────────────────────────────────
    # HELPER: resolve token
    # ──────────────────────────────────────────────────────────────────────────

    def _get_student_by_token(self, token):
        """Return (student_record, error_key) where error_key is None on success."""
        Student = request.env['university.student'].sudo()
        student = Student.search([('re_registration_token', '=', token)], limit=1)
        if not student:
            return None, 'not_found'
        
        # If already registered, form is considered expired/completed
        if student.registration_status == 'registered':
            return student, 'expired'
            
        # Check explicit token expiry
        if student.re_registration_token_expiry:
            from odoo import fields
            if fields.Date.today() > student.re_registration_token_expiry:
                return student, 'expired'
                
        return student, None

    # ──────────────────────────────────────────────────────────────────────────
    # Portal Home redirect (for the nav tab link)
    # ──────────────────────────────────────────────────────────────────────────

    @http.route('/my/student/re-register', type='http', auth='user', website=True)
    def portal_my_re_register_redirect(self, **kw):
        """Find the student's active re-registration and redirect to the token URL."""
        partner = request.env.user.partner_id
        student = request.env['university.student'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        if not student:
            return request.redirect('/my')

        if not student.re_registration_token or student.registration_status == 'registered':
            return request.render(
                'university_student.re_registration_no_pending',
                {'student': student, 'page_name': 're_registration'}
            )

        return request.redirect(f'/re-register/form/{student.re_registration_token}?step=1')

    # ──────────────────────────────────────────────────────────────────────────
    # MAIN FORM — GET (show current step)
    # ──────────────────────────────────────────────────────────────────────────

    @http.route(
        '/re-register/form/<string:token>',
        type='http', auth='user', website=True, methods=['GET'],
    )
    def re_register_form(self, token, step=1, error=None, **kw):
        student, err = self._get_student_by_token(token)

        if not student:
            return request.render('university_student.re_registration_not_found', {})

        # State-based redirects to status pages
        if err:
            return request.render('university_student.re_registration_status_page', {
                'student': student,
                'status_key': err,
                'page_name': 're_registration',
            })

        # Security: ensure the logged-in user matches the student
        partner = request.env.user.partner_id
        if student.partner_id and student.partner_id.id != partner.id:
            return request.render('university_student.re_registration_not_found', {})

        try:
            step = int(step)
        except (ValueError, TypeError):
            step = 1
        step = max(1, min(step, TOTAL_STEPS))

        # Merge persisted draft data for pre-filling
        draft = student.get_re_registration_draft_data()

        # Collect guardian data from student (read-only in step 2)
        guardians = []
        if hasattr(student, 'guardian_ids'):
            for g in student.guardian_ids:
                guardians.append({
                    'name': g.name,
                    'relationship': g.relationship,
                    'phone_1': g.phone_1,
                    'phone_whatsapp': g.phone_whatsapp,
                    'email': g.email,
                })

        values = {
            'page_name': 're_registration',
            'student': student,
            'step': step,
            'total_steps': TOTAL_STEPS,
            'draft': draft,
            'guardians': guardians,
            'error': error,
        }
        return request.render('university_student.re_registration_form', values)

    # ──────────────────────────────────────────────────────────────────────────
    # SAVE STEP — POST
    # ──────────────────────────────────────────────────────────────────────────

    @http.route(
        '/re-register/form/<string:token>/save',
        type='http', auth='user', website=True, methods=['POST'], csrf=True,
    )
    def re_register_form_save(self, token, **post):
        student, err = self._get_student_by_token(token)
        if not student or err:
            return request.redirect(f'/re-register/form/{token}')

        # Security check
        partner = request.env.user.partner_id
        if student.partner_id and student.partner_id.id != partner.id:
            return request.redirect('/my')

        try:
            step = int(post.get('step', 1))
        except (ValueError, TypeError):
            step = 1

        # ── Save step data to draft_form_data ─────────────────────────────────
        step_data = {}

        if step == 1:
            # Personal Information (editable by student)
            for field in [
                'phone', 'phone_whatsapp', 'email',
                'address', 'city_of_residence', 'religion',
            ]:
                if field in post:
                    step_data[field] = post.get(field) or ''
            for country_field in ['phone_country_id', 'whatsapp_country_id', 'residence_country_id']:
                val = post.get(country_field)
                step_data[country_field] = int(val) if val and val.isdigit() else False

        elif step == 2:
            # Guardians — read-only, nothing to save
            pass

        elif step == 3:
            # Document Upload (optional)
            files = request.httprequest.files
            for doc_field in ['photo', 'national_id_scan', 'national_id_photo']:
                uploaded = files.get(doc_field)
                if uploaded and uploaded.filename:
                    step_data[doc_field] = base64.b64encode(uploaded.read()).decode()

        elif step == 4:
            # Medical Declaration
            medical_bool_fields = [
                'medical_diabetes', 'medical_hypertension', 'medical_asthma',
                'medical_hepatitis_b', 'medical_heart_disease', 'medical_physical_disability',
                'medical_psychiatric', 'medical_other_disease', 'medical_admitted_hospital',
            ]
            medical_char_fields = [
                'medical_diabetes_drug', 'medical_hypertension_drug', 'medical_asthma_drug',
                'medical_hepatitis_b_drug', 'medical_heart_disease_details',
                'medical_physical_disability_details', 'medical_psychiatric_details',
                'medical_other_disease_details', 'medical_admitted_hospital_details',
            ]
            for f in medical_bool_fields:
                step_data[f] = f in post and bool(post.get(f))
            for f in medical_char_fields:
                step_data[f] = post.get(f) or ''

        # Persist to student record
        student.save_re_registration_draft_data(step_data)

        # ── Final step: apply draft to record & submit ────────────────────────
        if step == TOTAL_STEPS:
            all_data = student.get_re_registration_draft_data()
            apply_vals = {}

            # Contact fields
            for field in ['phone', 'phone_whatsapp', 'email', 'address', 'city_of_residence', 'religion']:
                if field in all_data:
                    apply_vals[field] = all_data[field]
            for country_field in ['phone_country_id', 'whatsapp_country_id', 'residence_country_id']:
                if country_field in all_data and all_data[country_field]:
                    apply_vals[country_field] = all_data[country_field]

            # Document fields
            for doc_field in ['photo', 'national_id_scan', 'national_id_photo']:
                if doc_field in all_data and all_data[doc_field]:
                    apply_vals[doc_field] = all_data[doc_field].encode() if isinstance(all_data[doc_field], str) else all_data[doc_field]

            # Medical fields
            medical_all = [
                'medical_diabetes', 'medical_diabetes_drug',
                'medical_hypertension', 'medical_hypertension_drug',
                'medical_asthma', 'medical_asthma_drug',
                'medical_hepatitis_b', 'medical_hepatitis_b_drug',
                'medical_heart_disease', 'medical_heart_disease_details',
                'medical_physical_disability', 'medical_physical_disability_details',
                'medical_psychiatric', 'medical_psychiatric_details',
                'medical_other_disease', 'medical_other_disease_details',
                'medical_admitted_hospital', 'medical_admitted_hospital_details',
            ]
            for f in medical_all:
                if f in all_data:
                    apply_vals[f] = all_data[f]

            student.sudo().write(apply_vals)
            student.sudo().message_post(body=_('Student submitted re-registration form via the portal.'))

            return request.render('university_student.re_registration_success', {
                'student': student,
                'page_name': 're_registration',
            })

        # Advance to next step
        next_step = step + 1
        return request.redirect(f'/re-register/form/{token}?step={next_step}')
