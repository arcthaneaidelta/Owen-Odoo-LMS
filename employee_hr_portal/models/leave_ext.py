from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.addons.hr_holidays.models.hr_leave import HolidaysRequest as ORGHolidaysRequest

def _validate_leave_request(self):
	holidays = self.filtered(lambda request: request.employee_id)
	holidays._create_resource_leave()
	meeting_holidays = holidays.filtered(lambda l: l.holiday_status_id.create_calendar_meeting)
	meetings = self.env['calendar.event']
	if meeting_holidays:
		meeting_values_for_user_id = meeting_holidays._prepare_holidays_meeting_values()
		Meeting = self.env['calendar.event']
		for user_id, meeting_values in meeting_values_for_user_id.items():
			#TO-DO ->portal userissue,so self.env.uid
			user = self.env['res.users']
			if user_id:
				if not user.browse(user_id).has_group('base.group_user'):
					meetings += Meeting.with_user(self.env.uid).with_context(
									allowed_company_ids=[],
									no_mail_to_attendees=True,
									calendar_no_videocall=True,
									active_model=self._name
								).create(meeting_values)
				else:	
					meetings += Meeting.with_user(user_id or self.env.uid).with_context(
									allowed_company_ids=[],
									no_mail_to_attendees=True,
									calendar_no_videocall=True,
									active_model=self._name
								).create(meeting_values)
			else:
				meetings += Meeting.with_user(user_id or self.env.uid).with_context(
									allowed_company_ids=[],
									no_mail_to_attendees=True,
									calendar_no_videocall=True,
									active_model=self._name
								).create(meeting_values)
	Holiday = self.env['hr.leave']
	for meeting in meetings:
		Holiday.browse(meeting.res_id).meeting_id = meeting

ORGHolidaysRequest._validate_leave_request = _validate_leave_request

class HrLeave(models.Model):
	_inherit = 'hr.leave'

	employee_manager_id = fields.Many2one(
		'hr.employee',
		string="Employee's Manager",
		related='employee_id.parent_id',
		store=True
	)
	employee_id = fields.Many2one('hr.employee', string='Employee', tracking=True, copy=False)

	@api.model
	def search(self, args=None, offset=0, limit=None, order=None):
		current_user = self.env.user
		domain = []
		if not current_user.has_group('employee_hr_portal.show_all_Leave'):
			domain = ['|',
				('employee_id.user_id', '=', current_user.id),
				('employee_id.parent_id.user_id', '=', current_user.id)
			]
		if args:
			domain = ['&'] + domain + args if domain else args
		return super(HrLeave,self).search(domain, offset=offset, limit=limit, order=order)

	def action_approve(self):
		current_user = self.env.user
		for leave in self:
			if not self.env.user.has_group('employee_hr_portal.show_all_Leave_approve'):
				if leave.employee_id.user_id == current_user:
					raise UserError(_("You cannot approve your own leave request."))
		return super(HrLeave, self).action_approve()

	def action_refuse(self):
		current_user = self.env.user
		for leave in self:
			if leave.employee_id.user_id == current_user:
				raise UserError(_("You cannot refuse your own leave request."))
		return super(HrLeave, self).action_refuse()
