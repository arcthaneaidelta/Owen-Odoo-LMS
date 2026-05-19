from odoo import http, _
from odoo.http import request
import base64
from datetime import datetime, timedelta

class AdmissionPortal(http.Controller):

	@http.route(['/admission/apply'], type='http', auth="public", website=True)
	def admission_apply(self, step=1, **post):
		"""Display or submit the admission form in multiple steps."""
		step = int(step) if str(step).isdigit() else 1
		# Create a fresh copy of the session dict so Werkzeug detects the change
		session_data = dict(request.session.get('admission_form_data', {}))

		if request.httprequest.method == 'POST':
			if step == 1:
				# Step 1: Admission Type + Personal Data
				fields_to_save = [
					'admission_type', 'name_part1_ar', 'name_part2_ar', 'name_part3_ar', 
					'name_part4_ar', 'name_en', 'gender', 'passport_number', 
					'id_document_number', 'student_nationality', 'nationality_id', 
					'country_of_birth', 'country_of_birth_id', 'date_of_birth', 'religion', 
					'address', 'city_of_residence', 'residence_country_id',
					'phone_whatsapp', 'whatsapp_country_id', 'phone', 'phone_country_id', 
					'email', 'citizenship', 'national_id', 'phone_1_country_code'
				]
				session_data.update({k: post.get(k) for k in fields_to_save})
				request.session['admission_form_data'] = session_data
				request.session.modified = True
				return request.redirect('/admission/apply?step=2')
				
			elif step == 2:
				# Step 2: Guardian Data
				guardians = []
				for key in post.keys():
					if key.startswith('guardian_name_'):
						idx = key.replace('guardian_name_', '')
						guardians.append({
							'name': post.get(f'guardian_name_{idx}'),
							'email': post.get(f'guardian_email_{idx}'),
							'phone_whatsapp': post.get(f'guardian_whatsapp_{idx}'),
							'phone_1': post.get(f'guardian_phone_{idx}'),
							'phone_1_country_id': post.get(f'guardian_phone_1_country_id_{idx}'),
							'whatsapp_country_id': post.get(f'guardian_whatsapp_country_id_{idx}'),
							'relationship': post.get(f'guardian_relation_{idx}', 'guardian'),
							'is_emergency_contact': True if idx == '0' else False, # first one is emergency
						})
				session_data['guardians'] = guardians
				request.session['admission_form_data'] = session_data
				request.session.modified = True
				return request.redirect('/admission/apply?step=3')

			elif step == 3:
				# Step 3: Admission Data
				fields_to_save = [
					'program_id', 'academic_year_id', 'financial_type', 
					'ministry_form_number', 'entry_year', 'certificate_type', 
					'high_school_grade', 'high_school_name', 'high_school_exam_number'
				]
				session_data.update({k: post.get(k) for k in fields_to_save})
				
				# Handle File Uploads
				for field in ['photo', 'passport_photo', 'national_id_photo', 'high_school_cert']:
					file = post.get(field)
					if file and hasattr(file, 'read'):
						content = file.read()
						if content:
							if len(content) > 3 * 1024 * 1024:
								return request.render("university_admission.admission_apply_form", {
									'error': _("File '%s' exceeds the 3MB limit.") % field.replace('_', ' ').title(),
									'post': session_data,
									'step': 3,
									'programs': request.env['university.program'].sudo().search([]),
									'years': request.env['university.academic_year'].sudo().search([('state', '=', 'active')]),
								})
							session_data[field] = base64.b64encode(content).decode('ascii')
				
				request.session['admission_form_data'] = session_data
				request.session.modified = True
				
				if session_data.get('admission_type') == 'regular':
					# Skip Step 4 for regular admission, go to Medical Info
					return request.redirect('/admission/apply?step=5')
				else:
					return request.redirect('/admission/apply?step=4')
					
			elif step == 4:
				# Step 4: Previous Institution Data
				fields_to_save = [
					'prev_institution_name', 'prev_years_completed', 'prev_enrollment_year',
					'prev_college_program', 'prev_graduation_cert_type'
				]
				session_data.update({k: post.get(k) for k in fields_to_save})
				
				# Handle File Uploads for Step 4
				for field in ['prev_inst_cert']:
					file = post.get(field)
					if file and hasattr(file, 'read'):
						content = file.read()
						if content:
							if len(content) > 3 * 1024 * 1024:
								return request.render("university_admission.admission_apply_form", {
									'error': _("File '%s' exceeds the 3MB limit.") % field.replace('_', ' ').title(),
									'post': session_data,
									'step': 4,
								})
							session_data[field] = base64.b64encode(content).decode('ascii')

				request.session['admission_form_data'] = session_data
				request.session.modified = True
				return request.redirect('/admission/apply?step=5')

			elif step == 5:
				# Step 5: Medical Information
				medical_fields = [
					'blood_type', 'medical_diabetes', 'medical_diabetes_drug',
					'medical_hypertension', 'medical_hypertension_drug',
					'medical_asthma', 'medical_asthma_drug',
					'medical_hepatitis_b', 'medical_hepatitis_b_drug',
					'medical_heart_disease', 'medical_heart_disease_details',
					'medical_physical_disability', 'medical_physical_disability_details',
					'medical_psychiatric', 'medical_psychiatric_details',
					'medical_other_disease', 'medical_other_disease_details',
					'medical_admitted_hospital', 'medical_admitted_hospital_details'
				]
				# Booleans from checkbox are 'on' or missing
				for field in medical_fields:
					if field in ['medical_diabetes', 'medical_hypertension', 'medical_asthma', 'medical_hepatitis_b', 
								 'medical_heart_disease', 'medical_physical_disability', 'medical_psychiatric', 
								 'medical_other_disease', 'medical_admitted_hospital']:
						session_data[field] = True if post.get(field) == 'on' else False
					else:
						session_data[field] = post.get(field)
				
				request.session['admission_form_data'] = session_data
				request.session.modified = True
				return self._process_final_submission(session_data)

		# GET request handling
		if step == 4 and session_data.get('admission_type') == 'regular':
			return request.redirect('/admission/apply?step=3')

		programs = request.env['university.program'].sudo().search([])
		years = request.env['university.academic_year'].sudo().search([('state', '=', 'active')])
		all_countries = request.env['res.country'].sudo().search([])
		
		# Add flag emoji to countries
		countries = []
		for c in all_countries:
			flag = "".join(chr(127397 + ord(char)) for char in c.code.upper()) if c.code else ""
			countries.append({
				'id': c.id,
				'name': c.name,
				'code': c.code,
				'phone_code': c.phone_code,
				'flag': flag,
			})

		return request.render("university_admission.admission_apply_form", {
			'post': session_data,
			'step': step,
			'programs': programs,
			'years': years,
			'countries': countries,
		})

	def _process_final_submission(self, data):
		"""Create records and redirect to thank you page."""
		if not data.get('program_id') or not data.get('name_part1_ar'):
			all_countries = request.env['res.country'].sudo().search([])
			countries = []
			for c in all_countries:
				flag = "".join(chr(127397 + ord(char)) for char in c.code.upper()) if c.code else ""
				countries.append({
					'id': c.id,
					'name': c.name,
					'code': c.code,
					'phone_code': c.phone_code,
					'flag': flag,
				})
			return request.render("university_admission.admission_apply_form", {
				'error': _("Your session has expired or the form data was lost. Please start the application over."),
				'post': {},
				'step': 1,
				'programs': request.env['university.program'].sudo().search([]),
				'years': request.env['university.academic_year'].sudo().search([('state', '=', 'active')]),
				'countries': countries,
			})

		# Need to explicitly typecast IDs and floats
		admission_vals = {
			k: v for k, v in data.items() 
			if k not in ['guardians', 'photo', 'passport_photo', 'national_id_photo'] and v
		}

		# Pass binary fields as is (base64 strings from session)
		for field in ['photo', 'passport_photo', 'national_id_photo']:
			if data.get(field):
				admission_vals[field] = data[field]

		if data.get('program_id'):
			admission_vals['program_id'] = int(data['program_id'])
		if data.get('academic_year_id'):
			admission_vals['academic_year_id'] = int(data['academic_year_id'])
		if data.get('entry_year'):
			admission_vals['entry_year'] = int(data['entry_year'])
		if data.get('high_school_grade'):
			admission_vals['high_school_grade'] = float(data['high_school_grade'])
		if data.get('prev_enrollment_year'):
			admission_vals['prev_enrollment_year'] = int(data['prev_enrollment_year'])
		if data.get('prev_years_completed'):
			admission_vals['prev_years_completed'] = int(data['prev_years_completed'])

		# Ensure boolean fields are set
		medical_bools = [
			'medical_diabetes', 'medical_hypertension', 'medical_asthma', 'medical_hepatitis_b', 
			'medical_heart_disease', 'medical_physical_disability', 'medical_psychiatric', 
			'medical_other_disease', 'medical_admitted_hospital'
		]
		for b in medical_bools:
			admission_vals[b] = data.get(b, False)

		if admission_vals.get('admission_type') == 'regular':
			admission_vals['starting_level'] = '1'
		else:
			admission_vals['starting_level'] = '2'

		# Combine Phone and WhatsApp with Country Code
		for phone_field, country_field in [('phone', 'phone_country_id'), ('phone_whatsapp', 'whatsapp_country_id'), ('phone_1', 'phone_1_country_id')]:
			country_id = admission_vals.get(country_field)
			base_number = admission_vals.get(phone_field)
			if country_id and base_number:
				country = request.env['res.country'].sudo().browse(int(country_id))
				if country and country.phone_code:
					prefix = str(country.phone_code)
					if not prefix.startswith('+'):
						prefix = '+' + prefix
					# Strip non-numeric from base_number if needed, or just combine
					# Clean base number (remove leading zero if prefix used)
					clean_number = base_number.lstrip('0')
					admission_vals[phone_field] = f"{prefix}{clean_number}"

		# Convert Many2one IDs to integers
		for field in ['nationality_id', 'country_of_birth_id', 'residence_country_id', 'phone_country_id', 'whatsapp_country_id']:
			if admission_vals.get(field):
				admission_vals[field] = int(admission_vals[field])

		# Duplicate check
		if data.get('ministry_form_number') and data.get('entry_year'):
			existing = request.env['university.admission'].sudo().search([
				('ministry_form_number', '=', data['ministry_form_number']),
				('entry_year', '=', data['entry_year'])
			], limit=1)
			
			if existing:
				# Error handling logic: redirect back to step 3 with error param
				return request.render("university_admission.admission_apply_form", {
					'error': _("An application with this Ministry Form Number (FRMNO) and Entry Year already exists."),
					'post': data,
					'step': 3,
					'programs': request.env['university.program'].sudo().search([]),
					'years': request.env['university.academic_year'].sudo().search([('state', '=', 'active')]),
				})

		if data.get('national_id') and data.get('academic_year_id'):
			existing_national = request.env['university.admission'].sudo().search([
				('national_id', '=', data['national_id']),
				('academic_year_id', '=', int(data['academic_year_id']))
			], limit=1)
			
			if existing_national:
				all_countries = request.env['res.country'].sudo().search([])
				countries = []
				for c in all_countries:
					flag = "".join(chr(127397 + ord(char)) for char in c.code.upper()) if c.code else ""
					countries.append({
						'id': c.id,
						'name': c.name,
						'code': c.code,
						'phone_code': c.phone_code,
						'flag': flag,
					})
				return request.render("university_admission.admission_apply_form", {
					'error': _("An application with this National ID and Academic Year already exists."),
					'post': data,
					'step': 1,
					'programs': request.env['university.program'].sudo().search([]),
					'years': request.env['university.academic_year'].sudo().search([('state', '=', 'active')]),
					'countries': countries,
				})

		# Create Admission in awaiting_verification state
		admission_vals.update({
			'state': 'awaiting_verification',
			'verification_deadline': datetime.now() + timedelta(minutes=30),
		})
		admission = request.env['university.admission'].sudo().create(admission_vals)

		# Create Guardians
		if data.get('guardians'):
			guardian_vals = []
			for g in data['guardians']:
				# Combine Phone and WhatsApp for each guardian
				for phone_field, country_field in [('phone_1', 'phone_1_country_id'), ('phone_whatsapp', 'whatsapp_country_id')]:
					country_id = g.get(country_field)
					base_number = g.get(phone_field)
					if country_id and base_number:
						country = request.env['res.country'].sudo().browse(int(country_id))
						if country and country.phone_code:
							prefix = str(country.phone_code)
							if not prefix.startswith('+'):
								prefix = '+' + prefix
							# Clean base number (remove leading zero if prefix used)
							clean_number = base_number.lstrip('0')
							g[phone_field] = f"{prefix}{clean_number}"
				
				# Remove temporary fields before creation (or keep if fields exist)
				# Based on user request, they don't want them in the form, 
				# but we can keep them in data if fields exist in DB.
				# For now, we only need the combined string in phone_1/phone_whatsapp.
				
				g['admission_id'] = admission.id
				guardian_vals.append(g)
			request.env['university.guardian'].sudo().create(guardian_vals)

		# Trigger Email Verification
		if admission.email:
			admission.sudo().action_verify_email()

		# Clear session data
		request.session.pop('admission_form_data', None)

		return request.render("university_admission.admission_verification_pending", {'admission': admission})

	@http.route(['/admission/verify_email'], type='http', auth="public", website=True)
	def admission_verify_email(self, token=None, **kwargs):
		if not token:
			return request.render("university_admission.admission_verification_failed", {
				'error': _("Invalid verification link. Token is missing.")
			})
			
		admission = request.env['university.admission'].sudo().search([('email_verification_token', '=', token)], limit=1)
		
		if not admission:
			return request.render("university_admission.admission_verification_failed", {
				'error': _("Invalid or expired verification link.")
			})

		# If already verified via another method
		if admission.is_email_verified:
			return request.render("university_admission.admission_thanks", {'admission': admission})

		# Check 30-minute timeout ONLY if it's the initial unverified website state
		if admission.state == 'awaiting_verification' and admission.verification_deadline:
			if datetime.now() > admission.verification_deadline:
				email = admission.email
				admission.sudo().unlink()
				return request.render("university_admission.admission_verification_expired", {
					'email': email
				})
			
			# Successfully verified within 30 minutes
			admission.sudo().write({
				'state': 'draft',
				'is_email_verified': True
			})
			admission.sudo().message_post(body=_("Email verified successfully via the verification link."))
			return request.render("university_admission.admission_thanks", {'admission': admission})

		# If created from backend (state is 'draft' or beyond), just verify and show thanks
		if admission.state in ['draft', 'submitted', 'approved', 'registered']:
			admission.sudo().write({'is_email_verified': True})
			admission.sudo().message_post(body=_("Email verified successfully via the verification link."))
			return request.render("university_admission.admission_thanks", {'admission': admission})

		return request.render("university_admission.admission_verification_failed", {
			'error': _("Verification failed. Invalid state.")
		})

	@http.route(['/admission/check_status/<int:admission_id>'], type='json', auth="public", website=True)
	def admission_check_status(self, admission_id, **kwargs):
		"""AJAX route to check if the email has been verified in another tab."""
		admission = request.env['university.admission'].sudo().browse(admission_id)
		if not admission.exists():
			return {'status': 'expired'}
		if admission.state != 'awaiting_verification':
			return {'status': 'verified'}
		return {'status': 'pending'}

	@http.route(['/admission/thanks'], type='http', auth="public", website=True)
	def admission_thanks_page(self, admission_id=None, **kwargs):
		"""Public route for the thanks page (used after verification)."""
		if not admission_id:
			return request.redirect('/admission/apply')
		admission = request.env['university.admission'].sudo().browse(int(admission_id))
		if not admission.exists() or not admission.is_email_verified:
			return request.redirect('/admission/apply')
		return request.render("university_admission.admission_thanks", {'admission': admission})
