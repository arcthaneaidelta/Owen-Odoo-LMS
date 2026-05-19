# -*- coding: utf-8 -*-
"""
Key changes vs previous version
================================
1. action_ministry_approve  →  scans university.ministry.bank using
	unique key  (ministry_form_number + entry_year)  and auto-fills
	all Ministry fields into the admission record.
2. academic_year_str is now a plain Char (NOT a related field) so it
	can be overwritten by the bank data exchange.
3. guardian_ids inverse field is 'admission_id' (matches guardian model).
"""
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class UniversityAdmission(models.Model):
	_name = 'university.admission'
	_description = 'Student Admission Application'
	_inherit = ['mail.thread', 'mail.activity.mixin']
	_order = 'application_date desc, name'

	# ─── Sequence ─────────────────────────────────────────────────────────────
	name = fields.Char(string='Application Reference', readonly=True,
						copy=False, default='New')

	# ─── State Machine ────────────────────────────────────────────────────────
	state = fields.Selection(
		 [
			  ('awaiting_verification', 'Awaiting Email Verification'),
			  ('draft', '1. Draft'),
			  ('validated', '2. Validated'),
			  ('medical_review', '3. Medical Review'),
			  ('program_review', '4. Program Review'),
			  ('ministry_approved', '5. Ministry Approved'),
			  ('head_approval', '6. Head Approval'),
			  ('academic_affair', '6. Academic Affair Approval'),
			  ('approved', '7. Approved'),
			  ('rejected', 'Rejected'),
			  ('cancelled', 'Cancelled'),
		 ],
		 string='Stage', default='draft', required=True,
		 tracking=True, copy=False,
	)
	verification_deadline = fields.Datetime(string='Verification Deadline', copy=False)

	# ─── Applicant Info ───────────────────────────────────────────────────────
	application_date = fields.Date(string='Application Date', required=True,
									default=fields.Date.today, tracking=True)
	name_en = fields.Char(string='Name (English)')
	display_name_ar = fields.Char(
		string='Full Arabic Name',
		compute='_compute_display_name_ar',
		store=True,
	)
	gender = fields.Selection(
		[('male', 'Male'), ('female', 'Female')],
		string='Gender', required=True,
	)
	date_of_birth = fields.Date(string='Date of Birth')
	phone = fields.Char(string='Phone', required=True)
	phone_country_id = fields.Many2one('res.country', string='Phone Country Code')
	phone_whatsapp = fields.Char(string='WhatsApp')
	whatsapp_country_id = fields.Many2one('res.country', string='WhatsApp Country Code')
	email = fields.Char(string='Email')
	is_email_verified = fields.Boolean(string='Email Verified', default=False)
	email_verification_token = fields.Char(string='Email Verification Token', copy=False, readonly=True)
	is_whatsapp_verified = fields.Boolean(string='WhatsApp Verified', default=False)

	# ─── Demographics & Additional Personal Info ──────────────────────────────
	passport_number = fields.Char(string='Passport Number', tracking=True)
	id_document_number = fields.Char(string='ID Document Number', tracking=True)
	student_nationality = fields.Char(string='Student Nationality (Legacy)', tracking=True)
	nationality_id = fields.Many2one('res.country', string='Nationality', tracking=True)
	country_of_birth = fields.Char(string='Country of Birth (Legacy)')
	country_of_birth_id = fields.Many2one('res.country', string='Country of Birth')
	religion = fields.Char(string='Religion')
	address = fields.Text(string='Detailed Address')
	city_of_residence = fields.Char(string='City of Residence')
	residence_country_id = fields.Many2one('res.country', string='Country of Residence')

	# ─── Guardians ────────────────────────────────────────────────────────────
	guardian_ids = fields.One2many(
		'university.guardian',
		'admission_id',
		string='Guardians',
	)

	# ─── Program ──────────────────────────────────────────────────────────────
	program_id = fields.Many2one('university.program', string='Requested Program',
								 required=True, tracking=True)
	college_id = fields.Many2one('university.college',
								 related='program_id.college_id',
								 store=True, readonly=True)
	admission_type = fields.Selection(
		[
			('regular', 'Regular Admission'),
			('bridging', 'Bridging'),
			('mature', 'Mature'),
			('transfer', 'Transfer'),
		],
		string='Admission Type', required=True, default='regular', tracking=True,
	)
	assigned_subject_ids = fields.Many2many(
		'university.subject',
		relation='university_admission_assigned_subject_rel',
		column1='admission_id',
		column2='subject_id',
		string='Assigned Subjects',
		help='For Bridging, Mature, or Transfer students, assign up to a maximum of 4 subjects to study.',
	)
	financial_type = fields.Selection(
		[
			('citizen', 'Sudanese Citizen'),
			('foreigner', 'Foreigner'),
		],
		string='Financial Type', required=True, default='citizen', tracking=True,
	)
	academic_year_id = fields.Many2one('university.academic_year',
										string='Academic Year',
										required=True, tracking=True)

	# ─── Ministry Import Fields ────────────────────────────────────────────────
	# These are populated either manually or auto-filled from the Ministry Bank
	ministry_form_number = fields.Char(
		string='FRMNO',
		help='Forum Number – entered manually by student on the form. '
			 'Combined with Entry Year, this is the unique search key.',
		index=True, tracking=True, copy=False,
	)
	entry_year = fields.Char(
		string='Entry Year',
		help='Admission year entered by student (e.g. 2021). '
			 'Combined with FRMNO to create the unique Ministry search key.',
		tracking=True,
	)
	ministry_fac_code = fields.Char(string='FAC')
	ministry_university_id_code = fields.Integer(string='UNIV_ID', index=True)
	# ministry_university_number = fields.Char(
	# 	string='Ministry University Number', tracking=True, copy=False)

	name_part1_ar = fields.Char(string='N1 (First Name)', required=True, tracking=True)
	name_part2_ar = fields.Char(string='N2 (Father\'s Name)', required=True, tracking=True)
	name_part3_ar = fields.Char(string='N3 (Grandfather\'s Name)', tracking=True)
	name_part4_ar = fields.Char(string='N4 (Family Name)', tracking=True)

	school_name = fields.Char(string='SCNAME (School)')
	gob_number = fields.Integer(string='GOBNO')
	faculty_name_ar = fields.Char(string='FACNAME')
	admission_type_text = fields.Char(string='GOBOLS')

	# academic_year_str is a plain Char so it can be overwritten by bank data
	academic_year_str = fields.Char(
		string='YEAR',
		help='Academic year string from Ministry (e.g. 2021/2020). '
			 'Auto-filled when Ministry Approved button is clicked.',
	)
	batch_id = fields.Many2one(
		'university.batch', 
		string='Batch', 
		domain="[('program_id', '=', program_id), ('state', '=', 'active')]",
		tracking=True
	)
	national_id = fields.Char(string='NATIONAL_ID', index=True,
								tracking=True, copy=False)
	gender_code = fields.Integer(string='SEX')
	university_name_ar = fields.Char(string='UNIVERSITY')
	internal_admission_type = fields.Char(string='Internal Admission Type')
	citizenship = fields.Selection(
		[('citizen', 'Citizen'), ('foreigner', 'Foreigner')],
		string='Citizenship'
	)

	# ─── Certificate Info ──────────────────────────────────────────────────────
	certificate_type = fields.Char(string='Certificate Type')
	high_school_grade = fields.Float(string='High School Grade %')
	high_school_name = fields.Char(string='High School Name')

	# ─── Previous Institution (For Bridging/Mature/Transfer) ──────────────────
	prev_institution_name = fields.Char(string='Previous Institution Name')
	prev_years_completed = fields.Integer(string='Years Completed')
	prev_enrollment_year = fields.Integer(string='Enrollment Year')
	prev_college_program = fields.Char(string='College / Program / Major')
	prev_graduation_cert_type = fields.Char(string='Graduation Certificate Type')
	starting_level = fields.Selection(
		[
			('1', 'Level 1'),
			('2', 'Level 2'),
			('3', 'Level 3'),
			('4', 'Level 4'),
			('5', 'Level 5'),
			('6', 'Level 6'),
		],
		string='Starting Level',
		default='1',
		required=True,
		tracking=True,
	)
	fin_position = fields.Char(string='Fin-Position')

	ministry_submission_date = fields.Date(string='Ministry Submission Date', tracking=True)

	# ── Bank match link ────────────────────────────────────────────────────────
	ministry_bank_id = fields.Many2one(
		'university.ministry.bank',
		string='Matched Bank Record',
		readonly=True, copy=False,
	)

	# ─── Medical Review ───────────────────────────────────────────────────────
	medical_reviewer_id = fields.Many2one('res.users', string='Medical Reviewer', tracking=True)
	medical_review_date = fields.Date(string='Medical Review Date')
	medical_result = fields.Selection(
		[('pending', 'Pending'), ('pass', 'Passed'),
		 ('fail', 'Failed'), ('conditional', 'Conditional Pass')],
		string='Medical Result', default='pending', tracking=True,
	)
	color_blindness_result = fields.Selection(
		[('pass', 'Pass'), ('fail', 'Fail'), ('na', 'N/A')],
		string='Color Blindness Test', default='na',
	)
	health_book_scan = fields.Binary(string='Health Book Scan', attachment=True)
	medical_notes = fields.Text(string='Medical Notes')

	# ─── Program Review ───────────────────────────────────────────────────────
	program_reviewer_id = fields.Many2one('res.users', string='Program Reviewer', tracking=True)
	program_review_date = fields.Date(string='Program Review Date')
	program_review_notes = fields.Text(string='Program Review Notes')

	# ─── Head Approval ────────────────────────────────────────────────────────
	head_approver_id = fields.Many2one('res.users', string='Head of Admissions', tracking=True)
	head_approval_date = fields.Date(string='Head Approval Date')
	head_approval_notes = fields.Text(string='Approval Notes')

	# ─── Academic Affair Approval ────────────────────────────────────────────────────────
	academic_affair_approver_id = fields.Many2one('res.users', string='Acadmic Affairs', tracking=True)
	academic_affair_approval_date = fields.Date(string='Academic Affairs Approval Date')
	academic_affair_approval_notes = fields.Text(string='Academic Affairs Approval Notes')

	# ─── Finance ──────────────────────────────────────────────────────────────
	# currency_id = fields.Many2one('res.currency', string='Currency',
	#                               default=lambda self: self.env.company.currency_id,
	#                               required=True)

	currency_id = fields.Many2one(
		'res.currency',
		string='Currency',
		default=lambda self: self.env['res.currency'].search([('name', '=', 'SDG')], limit=1)
	)
	admission_fee = fields.Monetary(string='Admission Fee', currency_field='currency_id',
									required=True, default=0.0)
	registration_fee = fields.Monetary(string='Registration Fee', currency_field='currency_id', default=0.0, tracking=True)
	tuition_fee = fields.Monetary(string='Tuition Fee', currency_field='currency_id', default=0.0, tracking=True)

	invoice_id = fields.Many2one('account.move', string='Invoice', copy=False, tracking=True)
	invoice_state = fields.Selection(related='invoice_id.payment_state',
									 string='Invoice Payment Status', readonly=True)
	bank_reference = fields.Char(string='Bank Reference Number', tracking=True)

	# ─── Result ───────────────────────────────────────────────────────────────
	student_id = fields.Many2one('university.student', string='Created Student',
								 copy=False, readonly=True, tracking=True)
	rejection_reason = fields.Text(string='Rejection Reason')

	# ─── Transfer Equivalency ─────────────────────────────────────────────────
	subject_equivalency_ids = fields.One2many(
		'university.subject.equivalency', 'admission_id', string='Subject Equivalencies')

	# ─── Documents ────────────────────────────────────────────────────────────
	national_id_scan = fields.Binary(string='National ID Scan', attachment=True)
	photo = fields.Binary(string='Photo', attachment=True)
	passport_photo = fields.Binary(string='Passport Photo', attachment=True)
	national_id_photo = fields.Binary(string='National ID Photo', attachment=True)
	high_school_cert = fields.Binary(string='High School Certificate', attachment=True)
	prev_inst_cert = fields.Binary(string='Previous Institution Certificate', attachment=True)
	high_school_exam_number = fields.Char(string='High School Exam Number', tracking=True)
	# previous_transcript = fields.Binary(string='Previous Transcript', attachment=True)
	# ─── Medical History ──────────────────────────────────────────────────────
	blood_type = fields.Selection([
		('A+', 'A+'), ('A-', 'A-'),
		('B+', 'B+'), ('B-', 'B-'),
		('AB+', 'AB+'), ('AB-', 'AB-'),
		('O+', 'O+'), ('O-', 'O-')
	], string='Blood Type', tracking=True)
	# Section A: Chronic Diseases
	medical_diabetes = fields.Boolean(string='Diabetes Mellitus')
	medical_diabetes_drug = fields.Char(string='Type of Drug (Diabetes)')
	medical_hypertension = fields.Boolean(string='Hypertension')
	medical_hypertension_drug = fields.Char(string='Type of Drug (Hypertension)')
	medical_asthma = fields.Boolean(string='Bronchial Asthma')
	medical_asthma_drug = fields.Char(string='Type of Drug (Asthma)')
	medical_hepatitis_b = fields.Boolean(string='Hepatitis B')
	medical_hepatitis_b_drug = fields.Char(string='Type of Drug (Hepatitis B)')
	
	# Section B: Other Diseases
	medical_heart_disease = fields.Boolean(string='Heart Disease')
	medical_heart_disease_details = fields.Char(string='Determine (Heart Disease)')
	medical_physical_disability = fields.Boolean(string='Physical Disability')
	medical_physical_disability_details = fields.Char(string='Determine (Physical Disability)')
	medical_psychiatric = fields.Boolean(string='Psychiatric Disease')
	medical_psychiatric_details = fields.Char(string='Determine (Psychiatric)')
	medical_other_disease = fields.Boolean(string='Any Other Disease')
	medical_other_disease_details = fields.Char(string='Determine (Other Disease)')

	# Section C: Hospitalization
	medical_admitted_hospital = fields.Boolean(string='Admitted in hospital before?')
	medical_admitted_hospital_details = fields.Char(string='Explain (Hospitalization)')

	notes = fields.Text(string='Internal Notes')

	# ─── SQL Constraints ──────────────────────────────────────────────────────
	_sql_constraints = [
		('national_id_year_uniq',
		 'unique(national_id, academic_year_id)',
		 'An application for this National ID and academic year already exists.'),
	]

	# ═══════════════════════════════════════════════════════════════════════════
	# COMPUTES
	# ═══════════════════════════════════════════════════════════════════════════

	@api.depends('name_part1_ar', 'name_part2_ar', 'name_part3_ar', 'name_part4_ar')
	def _compute_display_name_ar(self):
		for rec in self:
			parts = [rec.name_part1_ar or '', rec.name_part2_ar or '',
					 rec.name_part3_ar or '', rec.name_part4_ar or '']
			rec.display_name_ar = ' '.join(p for p in parts if p.strip())

	@api.onchange('financial_type')
	def _onchange_financial_type(self):
		"""Set currency based on financial type and convert fee."""
		if not self.financial_type:
			return

		old_currency = self.currency_id
		if self.financial_type == 'citizen':
			new_currency = self.env['res.currency'].search([('name', '=', 'SDG')], limit=1)
		elif self.financial_type == 'foreigner':
			new_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
		else:
			new_currency = False

		if new_currency and new_currency != old_currency:
			self.currency_id = new_currency
			date_cvt = self.application_date or fields.Date.today()
			if self.admission_fee:
				self.admission_fee = old_currency._convert(self.admission_fee, new_currency, self.env.company, date_cvt)
			if self.registration_fee:
				self.registration_fee = old_currency._convert(self.registration_fee, new_currency, self.env.company, date_cvt)
			if self.tuition_fee:
				self.tuition_fee = old_currency._convert(self.tuition_fee, new_currency, self.env.company, date_cvt)

	@api.onchange('program_id')
	def _onchange_program_for_fees(self):
		if self.program_id:
			self.registration_fee = self.program_id.registration_fee
			self.tuition_fee = self.program_id.tuition_fee


	@api.constrains('admission_type', 'starting_level', 'program_id')
	def _check_admission_level_rules(self):
		for rec in self:
			# 1st Scenario -> Regular Admission: Level 1 only
			if rec.admission_type == 'regular' and rec.starting_level != '1':
				raise ValidationError(_(
					'Regular Admission is only allowed for Level 1.'
				))
			
			# 2nd, 3rd, 4th Scenarios (Bridging, Mature, Transfer): Level 2 or 3
			if rec.admission_type in ['bridging', 'mature', 'transfer']:
				if rec.starting_level not in ['2', '3']:
					raise ValidationError(_(
						'Bridging, Mature, and Transfer students must start at Level 2 or Level 3.'
					))
				
				# Minister Rule: Must study at least 50% of the program
				# Example: 5 years -> must study 2.5 years. If level 3, they study 3, 4, 5 (3 years).
				# Max starting level calculation:
				if rec.program_id.duration_years:
					max_skip = rec.program_id.duration_years / 2.0
					if int(rec.starting_level) - 1 > max_skip:
						raise ValidationError(_(
							'Level Placement Rule: Student must study at least 50%% of the program curriculum. '
							'For a %s-year program, the maximum starting level is Level %d.'
						) % (rec.program_id.duration_years, int(max_skip) + 1))

	@api.constrains('assigned_subject_ids', 'admission_type')
	def _check_assigned_subjects(self):
		for rec in self:
			if rec.admission_type != 'regular' and len(rec.assigned_subject_ids) > 4:
				raise ValidationError(_(
					'You can assign a maximum of 4 subjects for non-regular admission students.'
				))
			if rec.admission_type == 'regular' and rec.assigned_subject_ids:
				raise ValidationError(_(
					'Assigned Subjects should not be used for Regular Admission students.'
				))

	# ═══════════════════════════════════════════════════════════════════════════
	# CREATE
	# ═══════════════════════════════════════════════════════════════════════════

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if vals.get('name', 'New') == 'New':
				vals['name'] = self.env['ir.sequence'].next_by_code(
					'university.admission') or 'New'
		return super().create(vals_list)

	# ═══════════════════════════════════════════════════════════════════════════
	# STATE TRANSITIONS
	# ═══════════════════════════════════════════════════════════════════════════

	def action_validate(self):
		self.ensure_one()
		self._check_mandatory_fields()
		self._check_duplicate_national_id()
		self.write({'state': 'validated'})
		self.message_post(body=_('Application validated successfully.'))

	def action_send_to_medical(self):
		self.ensure_one()
		self.write({'state': 'medical_review'})
		self.message_post(body=_('Sent to medical committee for review.'))

	def action_medical_approve(self):
		self.ensure_one()
		if self.medical_result == 'fail':
			raise UserError(_('Medical result is FAIL. Cannot proceed.'))
		self.write({
			'state': 'program_review',
			'medical_reviewer_id': self.env.user.id,
			'medical_review_date': fields.Date.today(),
		})
		self.message_post(body=_('Medical review passed.'))

	def action_program_approve(self):
		self.ensure_one()
		self.write({
			'state': 'ministry_approved',          # ← now goes to ministry
			'program_reviewer_id': self.env.user.id,
			'program_review_date': fields.Date.today(),
		})
		self.message_post(body=_('Program review approved.'))


	def action_ministry_approve(self):
		"""
		Stage 3 → 4: Scan the Ministry Bank using FRMNO + Entry Year.
		If a matching record is found, auto-fill all Ministry fields.
		Ministry data takes ABSOLUTE priority (name, codes, batch, etc.)
		"""
		self.ensure_one()

		# Validate search keys exist on this application
		if not self.ministry_form_number:
			raise UserError(_(
				'Please enter the FRMNO (Forum Number) on the application '
				'before approving Ministry.'
			))
		if not self.entry_year:
			raise UserError(_(
				'Please enter the Entry Year on the application '
				'before approving Ministry.'
			))

		# Search bank using the unique key: FRMNO + Entry Year
		bank_record = self.env['university.ministry.bank'].search([
			('ministry_form_number', '=', self.ministry_form_number),
			('entry_year', '=', self.entry_year),
		], limit=1)

		if not bank_record:
			raise UserError(_(
				'No record found in the Ministry Bank for:\n'
				'FRMNO: %s\n'
				'Entry Year: %s\n\n'
				'Please import the Ministry Excel sheet into the Ministry Bank first, '
				'or verify the FRMNO and Entry Year are correct.'
			) % (self.ministry_form_number, self.entry_year))

		# ── Auto-fill: Ministry data takes ABSOLUTE priority ──────────────────
		vals = {
			'state': 'head_approval',
			'ministry_bank_id': bank_record.id,
			# Name parts from Ministry (override what student entered)
			'name_part1_ar': bank_record.name_part1_ar or self.name_part1_ar,
			'name_part2_ar': bank_record.name_part2_ar or self.name_part2_ar,
			'name_part3_ar': bank_record.name_part3_ar or self.name_part3_ar,
			'name_part4_ar': bank_record.name_part4_ar or self.name_part4_ar,
			# All Ministry codes
			'ministry_fac_code': bank_record.ministry_fac_code,
			'ministry_university_id_code': bank_record.ministry_university_id_code,
			'school_name': bank_record.school_name,
			'gob_number': bank_record.gob_number,
			'faculty_name_ar': bank_record.faculty_name_ar,
			'admission_type_text': bank_record.admission_type_text,
			'academic_year_str': bank_record.academic_year_str,
			'batch_id': self.env['university.batch'].search([('batch_number', '=', bank_record.batch_number)], limit=1).id if bank_record.batch_number else False,
			'gender_code': bank_record.gender_code,
			'university_name_ar': bank_record.university_name_ar,
			'internal_admission_type': bank_record.internal_admission_type.lower() if bank_record.internal_admission_type and bank_record.internal_admission_type.lower() in ['regular', 'bridging', 'mature', 'transfer'] else False,
			'admission_type': bank_record.internal_admission_type.lower() if bank_record.internal_admission_type and bank_record.internal_admission_type.lower() in ['regular', 'bridging', 'mature', 'transfer'] else False,
			'citizenship': bank_record.citizenship.lower() if bank_record.citizenship and bank_record.citizenship.lower() in ['citizen', 'foreigner'] else False,
			'starting_level': bank_record.starting_level,
			'fin_position': bank_record.fin_position,
		}
		# Use national_id from bank if not already set
		if bank_record.national_id and not self.national_id:
			vals['national_id'] = bank_record.national_id

		self.write(vals)

		# Mark bank record as matched
		bank_record.write({
			'is_matched': True,
			'matched_admission_id': self.id,
		})

		self.message_post(
			body=_(
				'Ministry approved. Data auto-filled from Ministry Bank record '
				'(FRMNO: %s, Year: %s, Batch: %s).\n'
				'Name updated to: %s'
			) % (
				bank_record.ministry_form_number,
				bank_record.entry_year,
				bank_record.batch_number,
				self.display_name_ar,
			)
		)


	def action_head_approve(self):
		self.ensure_one()

		if not self.batch_id:
			raise UserError(_("A Batch must be selected before Head Approval."))
		if self.registration_fee <= 0:
			raise UserError(_("Registration Fee must be greater than 0 before Head Approval."))
		if self.tuition_fee <= 0:
			raise UserError(_("Tuition Fee must be greater than 0 before Head Approval."))
		
		

		self.write({
			'head_approver_id': self.env.user.id,
			'head_approval_date': fields.Date.today(),
			'state': 'academic_affair',
		})
		self.message_post(body=_('Head approved.'))


	def action_academic_affair_approval(self):
		self.ensure_one()

		if not self.email:
			raise UserError(_("Email address is required to create a portal user and approve the student."))

		student = self._create_student_from_admission()
		
		# --------------------------Work on it when the invoicing module starts------------------------------------
		reg_inv = self._create_fee_invoice(self.registration_fee, 'Registration Fee', 'Registration Fee')
		tui_inv = self._create_fee_invoice(self.tuition_fee, 'Tuition Fee', 'Tuition Fee')
		
		# Auto-post invoices so they are ready for payment
		if reg_inv: reg_inv.action_post()
		if tui_inv: tui_inv.action_post()
		
		student.write({
			'registration_invoice_id': reg_inv.id if reg_inv else False,
			'tuition_invoice_id': tui_inv.id if tui_inv else False,
		})
		# ----------------------------------------------------------------------------------------------------------

		# --- Portal User Setup ---
		username = self.email
		user_obj = self.env['res.users']
		
		existing_user = user_obj.sudo().search([('login', '=', username)], limit=1)
		
		if not existing_user:
			existing_partner = self._get_or_create_partner()
			
			user = user_obj.sudo().create({
				'name': self.display_name_ar or self.name_en,
				'login': username,
				'partner_id': existing_partner.id,
				'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
			})
			# Trigger the standard password reset email
			user.action_reset_password()
		else:
			existing_partner = existing_user.partner_id

		# Link the partner to the student
		student.write({
			'partner_id': existing_partner.id
		})

		self.write({
			'academic_affair_approver_id': self.env.user.id,
			'academic_affair_approval_date': fields.Date.today(),
			'student_id': student.id,
			'state': 'approved'
			})

	# def action_confirm_payment(self):
	# 	self.ensure_one()
	# 	if not self.invoice_id or self.invoice_id.payment_state not in ('paid', 'in_payment'):
	# 		raise UserError(_(
	# 			'Invoice must be paid before confirming payment. '
	# 			'Please record payment on invoice %s first.'
	# 		) % (self.invoice_id.name if self.invoice_id else ''))
	# 	self.write({'state': 'payment_received'})
	# 	self.message_post(body=_('Payment confirmed.'))

	# def action_register_student(self):
	# 	self.ensure_one()
	# 	# if self.state != 'payment_received':
	# 	# 	raise UserError(_('Payment must be confirmed before registration.'))
	# 	if not self.student_id:
	# 		raise UserError(_("No student record found. Please ensure the student was created during approval."))
	# 	self.write({'state': 'registered'})
	# 	self.message_post(body=_('Application marked as fully registered.'))

	def action_reject(self):
		self.write({'state': 'rejected'})
		self.message_post(body=_('Application rejected.'))

	def action_cancel(self):
		self.write({'state': 'cancelled'})

	def action_reset_to_draft(self):
		self.write({'state': 'draft'})

	# ═══════════════════════════════════════════════════════════════════════════
	# PRIVATE HELPERS
	# ═══════════════════════════════════════════════════════════════════════════

	def _check_mandatory_fields(self):
		required = {
			'name_part1_ar': _('First Name (N1)'),
			'name_part2_ar': _("Father's Name (N2)"),
			'national_id': _('National ID'),
			'program_id': _('Program'),
			'academic_year_id': _('Academic Year'),
			'phone': _('Phone'),
			'email': _('Email'),
			'ministry_form_number': _('FRMNO (Forum Number)'),
			'entry_year': _('Entry Year'),
		}
		missing = [label for fname, label in required.items() if not self[fname]]
		if missing:
			raise ValidationError(
				_('Required fields missing: %s') % ', '.join(missing))

	def _check_duplicate_national_id(self):
		existing = self.env['university.student'].search([
			('national_id', '=', self.national_id)])
		if existing:
			raise ValidationError(_(
				'A student with National ID "%s" already exists: %s'
			) % (self.national_id, existing.display_name_ar))

	
	# --------------------------Work on it when the invoicing module starts------------------------------------
	def _create_admission_invoice(self):
		return self._create_fee_invoice(self.admission_fee, 'Admission Fee', 'Admission Fee')

	def _get_or_create_fee_product(self, product_name):
		"""
		Find or auto-create a service product for fee invoicing.
		Having a real product guarantees Odoo picks an income account,
		which fixes the payment direction (inbound vs outbound).
		"""
		Product = self.env['product.product']
		product = Product.search([('name', '=', product_name)], limit=1)
		if not product:
			# Find a suitable income account for the product's category
			income_account = self.env['account.account'].search([
				('account_type', 'in', ['income', 'income_other']),
				('deprecated', '=', False),
			], limit=1)

			product_vals = {
				'name': product_name,
				'type': 'service',
				'invoice_policy': 'order',
				'sale_ok': True,
				'purchase_ok': False,
				'taxes_id': [],        # clear sale taxes to keep it simple
				'supplier_taxes_id': [],
			}
			if income_account:
				product_vals['property_account_income_id'] = income_account.id

			product = Product.sudo().create(product_vals)
		return product

	def _create_fee_invoice(self, amount, fee_desc, product_name):
		if amount <= 0:
			return self.env['account.move']

		invoice_currency = self.currency_id
		company_currency = self.env.company.currency_id

		# ── Journal selection: prefer one that supports the invoice currency ──
		# 1st: sale journal whose own currency matches (e.g. an SDG journal)
		journal = self.env['account.journal'].search([
			('type', '=', 'sale'),
			('currency_id', '=', invoice_currency.id),
		], limit=1)
		# 2nd: sale journal with no explicit currency (uses company currency)
		if not journal:
			journal = self.env['account.journal'].search([
				('type', '=', 'sale'),
				('currency_id', '=', False),
			], limit=1)
		# 3rd: any sale journal
		if not journal:
			journal = self.env['account.journal'].search(
				[('type', '=', 'sale')], limit=1)

		# Use the real product so Odoo resolves the correct income account
		# and the payment register wizard defaults to Inbound (Receive Money).
		product = self._get_or_create_fee_product(product_name)

		line_description = _('%s – %s (%s)') % (
			fee_desc, self.display_name_ar, self.program_id.name or ''
		)

		invoice_vals = {
			'move_type': 'out_invoice',
			'partner_id': self._get_or_create_partner().id,
			'invoice_date': fields.Date.today(),
			'invoice_date_due': fields.Date.today(),
			'ref': f"{self.name} - {fee_desc}",
			# Always set the currency explicitly so it is honoured
			# regardless of the journal's own currency setting.
			'currency_id': invoice_currency.id,
			'invoice_line_ids': [(0, 0, {
				'product_id': product.id,
				'name': line_description,
				'quantity': 1,
				'price_unit': amount,
				# Force the price unit in the invoice currency — prevents
				# Odoo from silently converting to the company currency.
				'currency_id': invoice_currency.id,
			})],
		}
		if journal:
			invoice_vals['journal_id'] = journal.id
		return self.env['account.move'].create(invoice_vals)

	def _get_or_create_partner(self):
		partner = self.env['res.partner'].sudo().search(
			['|', ('email', '=', self.email), ('name', '=', self.display_name_ar)], limit=1)
		if not partner:
			receivable = self.env['account.account'].search(
				[('account_type', '=', 'asset_receivable')], limit=1)
			payable = self.env['account.account'].search(
				[('account_type', '=', 'liability_payable')], limit=1)
			partner = self.env['res.partner'].sudo().create({
				'name': self.display_name_ar or self.name_en,
				'phone': self.phone,
				'email': self.email,
				'country_id': self.residence_country_id.id,
				'customer_rank': 1,
				'supplier_rank': 0,
				'property_account_receivable_id': receivable.id if receivable else False,
				'property_account_payable_id': payable.id if payable else False,
			})
		return partner
	# ------------------------------------------------------------------------------------------------------------


	def _create_student_from_admission(self):
		batch_id = self.batch_id.id if self.batch_id else False
		if not batch_id and self.program_id:
			batch = self.env['university.batch'].search([
				('program_id', '=', self.program_id.id), 
				('state', '=', 'active')
			], limit=1)
			if batch:
				batch_id = batch.id

		vals = {
			'name_part1_ar': self.name_part1_ar,
			'name_part2_ar': self.name_part2_ar,
			'name_part3_ar': self.name_part3_ar,
			'name_part4_ar': self.name_part4_ar,
			'display_name_ar': self.display_name_ar,
			'name_en': self.name_en,
			'national_id': self.national_id,
			'gender': self.gender,
			'date_of_birth': self.date_of_birth,
			'phone': self.phone,
			'phone_country_id': self.phone_country_id.id if self.phone_country_id else False,
			'phone_whatsapp': self.phone_whatsapp,
			'whatsapp_country_id': self.whatsapp_country_id.id if self.whatsapp_country_id else False,
			'email': self.email,
			'passport_number': self.passport_number,
			'id_document_number': self.id_document_number,
			'student_nationality': self.student_nationality,
			'nationality_id': self.nationality_id.id if self.nationality_id else False,
			'country_of_birth': self.country_of_birth,
			'country_of_birth_id': self.country_of_birth_id.id if self.country_of_birth_id else False,
			'religion': self.religion,
			'address': self.address,
			'city_of_residence': self.city_of_residence,
			'residence_country_id': self.residence_country_id.id if self.residence_country_id else False,
			'certificate_type': self.certificate_type,
			'high_school_grade': self.high_school_grade,
			'high_school_name': self.high_school_name,
			'prev_institution_name': self.prev_institution_name,
			'prev_years_completed': self.prev_years_completed,
			'prev_enrollment_year': self.prev_enrollment_year,
			'prev_college_program': self.prev_college_program,
			'prev_graduation_cert_type': self.prev_graduation_cert_type,
			'program_id': self.program_id.id if self.program_id else False,
			'academic_year_id': self.academic_year_id.id if self.academic_year_id else False,
			'admission_type': self.admission_type,
			'assigned_subject_ids': [(6, 0, self.assigned_subject_ids.ids)],
			'financial_type': self.financial_type,
			'starting_level': self.starting_level,
			'current_level': self.starting_level,
			'admission_date': fields.Date.today(),
			'ministry_form_number': self.ministry_form_number,
			'ministry_fac_code': self.ministry_fac_code,
			'ministry_university_id_code': self.ministry_university_id_code,
			'faculty_name_ar': self.faculty_name_ar,
			'university_name_ar': self.university_name_ar,
			'school_name': self.school_name,
			'gob_number': self.gob_number,
			'admission_type_text': self.admission_type_text,
			'academic_year_str': self.academic_year_str,
			'original_batch_id': batch_id,
			'batch_id': batch_id,
			'financial_clearance': False,
			'registration_status': 'unregistered',
			'registration_date': fields.Date.today(),
			'national_id_scan': self.national_id_scan,
			'photo': self.photo,
			'passport_photo': self.passport_photo,
			'national_id_photo': self.national_id_photo,
			'high_school_cert': self.high_school_cert,
			'prev_inst_cert': self.prev_inst_cert,
			'high_school_exam_number': self.high_school_exam_number,
			
			# Medical
			'blood_type': self.blood_type,
			'medical_diabetes': self.medical_diabetes,
			'medical_diabetes_drug': self.medical_diabetes_drug,
			'medical_hypertension': self.medical_hypertension,
			'medical_hypertension_drug': self.medical_hypertension_drug,
			'medical_asthma': self.medical_asthma,
			'medical_asthma_drug': self.medical_asthma_drug,
			'medical_hepatitis_b': self.medical_hepatitis_b,
			'medical_hepatitis_b_drug': self.medical_hepatitis_b_drug,
			'medical_heart_disease': self.medical_heart_disease,
			'medical_heart_disease_details': self.medical_heart_disease_details,
			'medical_physical_disability': self.medical_physical_disability,
			'medical_physical_disability_details': self.medical_physical_disability_details,
			'medical_psychiatric': self.medical_psychiatric,
			'medical_psychiatric_details': self.medical_psychiatric_details,
			'medical_other_disease': self.medical_other_disease,
			'medical_other_disease_details': self.medical_other_disease_details,
			'medical_admitted_hospital': self.medical_admitted_hospital,
			'medical_admitted_hospital_details': self.medical_admitted_hospital_details,
		}
		student = self.env['university.student'].create(vals)
		if self.guardian_ids:
			self.guardian_ids.write({'student_id': student.id})
			
		self.env['university.rfid_card'].create({
			'student_id': student.id,
			'card_uid': 'CARD-%s' % student.student_id,
			'status': 'active',
			'issue_date': fields.Date.today(),
		})
		return student

	def action_view_student(self):
		"""Return an action to open the linked student form."""
		self.ensure_one()
		if not self.student_id:
			return False
		return {
			'name': _('Student'),
			'type': 'ir.actions.act_window',
			'res_model': 'university.student',
			'view_mode': 'form',
			'res_id': self.student_id.id,
			'target': 'current',
		}
	def action_create_portal_user(self):
		"""Create a portal user for the student."""
		self.ensure_one()
		if self.phone_whatsapp and not self.is_whatsapp_verified:
			raise UserError(_("Please verify WhatsApp contact before creating a user account."))
			
		# Username: Entry Year + Univ ID
		# Using ministry_university_id_code as the 'University ID'
		username = f"{self.entry_year}{self.ministry_university_id_code or ''}"
		if not username:
			 raise UserError(_("Entry Year and University ID are required to generate a username."))

		user_obj = self.env['res.users']
		existing_user = user_obj.sudo().search([('login', '=', username)], limit=1)
		if existing_user:
			 raise UserError(_("A user with login %s already exists.") % username)

		user = user_obj.sudo().create({
			'name': self.display_name_ar or self.name_en,
			# 'name': username,
			'login': self.email,
			'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
		})
		# Note: Password is set by student via reset password or during signup
		self.message_post(body=_("Portal user created with username: %s") % username)
		return user

	def action_verify_whatsapp(self):
		"""Placeholder for WhatsApp verification logic."""
		self.ensure_one()
		self.is_whatsapp_verified = True
		self.message_post(body=_("WhatsApp contact verified."))

	def action_verify_email(self):
		"""Generate token and send Email verification link."""
		for rec in self:
			if not rec.email:
				raise UserError(_("Email address is required to send verification link."))
			if not rec.email_verification_token:
				import uuid
				rec.email_verification_token = str(uuid.uuid4())
			template = self.env.ref('university_admission.email_template_admission_verification', raise_if_not_found=False)
			if template:
				try:
					template.send_mail(rec.id, force_send=True)
					rec.message_post(body=_("Verification email sent to %s") % rec.email)
				except Exception as e:
					# Log the error but don't crash the admission submission
					import logging
					_logger = logging.getLogger(__name__)
					_logger.warning("Failed to send admission verification email to %s: %s", rec.email, str(e))
					rec.message_post(body=_("⚠ Verification email could not be sent to %s. Please send manually.") % rec.email)

	@api.model
	def action_cleanup_expired_admissions(self):
		"""Delete records that haven't been verified within the deadline."""
		from datetime import datetime
		expired = self.search([
			('state', '=', 'awaiting_verification'),
			('verification_deadline', '<', datetime.now())
		])
		if expired:
			expired.sudo().unlink()

class UniversityStudent(models.Model):
	_inherit = 'university.student'

	assigned_subject_ids = fields.Many2many(
		'university.subject',
		relation='university_student_assigned_subject_rel_inherited',
		column1='student_id',
		column2='subject_id',
		string='Assigned Subjects',
		help='Assigned explicitly during bridging/mature/transfer admission.',
		tracking=True,
	)

	def name_get(self):
		return [(rec.id, '[%s] %s' % (rec.name, rec.display_name_ar)) for rec in self]