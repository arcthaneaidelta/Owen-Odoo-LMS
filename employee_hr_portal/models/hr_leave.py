# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

from odoo.http import request
from odoo import api, fields, models, _
from psycopg2 import errorcodes
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
import uuid
from datetime import datetime, time, timedelta
from collections import defaultdict

class HolidaysEmployeeCalendar(models.Model):
	_inherit = 'resource.calendar'

	def _get_resources_day_total(self, from_datetime, to_datetime, resources=None):
		"""
		@return dict with hours of attendance in each day between `from_datetime` and `to_datetime`
		"""
		self.ensure_one()
		if not resources:
			resources = self.env['resource.resource']
			resources_list = [resources]
		else:
			resources_list = list(resources) + [self.env['resource.resource']]
		# total hours per day:  retrieve attendances with one extra day margin,
		# in order to compute the total hours on the first and last days
		from_full = from_datetime
		to_full = to_datetime
		intervals = self._attendance_intervals_batch(from_full, to_full, resources=resources)

		result = defaultdict(lambda: defaultdict(float))
		for resource in resources_list:
			day_total = result[resource.id]
			for start, stop, meta in intervals[resource.id]:
				day_total[start.date()] += (stop - start).total_seconds() / 3600
		return result

class HolidaysEmployee(models.Model):
	_inherit = 'hr.employee'

	allow_loan_request = fields.Boolean(string='Allow Loan Request', tracking=True, copy=False)
	pension_eligible = fields.Boolean(string="Pension Eligible")
	show_overtime_requests = fields.Boolean(string="Allow Over Time ", default=False)
	allow_checkin_checkout = fields.Boolean(
		string='Allow Portal Check-in/Check-out',
		default=False,
		help="Enable employee portal check-in/check-out"
	)

	def action_create_user_portal(self):
		self.ensure_one()
		if self.user_id:
			if self.user_id.has_group('base.group_portal'):
				if self.user_id.has_group('employee_hr_portal.access_to_allow_portal_group_access'):
					raise ValidationError('This Employee already has a user with portal level access!')

			group_portal = self.env.ref('base.group_portal')
			group_portal_leaves = self.env.ref('employee_hr_portal.access_to_allow_portal_group_access')
			group_portal_user = self.env.ref('employee_hr_portal.access_to_employee_portal_custom_user')
			return {
				'name': _('Grant Only Portal Access'),
				'type': 'ir.actions.act_window',
				'res_model': 'employee.present.user.portal',
				'view_mode': 'form',
				'view_id': self.env.ref('employee_hr_portal.employee_wizard_view').id,
				'target': 'new',
				'context': {
					'default_create_employee_id': self.id,
					'default_user_id': self.user_id.id,
					'default_groups_id': [(6, 0, [group_portal.id, group_portal_leaves.id, group_portal_user.id])]
				}
			}
		else:
			group_portal = self.env.ref('base.group_portal')
			group_portal_leaves = self.env.ref('employee_hr_portal.access_to_allow_portal_group_access')
			group_portal_user = self.env.ref('employee_hr_portal.access_to_employee_portal_custom_user')
			return {
				'name': _('Grant Only Portal Access'),
				'type': 'ir.actions.act_window',
				'res_model': 'res.users',
				'view_mode': 'form',
				'view_id': self.env.ref('hr.view_users_simple_form').id,
				'target': 'new',
				'context': {
					'default_create_employee_id': self.id,
					'default_name': self.name,
					'default_phone': self.work_phone,
					'default_mobile': self.mobile_phone,
					'default_login': self.work_email,
					'default_groups_id': [(6, 0, [group_portal.id, group_portal_leaves.id, group_portal_user.id])]
				}
			}


# class Holidaysatypes(models.Model):
# 	_inherit = 'hr.leave.type'

# 	# YTI TODO: Remove me in master
# 	def get_days(self, employee_id):
# 		return self.get_employees_days([employee_id])[employee_id]


