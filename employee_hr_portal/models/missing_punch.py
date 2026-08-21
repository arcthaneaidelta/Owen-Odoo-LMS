from odoo import models, fields, api, exceptions, _
from odoo.exceptions import ValidationError, AccessError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
	_inherit = 'hr.employee'

	missing_punch_approver_id = fields.Many2one('hr.employee', string='Missing Punch Approver')


class MissingPunch(models.Model):
	_name = "missing.punch"
	_description = "Missing Punch Records"
	_rec_name = 'employee_id'
	_inherit = ['mail.thread', 'mail.activity.mixin']

	company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, copy=False,
								 tracking=True)
	user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user, tracking=True,
							  copy=False)
	employee_id = fields.Many2one('hr.employee', string='Employee', tracking=True, copy=False)
	punch_datetime = fields.Datetime(string='Date/Time', tracking=True, copy=False)
	punch_type = fields.Selection([
		('check_in', 'Check In'),
		('check_out', 'Check Out'),
		('break_in', 'Break In'),
		('break_out', 'Break Out'),
	], string='Punch Type', tracking=True, copy=False, required=True)

	break_slot = fields.Selection([
		('1', 'Break 1'),
		('2', 'Break 2')
	], string="Select Break Slot", tracking=True)
	reason = fields.Text(string='Reason/Description')
	state = fields.Selection([
		('new', 'New'),
		('approve', 'Approved'),
		('attendance_created', 'Attendance Created'),
		('refuse', 'Refused'),
		('cancel', 'Cancelled')
	], default='new', tracking=True)

	attendance_id = fields.Many2one('hr.attendance', string='Created Attendance', readonly=True)
	break_id = fields.Many2one('employee.break', string="Break Record", readonly=True)



	@api.model
	def search(self, args=None, offset=0, limit=None, order=None):
		current_user = self.env.user
		domain = []
		if not current_user.has_group('employee_hr_portal.group_show_all_missing_punch'):
			domain = ['|',
				('employee_id.user_id', '=', current_user.id),
				('employee_id.missing_punch_approver_id.user_id', '=', current_user.id)
			]
		if args:
			domain = ['&'] + domain + args if domain else args
		return super(MissingPunch,self).search(domain, offset=offset, limit=limit, order=order)

	def _delete_created_attendance(self):
		"""Delete attendance record if it was created by this missing punch request"""
		for rec in self:
			if rec.attendance_id:
				# Delete the attendance record
				rec.attendance_id.sudo().unlink()
				rec.attendance_id = False

				punch_date = (rec.punch_datetime + timedelta(hours=5)).date()

	def action_reset(self):
		for rec in self:
			if rec.state in ['attendance_created'] and rec.attendance_id:
				rec._delete_created_attendance()
			rec.state = 'new'

	def action_approve(self):
		"""Approve the missing punch request, ensuring only the designated approver can approve."""
		for rec in self:
			current_employee = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.uid)], limit=1)
			if not current_employee:
				raise AccessError(
					"No employee record found for the current user. Please ensure your user is linked to an employee.")

			employee = rec.employee_id.sudo()
			if employee.missing_punch_approver_id:
				if not self.env.user.has_group('employee_hr_portal.show_all_missing_punch_approve'):
					if current_employee.id != employee.missing_punch_approver_id.id:
						raise AccessError("Only the designated approver can approve this request.")

			rec.state = 'approve'


	def action_refuse(self):
		for rec in self:
			current_employee = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.uid)], limit=1)

			employee = rec.employee_id.sudo()

			if employee.missing_punch_approver_id:
				if current_employee.id != employee.missing_punch_approver_id.id:
					raise AccessError("Only the designated approver can refuse this request.")

			if rec.state in ['attendance_created'] and rec.attendance_id:
				rec._delete_created_attendance()

			rec.state = 'refuse'
	def action_cancel(self):
		for rec in self:
			# If attendance was created and we're cancelling, delete the attendance
			if rec.state in ['attendance_created'] and rec.attendance_id:
				rec._delete_created_attendance()

			rec.state = 'cancel'


	def action_attendance_created(self):
		for rec in self:
			employee = rec.employee_id.sudo()

			if not employee.contract_id:
				raise ValidationError(_('Employee has no valid or running contract!'))

			punch_date = rec.punch_datetime.date()
			punch_datetime = rec.punch_datetime

			if rec.punch_type in ['break_in', 'break_out']:

				punch_datetime = punch_datetime

				attendance = self.env['hr.attendance'].sudo().search([
					('employee_id', '=', employee.id),
					('check_in', '>=', punch_date),
					('check_in', '<', punch_date + timedelta(days=1)),
				], limit=1)

				if not attendance:
					raise ValidationError(_(
						"Cannot record break for %(emp)s. No attendance found for %(date)s."
					) % {'emp': employee.name, 'date': punch_date})

				break_slot = rec.break_slot  # '1' or '2'
				break_field_checkin = 'break_checkin'
				break_field_checkout = 'break_checkout'

				existing_break = self.env['employee.break'].sudo().search([
					('attendance_id', '=', attendance.id),
					('break_slot', '=', rec.break_slot),
				], limit=1)

				vals = {
					'employee_id': employee.id,
					'attendance_id': attendance.id,
					'break_slot': rec.break_slot,
				}

				if rec.punch_type == 'break_in':
					vals['break_checkin'] = punch_datetime + timedelta(hours=5)
				else:
					vals['break_checkout'] = punch_datetime + timedelta(hours=5)

				if existing_break:
					existing_break.write(vals)
				else:
					self.env['employee.break'].sudo().create(vals)
					new_break = self.env['employee.break'].sudo().create(vals)
					rec.break_id = new_break.id
					_logger.info(f"Created break {break_slot} for {employee.name}")

				self._remove_absent(rec)
				attendance._compute_overtime()
				attendance._compute_break_display()

				rec.state = 'attendance_created'
				continue  # Skip attendance logic

			attendance_obj = self.env['hr.attendance'].sudo()
			created_attendance = None

			if rec.punch_type == 'check_in':
				existing = attendance_obj.search([
					('employee_id', '=', employee.id),
					('check_in', '>=', punch_date),
					('check_in', '<', punch_date + timedelta(days=1)),
				], limit=1)

				if existing:
					if existing.check_in > punch_datetime:
						existing.write({'check_in': punch_datetime})
					elif not existing.check_out:
						existing.write({'check_out': punch_datetime})
					created_attendance = existing
				else:
					created_attendance = attendance_obj.create({
						'employee_id': employee.id,
						'check_in': punch_datetime,
					})

			elif rec.punch_type == 'check_out':
				existing = attendance_obj.search([
					('employee_id', '=', employee.id),
					('check_in', '>=', punch_date),
					('check_in', '<', punch_date + timedelta(days=1)),
				], limit=1)

				if existing:
					existing.write({'check_out': punch_datetime})
					created_attendance = existing
				else:
					raise ValidationError(_(
						"Cannot check out %(emp)s on %(date)s without check-in."
					) % {'emp': employee.name, 'date': punch_date})

			if created_attendance:
				created_attendance._compute_overtime()
				created_attendance._compute_break_display()

			rec.attendance_id = created_attendance.id if created_attendance else False
			self._remove_absent(rec)
			rec.state = 'attendance_created'

	def _remove_absent(self, rec):
		absent_recs = self.env['hr.attendance.absents'].sudo().search([
			('employee_id', '=', rec.employee_id.id),
			('time', '=', rec.punch_datetime.date()),
		])
		absent_recs.unlink()

	def action_bulk_attendance_create(self):
		for rec in self:
			employee = rec.employee_id.sudo()

			if not employee.contract_id:
				rec.message_post(body=_("Skipped — Employee has no valid or running contract!"))
				continue

			punch_date = fields.Date.to_date(rec.punch_datetime)
			punch_datetime = rec.punch_datetime
			created_attendance = None

			try:
				if rec.punch_type in ['break_in', 'break_out']:
					punch_datetime = punch_datetime
					attendance = self.env['hr.attendance'].sudo().search([
						('employee_id', '=', employee.id),
						('check_in', '>=', punch_date),
						('check_in', '<', punch_date + timedelta(days=1)),
					], limit=1)

					if not attendance:
						rec.message_post(body=_(
							"No attendance found for %(emp)s on %(date)s. Break not recorded."
						) % {'emp': employee.name, 'date': punch_date})
						rec.action_reset()
						continue

					break_slot = rec.break_slot or '1'

					existing_break = self.env['employee.break'].sudo().search([
						('attendance_id', '=', attendance.id),
						('break_slot', '=', break_slot),
					], limit=1)

					vals = {
						'employee_id': employee.id,
						'attendance_id': attendance.id,
						'break_slot': break_slot,
					}

					if rec.punch_type == 'break_in':
						vals['break_checkin'] = punch_datetime + timedelta(hours=5)
					else:
						vals['break_checkout'] = punch_datetime + timedelta(hours=5)

					if existing_break:
						existing_break.write(vals)
						rec.break_id = existing_break.id
						rec.message_post(body=_(
							"Break %(slot)s updated: %(time)s"
						) % {'slot': break_slot, 'time': punch_datetime.strftime('%H:%M')})
					else:
						new_break = self.env['employee.break'].sudo().create(vals)
						rec.break_id = new_break.id
						rec.message_post(body=_(
							"Break %(slot)s recorded: %(time)s"
						) % {'slot': break_slot, 'time': punch_datetime.strftime('%H:%M')})

					# Remove absent
					self.env['hr.attendance.absents'].sudo().search([
						('employee_id', '=', employee.id),
						('time', '=', punch_date),
					]).unlink()
					
					attendance._compute_overtime()
					attendance._compute_break_display()

					rec.state = 'attendance_created'
					continue  # Skip normal attendance

				attendance_obj = self.env['hr.attendance'].sudo()

				if rec.punch_type == 'check_in':
					existing = attendance_obj.search([
						('employee_id', '=', employee.id),
						('check_in', '>=', punch_date),
						('check_in', '<', punch_date + timedelta(days=1)),
					], limit=1)

					if existing:
						if existing.check_in > punch_datetime:
							existing.write({'check_in': punch_datetime})
						created_attendance = existing
					else:
						created_attendance = attendance_obj.create({
							'employee_id': employee.id,
							'check_in': punch_datetime,
						})

				elif rec.punch_type == 'check_out':
					existing = attendance_obj.search([
						('employee_id', '=', employee.id),
						('check_in', '>=', punch_date),
						('check_in', '<', punch_date + timedelta(days=1)),
					], limit=1)

					if existing:
						existing.write({'check_out': punch_datetime})
						created_attendance = existing
					else:
						rec.message_post(body=_(
							"No check-in found for %(empl_name)s on %(date)s"
						) % {'empl_name': employee.name, 'date': punch_date})
						rec.action_reset()
						continue

				if created_attendance:
					created_attendance._compute_overtime()
					created_attendance._compute_break_display()

				rec.attendance_id = created_attendance.id if created_attendance else False

				self.env['hr.attendance.absents'].sudo().search([
					('employee_id', '=', employee.id),
					('time', '=', punch_date),
				]).unlink()

				rec.state = 'attendance_created'

			except Exception as e:
				rec.message_post(body=_("Error: %s") % str(e))
				rec.action_reset()
				continue