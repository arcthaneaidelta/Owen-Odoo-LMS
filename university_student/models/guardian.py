# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityGuardian(models.Model):
	_name = 'university.guardian'
	_description = 'Student Guardian'
	_order = 'id'

	student_id = fields.Many2one(
		'university.student',
		string='Student',
		ondelete='cascade',
	)

	name = fields.Char(
		string='Guardian Name',
		required=True,
		translate=True,
	)
	relationship = fields.Selection(
		[
			('father', 'Father'),
			('mother', 'Mother'),
			('brother', 'Brother'),
			('sister', 'Sister'),
			('uncle', 'Uncle'),
			('aunt', 'Aunt'),
			('grandfather', 'Grandfather'),
			('grandmother', 'Grandmother'),
			('guardian', 'Legal Guardian'),
			('other', 'Other'),
		],
		string='Relationship',
		required=True,
	)
	phone_1 = fields.Char(string='Phone 1', required=True)
	phone_1_country_id = fields.Many2one('res.country', string='Phone Country Code')
	phone_whatsapp = fields.Char(string='WhatsApp')
	whatsapp_country_id = fields.Many2one('res.country', string='WhatsApp Country Code')
	phone_2 = fields.Char(string='Phone 2')
	email = fields.Char(string='Email')
	national_id = fields.Char(string='National ID')
	address = fields.Text(string='Address', translate=True)
	is_emergency_contact = fields.Boolean(
		string='Emergency Contact',
		default=False,
		help='Exactly one guardian must be marked as emergency contact.',
	)
	notes = fields.Text(string='Notes', translate=True)

	@api.constrains('is_emergency_contact', 'student_id', 'admission_id')
	def _check_emergency_contact(self):
		for rec in self.filtered(lambda r: r.is_emergency_contact):

			domain = [
				('id', '!=', rec.id),
				('is_emergency_contact', '=', True)
			]

			if rec.student_id:
				domain.append(('student_id', '=', rec.student_id.id))
			elif rec.admission_id:
				domain.append(('admission_id', '=', rec.admission_id.id))
			else:
				continue

			others = self.search(domain)

			if others:
				raise ValidationError(_(
					'Only one guardian can be marked as emergency contact.'
				))
