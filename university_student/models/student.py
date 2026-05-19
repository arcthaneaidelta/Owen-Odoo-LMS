# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from datetime import date



class UniversityStudentRepeatHistory(models.Model):
	_name = 'university.student.repeat.history'
	_description = 'Student Repetition History'
	
	student_id = fields.Many2one('university.student', string='Student', required=True, ondelete='cascade')
	academic_year_id = fields.Many2one('university.academic_year', string='Academic Year')
	level_repeated = fields.Char(string='Level Repeated')
	status = fields.Selection([
		('ongoing', 'Ongoing'),
		('passed', 'Passed'),
		('failed_again', 'Failed Again'),
		('passed_as_external', 'Passed as External'),
	], string='Status', default='ongoing')
	notes = fields.Text(string='Notes')


class UniversityStudent(models.Model):
	"""
	Main student model for the Sudanese University Management System.

	Ministry Excel Import Field Mapping
	====================================
	Excel Column  -> System Field
	FRMNO         -> ministry_form_number
	FAC           -> ministry_fac_code
	UNIV_ID       -> ministry_university_id_code  (numeric university code from Ministry)
	N1            -> name_part1_ar  (First name)
	N2            -> name_part2_ar  (Father's name)
	N3            -> name_part3_ar  (Grandfather's name)
	N4            -> name_part4_ar  (Family/last name)
	SCNAME        -> school_name
	GOBNO         -> gob_number
	FACNAME       -> faculty_name_ar
	GOBOLS        -> admission_type_text
	YEAR          -> academic_year_str  (e.g. '2023/2022')
	NATIONAL_ID   -> national_id
	SEX           -> gender  (1=Female based on data, check your data)
	UNIVERSITY    -> university_name_ar
	"""
	_name = 'university.student'
	_description = 'Student'
	_inherit = ['mail.thread', 'mail.activity.mixin']
	_order = 'name_part1_ar'
	_rec_name = 'display_name_ar'

	# ═══════════════════════════════════════════════════════════════════════════
	# MINISTRY IMPORT FIELDS  (match exactly to Excel columns for seamless import)
	# ═══════════════════════════════════════════════════════════════════════════

	# FRMNO - Ministry Form Number
	ministry_form_number = fields.Char(
		string='FRMNO',
		help='Ministry Form Number (FRMNO from Ministry Excel)',
		index=True,
		tracking=True,
		copy=False,
	)

	# FAC - Faculty Code (numeric code from Ministry)
	ministry_fac_code = fields.Char(
		string='FAC',
		help='Faculty Code from Ministry (FAC column)',
		index=True,
	)

	# UNIV_ID - University ID code from Ministry
	ministry_university_id_code = fields.Integer(
		string='UNIV_ID',
		help='Numeric University ID code assigned by Ministry (UNIV_ID column)',
		index=True,
	)

	# N1 - First name part (Arabic)
	name_part1_ar = fields.Char(
		string='N1 (First Name)',
		help='First part of Arabic name (N1 column)',
		required=True,
		tracking=True,
	)

	# N2 - Second name part (Father's name)
	name_part2_ar = fields.Char(
		string='N2 (Father\'s Name)',
		help='Second part of Arabic name / Father\'s name (N2 column)',
		required=True,
		tracking=True,
	)

	# N3 - Third name part (Grandfather's name)
	name_part3_ar = fields.Char(
		string='N3 (Grandfather\'s Name)',
		help='Third part of Arabic name / Grandfather\'s name (N3 column)',
		tracking=True,
	)

	# N4 - Fourth name part (Family/last name)
	name_part4_ar = fields.Char(
		string='N4 (Family Name)',
		help='Fourth part of Arabic name / Family name (N4 column)',
		tracking=True,
	)

	# SCNAME - School Name (secondary school)
	school_name = fields.Char(
		string='SCNAME (School)',
		help='Secondary school name (SCNAME column)',
	)

	# GOBNO - Governorate Number
	gob_number = fields.Integer(
		string='GOBNO',
		help='Governorate number from Ministry (GOBNO column)',
	)

	# FACNAME - Faculty Name in Arabic
	faculty_name_ar = fields.Char(
		string='FACNAME',
		help='Faculty name in Arabic as provided by Ministry (FACNAME column)',
	)

	# GOBOLS - Admission type / Governorate description
	admission_type_text = fields.Char(
		string='GOBOLS',
		help='Admission type text from Ministry (GOBOLS column, e.g. عام)',
	)

	# YEAR - Academic year string from Ministry (e.g. '2023/2022')
	academic_year_str = fields.Char(
		string='YEAR',
		help='Academic year as provided by Ministry (YEAR column, e.g. 2023/2022)',
	)

	# NATIONAL_ID - National Identification Number
	national_id = fields.Char(
		string='NATIONAL_ID',
		help='National ID number (NATIONAL_ID column)',
		index=True,
		tracking=True,
		copy=False,
	)

	# SEX - Gender from Ministry (1 or 2)
	gender_code = fields.Integer(
		string='SEX',
		help='Gender code from Ministry (SEX column). 1=Female, 2=Male (verify with your data)',
	)

	# UNIVERSITY - University name in Arabic from Ministry
	university_name_ar = fields.Char(
		string='UNIVERSITY',
		help='University name in Arabic from Ministry (UNIVERSITY column)',
	)

	# ═══════════════════════════════════════════════════════════════════════════
	# INTERNAL SYSTEM FIELDS
	# ═══════════════════════════════════════════════════════════════════════════

	# Re-Registration Portal Fields
	re_registration_token = fields.Char(string="Re-Registration Token", copy=False, readonly=True)
	re_registration_token_expiry = fields.Date(string="Re-Registration Token Expiry", copy=False, readonly=True)
	re_registration_draft_data = fields.Text(string="Re-Registration Draft Data", copy=False, help="Stores student portal progress between steps as JSON.")

	def get_re_registration_draft_data(self):
		self.ensure_one()
		import json
		try:
			return json.loads(self.re_registration_draft_data or '{}')
		except Exception:
			return {}

	def save_re_registration_draft_data(self, new_data: dict):
		self.ensure_one()
		import json
		existing = self.get_re_registration_draft_data()
		existing.update(new_data)
		self.sudo().write({'re_registration_draft_data': json.dumps(existing)})

	# Internal Student ID (auto-generated sequence)
	student_id = fields.Char(
		string='Internal Student ID',
		readonly=True,
		copy=False,
		default='New',
		index=True,
	)

	# Ministry-issued University Number (immutable once set)
	# ministry_university_number = fields.Char(
	# 	string='Ministry University Number',
	# 	copy=False,
	# 	index=True,
	# 	tracking=True,
	# 	help='University number officially assigned by the Ministry after approval.',
	# )

	# Full Arabic display name (computed from parts)
	display_name_ar = fields.Char(
		string='Full Arabic Name',
		compute='_compute_display_name_ar',
		store=True,
	)

	# English name fields
	name_en = fields.Char(string='Name (English)', tracking=True)

	# Gender selection (user-friendly, synced from gender_code on import)
	gender = fields.Selection(
		[('male', 'Male'), ('female', 'Female')],
		string='Gender',
		tracking=True,
	)

	date_of_birth = fields.Date(string='Date of Birth', tracking=True)
	place_of_birth = fields.Char(string='Place of Birth', translate=True)

	# ─── Academic Placement ───────────────────────────────────────────────────
	program_id = fields.Many2one(
		'university.program',
		string='Program',
		tracking=True,
	)
	college_id = fields.Many2one(
		'university.college',
		string='College',
		related='program_id.college_id',
		store=True,
		readonly=True,
	)
	university_id = fields.Many2one(
		'university.university',
		string='University',
		related='program_id.university_id',
		store=True,
		readonly=True,
	)
	specialization_id = fields.Many2one(
		'university.specialization',
		string='Specialization',
		domain="[('program_id', '=', program_id)]",
		tracking=True,
	)
	batch_id = fields.Many2one(
		'university.batch',
		string='Current Batch',
		domain="[('program_id', '=', program_id), ('state', '=', 'active')]",
		tracking=True,
	)
	original_batch_id = fields.Many2one(
		'university.batch',
		string='Original Batch',
		tracking=True,
		help='Batch assigned upon admission. Current Batch may differ due to repetition/freezing.'
	)
	academic_year_id = fields.Many2one(
		'university.academic_year',
		string='Academic Year',
		domain="[('state', '=', 'active')]",
		tracking=True,
	)

	@api.onchange('program_id')
	def _onchange_program_id(self):
		if self.program_id:
			# Auto-select active batch for UI feedback
			active_batch = self.env['university.batch'].search([
				('program_id', '=', self.program_id.id),
				('state', '=', 'active')
			], limit=1)
			self.batch_id = active_batch
		else:
			self.batch_id = False

	# def write(self, vals):
	# 	res = super().write(vals)
	# 	# If program changes, sync the linked personal curriculum
	# 	if 'program_id' in vals:
	# 		new_program = self.env['university.program'].browse(vals['program_id'])
	# 		print(new_program.name)
	# 		print('1111111111111111111111111111111111')
	# 		for rec in self:
	# 			student_curricula = self.env['university.curriculum'].search([
	# 				('student_id', '=', rec.id)
	# 			])
	# 			if student_curricula:
	# 				print('2222222222222222222222222222222')
	# 				# Temporarily unlock to allow program/subject changes if locked
	# 				locked_curricula = student_curricula.filtered(lambda c: c.is_locked)
	# 				if locked_curricula:
	# 					locked_curricula.sudo().write({'is_locked': False})

	# 				# Clear lines and update program/name in one step
	# 				student_curricula.sudo().write({
	# 					'program_id': new_program.id,
	# 					'name': f"Personal Curriculum - {rec.display_name_ar or rec.name_en} ({new_program.name})",
	# 					'line_ids': [(5, 0, 0)]
	# 				})
	# 				# Re-populate subjects from the new program
	# 				for curriculum in student_curricula:
	# 					curriculum.sudo()._populate_subjects_from_program()
					
	# 				# Restore lock state
	# 				if locked_curricula:
	# 					locked_curricula.sudo().write({'is_locked': True})
	# 	return res

	# @api.onchange('batch_id')
	# def _onchange_batch_sync_year(self):
	# 	"""Sync academic year from batch when batch changes."""
	# 	if self.batch_id and self.batch_id.academic_year_id:
	# 		self.academic_year_id = self.batch_id.academic_year_id

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			# Auto-set Original Batch to same as Current Batch on creation
			if vals.get('batch_id') and not vals.get('original_batch_id'):
				vals['original_batch_id'] = vals['batch_id']
		return super().create(vals_list)

	# ─── Admission Info ───────────────────────────────────────────────────────
	admission_type = fields.Selection(
		[
			('regular', 'Regular Admission'),
			('bridging', 'Bridging'),
			('mature', 'Mature'),
			('transfer', 'Transfer'),
		],
		string='Admission Type',
		default='regular',
		tracking=True,
	)
	financial_type = fields.Selection(
		[
			('citizen', 'Sudanese Citizen'),
			('foreigner', 'Foreigner'),
		],
		string='Financial Type',
		default='citizen',
		tracking=True,
	)
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
		tracking=True,
	)
	current_level = fields.Selection(
		[
			('1', 'Level 1'),
			('2', 'Level 2'),
			('3', 'Level 3'),
			('4', 'Level 4'),
			('5', 'Level 5'),
			('6', 'Level 6'),
		],
		string='Current Level',
		tracking=True,
		default='1',
	)
	admission_date = fields.Date(string='Admission Date', tracking=True)
	is_repeater = fields.Boolean(
		string='Repeater',
		default=False,
		tracking=True,
		help='When True, student is a repeater. Triggers fee adjustment and batch reassignment.',
	)
	repeat_history_ids = fields.One2many(
		'university.student.repeat.history',
		'student_id',
		string='Repetition History',
	)
	total_repeat_years = fields.Integer(
		string='Total Repeat Years',
		compute='_compute_total_repeat_years',
		store=True,
	)
	
	@api.depends('repeat_history_ids', 'repeat_history_ids.status')
	def _compute_total_repeat_years(self):
		for rec in self:
			rec.total_repeat_years = len(rec.repeat_history_ids.filtered(lambda h: h.status != 'discarded'))


	# ─── Academic Standing ────────────────────────────────────────────────────
	academic_standing = fields.Selection(
		[
			('good_standing', 'Good Standing'),
			('frozen', 'Frozen'),
			('warning', 'Warning'),
			('probation', 'Probation'),
			('suspended', 'Suspended'),
			('expelled', 'Expelled'),
			('graduated', 'Graduated'),
			('withdrawn', 'Withdrawn'),
		],
		string='Academic Standing',
		default='good_standing',
		tracking=True,
	)

	# ─── Registration ─────────────────────────────────────────────────────────
	registration_status = fields.Selection(
		[
			('registered', 'Registered'),
			('unregistered', 'Unregistered'),
		],
		string='Registration Status',
		compute='_compute_registration_status',
		store=True,
		tracking=True,
	)
	
	registration_invoice_id = fields.Many2one('account.move', string='Registration Invoice', readonly=True, copy=False)
	tuition_invoice_id = fields.Many2one('account.move', string='Tuition Invoice', readonly=True, copy=False)

	is_id_and_exam_eligible = fields.Boolean(
		string='ID & Exam Eligible',
		compute='_compute_student_milestones',
		store=True,
		help='Unlocked when at least 50% of Tuition Fee is paid.'
	)
	is_second_semester_eligible = fields.Boolean(
		string='2nd Semester Eligible',
		compute='_compute_student_milestones',
		store=True,
		help='Unlocked when both Registration and Tuition Invoices are fully paid.'
	)

	@api.depends('registration_invoice_id', 'registration_invoice_id.payment_state')
	def _compute_registration_status(self):
		for rec in self:
			if rec.registration_invoice_id and rec.registration_invoice_id.payment_state in ['paid', 'in_payment']:
				rec.registration_status = 'registered'
			else:
				rec.registration_status = 'unregistered'
				
				# Auto-block any active RFID cards
				if rec.id:
					active_cards = self.env['university.rfid_card'].search([
						('student_id', '=', rec.id),
						('status', '=', 'active')
					])
					if active_cards:
						active_cards.write({
							'status': 'blocked',
							'block_reason': 'System: Student is unregistered.'
						})

	@api.depends('tuition_invoice_id', 'tuition_invoice_id.amount_residual', 'tuition_invoice_id.amount_total', 'registration_invoice_id.payment_state', 'tuition_invoice_id.payment_state')
	def _compute_student_milestones(self):
		for rec in self:
			if rec.tuition_invoice_id and rec.tuition_invoice_id.amount_total > 0:
				paid_amt = rec.tuition_invoice_id.amount_total - rec.tuition_invoice_id.amount_residual
				half_tuition = rec.tuition_invoice_id.amount_total / 2.0
				rec.is_id_and_exam_eligible = (paid_amt >= half_tuition)
			else:
				rec.is_id_and_exam_eligible = (rec.registration_status == 'registered')

			reg_paid = rec.registration_invoice_id and rec.registration_invoice_id.payment_state in ['paid', 'in_payment']
			tui_paid = rec.tuition_invoice_id and rec.tuition_invoice_id.payment_state in ['paid', 'in_payment']
			
			if not rec.registration_invoice_id or not rec.tuition_invoice_id:
				rec.is_second_semester_eligible = False
				rec.financial_clearance = False
			else:
				rec.is_second_semester_eligible = (reg_paid and tui_paid)
				rec.financial_clearance = (reg_paid and tui_paid)

	registration_date = fields.Date(string='Registration Date')

	financial_clearance = fields.Boolean(
		string='Financial Clearance',
		compute='_compute_student_milestones',
		store=True,
		tracking=True,
		help='Auto-set to True when Registration and Tuition fees are fully paid.',
	)

	# ─── Contact Info ─────────────────────────────────────────────────────────
	# Primary phone (current active number)
	phone = fields.Char(string='Primary Phone', tracking=True)
	phone_country_id = fields.Many2one('res.country', string='Phone Country Code')
	phone_whatsapp = fields.Char(string='WhatsApp Number')
	whatsapp_country_id = fields.Many2one('res.country', string='WhatsApp Country Code')
	email = fields.Char(string='Email', tracking=True)

	# Phone history (never overwrite policy)
	phone_history_ids = fields.One2many(
		'university.student.phone',
		'student_id',
		string='Phone History',
	)

	# ─── Guardian ─────────────────────────────────────────────────────────────
	guardian_ids = fields.One2many(
		'university.guardian',
		'student_id',
		string='Guardians',
	)

	# ─── RFID ─────────────────────────────────────────────────────────────────
	rfid_card_ids = fields.One2many(
		'university.rfid_card',
		'student_id',
		string='RFID Cards',
	)
	active_rfid_card_id = fields.Many2one(
		'university.rfid_card',
		string='Active RFID Card',
		compute='_compute_active_rfid',
		store=True,
	)

	# ─── Portal ───────────────────────────────────────────────────────────────
	partner_id = fields.Many2one(
		'res.partner',
		string='Contact (Portal)',
		copy=False,
		help='Linked res.partner record for portal access.',
	)

	# ─── Nationality / Address ────────────────────────────────────────────────
	nationality_id = fields.Many2one(
		'res.country',
		string='Nationality',
	)
	student_nationality = fields.Char(string='Student Nationality', tracking=True)
	passport_number = fields.Char(string='Passport Number', tracking=True)
	id_document_number = fields.Char(string='ID Document Number', tracking=True)
	country_of_birth = fields.Char(string='Country of Birth (Legacy)')
	country_of_birth_id = fields.Many2one('res.country', string='Country of Birth')
	religion = fields.Char(string='Religion')
	city_of_residence = fields.Char(string='City of Residence')
	residence_country_id = fields.Many2one('res.country', string='Country of Residence')
	governorate = fields.Char(string='Governorate / State', translate=True)
	locality = fields.Char(string='Locality', translate=True)
	address = fields.Text(string='Address', translate=True)
	citizenship = fields.Selection(
		[('citizen', 'Citizen'), ('foreigner', 'Foreigner')],
		string='Citizenship'
	)

	# ─── Certificate Info ──────────────────────────────────────────────────────
	certificate_type = fields.Char(string='Certificate Type')
	high_school_grade = fields.Float(string='High School Grade %')
	high_school_name = fields.Char(string='High School Name')
	high_school_exam_number = fields.Char(string='High School Exam Number')

	# ─── Previous Institution ──────────────────────────────────────────────────
	prev_institution_name = fields.Char(string='Previous Institution Name')
	prev_years_completed = fields.Integer(string='Years Completed')
	prev_enrollment_year = fields.Integer(string='Enrollment Year')
	prev_college_program = fields.Char(string='College / Program / Major')
	prev_graduation_cert_type = fields.Char(string='Graduation Certificate Type')
	prev_inst_cert = fields.Binary(string='Previous Institution Certificate', attachment=True)

	# ─── Documents ────────────────────────────────────────────────────────────
	national_id_scan = fields.Binary(string='National ID Scan', attachment=True)
	photo = fields.Binary(string='Student Photo', attachment=True)
	passport_photo = fields.Binary(string='Passport Photo', attachment=True)
	national_id_photo = fields.Binary(string='National ID Photo', attachment=True)
	high_school_cert = fields.Binary(string='High School Certificate', attachment=True)
	photo_filename = fields.Char(string='Photo Filename')
	google_drive_folder_url = fields.Char(string='Google Drive Folder URL')

	# ─── Medical History ──────────────────────────────────────────────────────
	blood_type = fields.Selection([
		('A+', 'A+'), ('A-', 'A-'),
		('B+', 'B+'), ('B-', 'B-'),
		('AB+', 'AB+'), ('AB-', 'AB-'),
		('O+', 'O+'), ('O-', 'O-')
	], string='Blood Type', tracking=True)
	# Section A: Chronic Diseases
	medical_diabetes = fields.Boolean(string='Diabetes Mellitus', tracking=True)
	medical_diabetes_drug = fields.Char(string='Type of Drug (Diabetes)', tracking=True)
	medical_hypertension = fields.Boolean(string='Hypertension', tracking=True)
	medical_hypertension_drug = fields.Char(string='Type of Drug (Hypertension)', tracking=True)
	medical_asthma = fields.Boolean(string='Bronchial Asthma', tracking=True)
	medical_asthma_drug = fields.Char(string='Type of Drug (Asthma)', tracking=True)
	medical_hepatitis_b = fields.Boolean(string='Hepatitis B', tracking=True)
	medical_hepatitis_b_drug = fields.Char(string='Type of Drug (Hepatitis B)', tracking=True)
	
	# Section B: Other Diseases
	medical_heart_disease = fields.Boolean(string='Heart Disease', tracking=True)
	medical_heart_disease_details = fields.Char(string='Determine (Heart Disease)', tracking=True)
	medical_physical_disability = fields.Boolean(string='Physical Disability', tracking=True)
	medical_physical_disability_details = fields.Char(string='Determine (Physical Disability)', tracking=True)
	medical_psychiatric = fields.Boolean(string='Psychiatric Disease', tracking=True)
	medical_psychiatric_details = fields.Char(string='Determine (Psychiatric)', tracking=True)
	medical_other_disease = fields.Boolean(string='Any Other Disease', tracking=True)
	medical_other_disease_details = fields.Char(string='Determine (Other Disease)', tracking=True)

	# Section C: Hospitalization
	medical_admitted_hospital = fields.Boolean(string='Admitted in hospital before?', tracking=True)
	medical_admitted_hospital_details = fields.Char(string='Explain (Hospitalization)', tracking=True)

	# ─── Notes ────────────────────────────────────────────────────────────────
	notes = fields.Text(string='Notes', translate=True)
	active = fields.Boolean(default=True)

	# ═══════════════════════════════════════════════════════════════════════════
	# SQL CONSTRAINTS
	# ═══════════════════════════════════════════════════════════════════════════
	_sql_constraints = [
		(
			'national_id_uniq',
			'unique(national_id)',
			'A student with this National ID already exists.',
		),
		(
			'ministry_form_number_uniq',
			'unique(ministry_form_number)',
			'A student with this Ministry Form Number (FRMNO) already exists.',
		),
		(
			'student_id_uniq',
			'unique(student_id)',
			'Internal Student ID must be unique.',
		),
	]

	# ═══════════════════════════════════════════════════════════════════════════
	# COMPUTES
	# ═══════════════════════════════════════════════════════════════════════════

	def action_promote(self):
		"""Promote the student to the next academic level."""
		for rec in self:
			# if not rec.financial_clearance:
			# 	raise ValidationError(_('Student cannot be promoted until Registration and Tuition fees are fully paid (Financial Clearance required).'))
				
			if not rec.current_level:
				rec.current_level = '1'
				continue
				
			current = int(rec.current_level)
			duration = rec.program_id.duration_years or 4
			
			if current < duration:
				rec.current_level = str(current + 1)
				rec.message_post(body=_("Student promoted to Level %s") % rec.current_level)
			else:
				# Reached final year
				rec.academic_standing = 'graduated'
				rec.message_post(body=_("Student has completed the program and is marked as Graduated."))

	def action_expel(self):
		"""Expel the student and archive their file."""
		for rec in self:
			rec.academic_standing = 'expelled'
			rec.active = False  # Archive the record
			rec.message_post(body=_("Student has been expelled and their file archived."))
			# Block all RFID cards
			rec.rfid_card_ids.filtered(lambda c: c.status == 'active').write({
				'status': 'blocked',
				'block_reason': 'System: Student expelled.'
			})

	def _compute_display_name_ar(self):
		for rec in self:
			parts = [
				rec.name_part1_ar or '',
				rec.name_part2_ar or '',
				rec.name_part3_ar or '',
				rec.name_part4_ar or '',
			]
			rec.display_name_ar = ' '.join(p for p in parts if p.strip())

	@api.depends('rfid_card_ids', 'rfid_card_ids.status')
	def _compute_active_rfid(self):
		for rec in self:
			active = rec.rfid_card_ids.filtered(lambda c: c.status == 'active')
			rec.active_rfid_card_id = active[:1] if active else False

	# ═══════════════════════════════════════════════════════════════════════════
	# SEQUENCE AUTO-ASSIGN
	# ═══════════════════════════════════════════════════════════════════════════

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if vals.get('student_id', 'New') == 'New':
				program = self.env['university.program'].browse(vals.get('program_id')) if vals.get('program_id') else None
				batch = self.env['university.batch'].browse(vals.get('batch_id')) if vals.get('batch_id') else None
				academic_year = self.env['university.academic_year'].browse(vals.get('academic_year_id')) if vals.get('academic_year_id') else None
				
				prog_prefix = (program.code or 'PRG')[:3].upper().ljust(3, 'X') if program else 'XXX'
				
				year_val = '00'
				if academic_year and academic_year.name:
					import re
					match = re.search(r'\d{4}', str(academic_year.name))
					if match:
						matched_str = str(match.group(0))
						year_val = f"{int(matched_str) % 100:02d}"
				
				batch_num = batch.batch_number if batch and batch.batch_number else 'B000'
				
				univ = program.university_id if program else None
				univ_id = (univ.code or 'UNV').upper() if univ else 'UNV'
				
				if batch:
					seq_code = f'university.student.batch.{batch.id}'
					sequence = self.env['ir.sequence'].search([('code', '=', seq_code)], limit=1)
					if not sequence:
						sequence = self.env['ir.sequence'].sudo().create({
							'name': f'Student Sequence Batch {batch.id}',
							'code': seq_code,
							'prefix': '',
							'padding': 3,
							'company_id': False,
						})
					seq_num = sequence.next_by_id()
					seq_str = f'S{seq_num}'
				else:
					# Fallback generic sequence if no batch
					fallback_seq = self.env['ir.sequence'].search([('code', '=', 'university.student.fallback')], limit=1)
					if not fallback_seq:
						fallback_seq = self.env['ir.sequence'].sudo().create({
							'name': 'Student Fallback Sequence',
							'code': 'university.student.fallback',
							'prefix': '',
							'padding': 3,
							'company_id': False,
						})
					seq_num = fallback_seq.next_by_id()
					seq_str = f'S{seq_num}'
				
				vals['student_id'] = f"{prog_prefix}{year_val}{batch_num}{univ_id}{seq_str}"

			# Sync gender from gender_code if provided
			if 'gender_code' in vals and not vals.get('gender'):
				code = vals.get('gender_code')
				if code == 1:
					vals['gender'] = 'female'
				elif code == 2:
					vals['gender'] = 'male'
		return super().create(vals_list)

	# ═══════════════════════════════════════════════════════════════════════════
	# CONSTRAINTS
	# ═══════════════════════════════════════════════════════════════════════════

	# @api.constrains('ministry_university_number')
	# def _check_ministry_university_number_unique(self):
	# 	for rec in self:
	# 		if rec.ministry_university_number:
	# 			duplicate = self.search([
	# 				('ministry_university_number', '=', rec.ministry_university_number),
	# 				('id', '!=', rec.id),
	# 			])
	# 			if duplicate:
	# 				raise ValidationError(_(
	# 					'Ministry University Number "%s" is already assigned to another student.'
	# 				) % rec.ministry_university_number)

	# ═══════════════════════════════════════════════════════════════════════════
	# FINANCIAL CLEARANCE WATCHER
	# ═══════════════════════════════════════════════════════════════════════════

	def write(self, vals):
		result = super().write(vals)
		
		# ── Program change: sync personal curriculum ──────────────────────────
		if 'program_id' in vals:
			new_program = self.env['university.program'].browse(vals['program_id'])
			for rec in self:
				student_curricula = self.env['university.curriculum'].search([
					('student_id', '=', rec.id)
				])
				if student_curricula:
					locked_curricula = student_curricula.filtered(lambda c: c.is_locked)
					if locked_curricula:
						locked_curricula.sudo().write({'is_locked': False})

					student_curricula.sudo().write({
						'program_id': new_program.id,
						'name': f"Personal Curriculum - {rec.display_name_ar or rec.name_en} ({new_program.name})",
						'line_ids': [(5, 0, 0)]
					})
					for curriculum in student_curricula:
						curriculum.sudo()._populate_subjects_from_program()

					if locked_curricula:
						locked_curricula.sudo().write({'is_locked': True})

		# ── Financial clearance: sync RFID cards ─────────────────────────────
		if 'financial_clearance' in vals:
			for rec in self:
				if not rec.financial_clearance:
					rec.rfid_card_ids.filtered(
						lambda c: c.status == 'active'
					).write({'status': 'blocked'})
					rec.message_post(
						body=_('Financial clearance revoked. RFID card(s) blocked automatically.')
					)
				else:
					rec.rfid_card_ids.filtered(
						lambda c: c.status == 'blocked'
					).write({'status': 'active'})
					rec.message_post(
						body=_('Financial clearance granted. RFID card(s) re-activated.')
					)

		return result

	# ═══════════════════════════════════════════════════════════════════════════
	# DISPLAY NAME
	# ═══════════════════════════════════════════════════════════════════════════

	def name_get(self):
		result = []
		for rec in self:
			name = rec.display_name_ar or rec.name_en or ''
			if rec.student_id and rec.student_id != 'New':
				name = f'[{rec.student_id}] {name}'
			result.append((rec.id, name))
		return result
