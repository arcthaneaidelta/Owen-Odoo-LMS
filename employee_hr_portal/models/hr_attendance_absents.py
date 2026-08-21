from odoo import models, fields, api, _
from datetime import datetime, date, timedelta

class HrAttendanceAbsents(models.Model):
	_name = "hr.attendance.absents"
	_description = "Hr Attendance Absents"
	_rec_name = 'employee_id'
	_inherit = ['mail.thread', 'mail.activity.mixin']

	company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company,copy=False,tracking=True)
	user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user,tracking=True,copy=False)
	employee_id = fields.Many2one('hr.employee', string='Employee', tracking=True, copy=False)
	time = fields.Date(string='Date', tracking=True, copy=False, default=fields.Date.today())
	contract_id = fields.Many2one('hr.contract', string='Employee Contract', tracking=True, copy=False)

	@api.model
	def _mark_absentees(self):
		today = (datetime.today() + timedelta(hours=5)).date()
		employees = self.env['hr.employee'].sudo().search([])
		for employee in employees:
			attendance = self.env['hr.attendance'].sudo().search([(('employee_id', '=', employee.id))]).filtered(lambda m:m.employee_id.id == employee.id and (m.check_in + timedelta(hours=5)) >= datetime.combine(today, datetime.min.time()) and (m.check_in + timedelta(hours=5)) <= datetime.combine(today, datetime.max.time()))
			already_absents_recs = self.env['hr.attendance.absents'].sudo().search_count([
				('employee_id', '=', employee.id),
				('time', '>=', today),
				('time', '<=', today)
			])
			absents_recs = self.env['hr.attendance.absents'].sudo()
			if len(attendance) == 0 and already_absents_recs == 0:
				absents_recs = absents_recs.sudo().create({
					'employee_id': employee.id,
					'time': today,
					'contract_id':employee.contract_id.id if employee.contract_id else False
				})

	@api.model
	def _mark_old_del_absentees(self):
		today = (datetime.today() + timedelta(hours=5)).date()
		employees = self.env['hr.employee'].sudo().search([])
		for employee in employees:
			attendance = self.env['hr.attendance'].sudo().search([(('employee_id', '=', employee.id))]).filtered(lambda m:m.employee_id.id == employee.id and (m.check_in + timedelta(hours=5)) >= datetime.combine(today, datetime.min.time()) and (m.check_in + timedelta(hours=5)) <= datetime.combine(today, datetime.max.time()))
			already_absents_recs = self.env['hr.attendance.absents'].sudo().search([
				('employee_id', '=', employee.id),
				('time', '>=', today),
				('time', '<=', today)
			])
			absents_recs = self.env['hr.attendance.absents'].sudo()
			if attendance and already_absents_recs:
				for x in already_absents_recs:
					x.sudo().unlink()