from odoo import models, fields, api, _
from datetime import date,datetime
import calendar
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from datetime import timedelta

class OvertimeRequests(models.Model):
	_name = "hr.overtime.requests"
	_description = "Overtime Requests"
	_rec_name = 'name'
	_inherit = ['mail.thread', 'mail.activity.mixin']

	company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company,copy=False,tracking=True)
	user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user,tracking=True,copy=False)
	name = fields.Char(string='Name', copy=False, tracking=True)
	employee_id = fields.Many2one('hr.employee', string='Employee', tracking=True, copy=False)
	requested_date = fields.Date(string='Requested Date', tracking=True, copy=False)
	reason = fields.Text(string='Reason/Description')
	state = fields.Selection([
		('new', 'New'),
		('approve', 'Approved'),
		('attendance_updated', 'Attendance Updated'),
		('refuse', 'Refused'),
		('cancel', 'Cancelled')
	], default='new', tracking=True)

	
	def action_reset(self):
		for rec in self:
			rec.state = 'new'
	
	def action_approve(self):
		for rec in self:
			rec.state = 'approve'
	
	def action_refuse(self):
		for rec in self:
			rec.state = 'refuse'
	
	def action_cancel(self):
		for rec in self:
			rec.state = 'cancel'

	def update_attendance(self):
		for rec in self:
			attendance = self.env['hr.attendance'].sudo().search([('employee_id', '=', rec.employee_id.id)]).filtered(lambda m:m.employee_id.id == rec.employee_id.id and (m.check_in + timedelta(hours=5)) >= datetime.combine(rec.requested_date, datetime.min.time()) and (m.check_in + timedelta(hours=5)) <= datetime.combine(rec.requested_date, datetime.max.time()))
			if attendance:
				attendance._compute_overtime()
				rec.state = 'attendance_updated'
			else:
				raise ValidationError('No Attendance Found For Requested Date!')


	def unlink(self):
		for advance in self:
			if advance.state not in ("new", "cancel"):
				raise UserError(
					_(
						"You can only delete a new or cancel Overtime Requests."
					)
				)
		return super(OvertimeRequests, self).unlink()