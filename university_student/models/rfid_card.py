# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityRfidCard(models.Model):
	_name = 'university.rfid_card'
	_description = 'Student RFID Card'
	_order = 'student_id, issue_date desc'

	student_id = fields.Many2one(
		'university.student',
		string='Student',
		required=True,
		ondelete='restrict',
		index=True,
	)
	card_uid = fields.Char(
		string='Card UID',
		required=True,
		copy=False,
		index=True,
		help='Physical UID encoded on the RFID chip.',
	)
	status = fields.Selection(
		[
			('active', 'Active'),
			('blocked', 'Blocked'),
			('lost', 'Lost'),
			('expired', 'Expired'),
			('cancelled', 'Cancelled'),
		],
		string='Status',
		default='active',
		required=True,
		tracking=True,
	)
	issue_date = fields.Date(
		string='Issue Date',
		required=True,
		default=fields.Date.today,
	)
	expiry_date = fields.Date(string='Expiry Date')
	block_reason = fields.Char(
		string='Block Reason',
		help='Reason card was blocked (e.g., financial hold, lost).',
	)

	admission_id = fields.Many2one('university.admission', string="Admission Record")

	_sql_constraints = [
		('card_uid_uniq', 'unique(card_uid)', 'RFID Card UID must be unique.'),
	]

	# def action_block(self):
	# 	self.write({'status': 'blocked'})

	def action_block(self):
		return {
			'name': 'Reason for Blocking',
			'type': 'ir.actions.act_window',
			'res_model': 'university.block.wizard',
			'view_mode': 'form',
			'view_id': self.env.ref('university_student.view_university_block_wizard_form').id,
			'target': 'new',
			'context': {
				'default_rfid_card_id': self.id,
			},
		}

	def action_activate(self):
		# Only activate if student is registered
		for rec in self:
			if rec.student_id.registration_status != 'registered':
				raise ValidationError(_(
					'Cannot activate RFID card. Student "%s" must be in "Registered" status.'
				) % rec.student_id.display_name_ar)
		self.write({
			'status': 'active',
			'block_reason': False
			})

	def action_report_lost(self):
		self.write({'status': 'lost'})


class UniversityBlockWizard(models.TransientModel):
	_name = 'university.block.wizard'
	_description = 'Block Reason Wizard'

	block_reason = fields.Text(string="Reason for Blocking", required=True)
	# admission_id = fields.Many2one('university.admission', string="Admission Record")
	rfid_card_id = fields.Many2one('university.rfid_card', string="RFID Card")

	def confirm_block(self):
		if self.rfid_card_id:
			self.rfid_card_id.write({
				'status': 'blocked',
				'block_reason': self.block_reason
			})
		return {'type': 'ir.actions.act_window_close'}