class HolidaysRequest(models.Model):
	_inherit = 'hr.leave'

	is_medical_leave = fields.Boolean(
		string="Is Medical Leave",
		compute="_compute_is_medical_leave",
		store=False
	)

	@api.depends('holiday_status_id')
	def _compute_is_medical_leave(self):
		for rec in self:
			rec.is_medical_leave = rec.holiday_status_id.name == "Medical Leave"

	# def action_approve(self):
	# 	res = super(HolidaysRequest, self).action_approve()
	# 	for leave in self:
	# 		if leave.is_medical_leave and not leave.supported_attachment_ids:
	# 			raise ValidationError(
	# 				"Please attach a medical certificate before approving this medical leave."
	# 			)
	# 	return res
		
	def _leave_get_portal_domain(self):
		employee_id = self.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
		return [
			'|', '|', ('employee_id.user_id', '=', request.env.uid), ('employee_id.parent_id', 'child_of', [employee_id.id]),
			'|', '|', ('department_id', '=', False), ('department_id.member_ids.user_id', 'in', [request.env.uid]),
			('department_id.manager_id.user_id', '=', request.env.uid),
			'|', ('message_partner_ids', 'child_of', [request.env.user.partner_id.commercial_partner_id.id]),
			('employee_id.parent_id', 'child_of', [employee_id.id])
		]

	def _compute_access_url(self):
		super(HolidaysRequest, self)._compute_access_url()
		for leave in self:
			leave.access_url = '/my/leave/%s' % leave.id

	def error_msg(self, msg):
		if msg:
			if not (isinstance(msg, AttributeError) or isinstance(msg, ValidationError) or isinstance(msg, MissingError)
					or isinstance(msg, UserError) or isinstance(msg, AccessError)):
				if msg.pgcode in (errorcodes.CHECK_VIOLATION,):
					msg = _('The start date must be anterior to the end date.')
					return msg
				elif msg.pgcode in (errorcodes.NOT_NULL_VIOLATION, errorcodes.FOREIGN_KEY_VIOLATION, errorcodes.RESTRICT_VIOLATION):
					msg = _('The operation cannot be completed, probably due to the value')
					return msg
				return msg.pgerror or msg.name
			return msg

	@api.model
	def create(self, vals):
		record = super(HolidaysRequest, self).create(vals)
		for leave in self:
			if leave.is_medical_leave and not leave.supported_attachment_ids:
				raise ValidationError(
					"Please attach a medical certificate before approving this medical leave."
				)
		if record and record.employee_id.parent_id:
			if record and record.employee_id.parent_id.work_email:
				try:
					for x in record:
						subject = _("(%(data)s) Has Requested New Leave (%(data2)s)") % {
							'data': x.sudo().employee_id.name,
							'data2': x.sudo().name
						}
						body_html = self.env['ir.qweb']._render(
							'portal_users_leaves_holidays.leave_create_send_email_ext',
							{"data": x.sudo(), "company": self.env.company}
						)
						msg = self.env["mail.message"].sudo().new(dict(body=body_html, record_name=self.env.company.name))
						full_mail = self.env["mail.render.mixin"]._render_encapsulate(
							"mail.mail_notification_light",
							body_html,
							add_context=dict(message=msg, model_description=_("New Website Order")),
						)
						mail_values = {
							"subject": subject,
							"email_from": x.sudo().employee_id.work_email,
							"email_to": x.employee_id.parent_id.work_email,
							"body_html": full_mail,
						}
						mail = self.env["mail.mail"].sudo().create(mail_values)
						mail.sudo().send(raise_exception=False)
				except Exception:
					pass
		if 'supported_attachment_ids' in vals:
			for rec in record:
				if rec.supported_attachment_ids:
					rec.get_access_token_attachment_leave_website()
		return record

	def get_access_token_attachment_leave_website(self):
		for x in self:
			for documents in x.supported_attachment_ids:
				url = self.get_portal_url_website_document_leave()
				sql = "UPDATE ir_attachment SET access_token = '%s' WHERE id = '%s' " % (
					url, str(documents[0]._origin.id)
				)
				try:
					self._cr.execute(sql)
					self._cr.commit()
				except Exception:
					pass

	def write(self, vals):
		res = super(HolidaysRequest, self).write(vals)
		if 'supported_attachment_ids' in vals:
			for rec in self:
				if rec.supported_attachment_ids:
					rec.get_access_token_attachment_leave_website()
		return res

	def _portal_ensure_token_website_document(self):
		return str(uuid.uuid4())

	def get_portal_url_website_document_leave(
		self, suffix=None, report_type=None, download=None, query_string=None, anchor=None
	):
		url = '%s%s%s%s%s' % (
			self._portal_ensure_token_website_document(),
			'&report_type=%s' % report_type if report_type else '',
			'&download=true' if download else '',
			query_string if query_string else '',
			'#%s' % anchor if anchor else ''
		)
		return url
