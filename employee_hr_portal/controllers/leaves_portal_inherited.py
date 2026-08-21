# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

import base64
import logging
import json
from collections import OrderedDict
from dateutil.relativedelta import relativedelta
from operator import itemgetter
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF, date_utils, groupby as groupbyelem
from pytz import timezone, UTC
from odoo.addons.resource.models.utils import float_to_time
from odoo import fields, http, _
from odoo.exceptions import ValidationError
from odoo.osv.expression import AND, OR
from ast import literal_eval
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from datetime import datetime, date, timedelta
from odoo.http import request, Response


# Monkey patch CustomerPortal._prepare_portal_layout_values to inject show_attendance_dashboard safely
orig_prepare_portal_layout_values = CustomerPortal._prepare_portal_layout_values

def new_prepare_portal_layout_values(self):
	values = orig_prepare_portal_layout_values(self)
	user = request.env.user
	is_employee_portal = False
	is_manager = False
	has_employee_and_contract = False
	try:
		is_employee_portal = user.sudo().has_group('employee_hr_portal.access_to_employee_portal_custom_user')
		is_manager = user.sudo().has_group('employee_hr_portal.access_to_quot_manager_custom')
		if user.employee_id:
			employee = user.employee_id.sudo()
			if employee.contract_id:
				has_employee_and_contract = True
	except Exception:
		pass
	values['show_attendance_dashboard'] = is_employee_portal and (is_manager or has_employee_and_contract)
	return values

CustomerPortal._prepare_portal_layout_values = new_prepare_portal_layout_values


_logger = logging.getLogger(__name__)


class LeaveCustomerPortal(CustomerPortal):

	MANDATORY_BILLING_FIELDS = ["name", "phone", "email", "street", "tz", "city", "country_id"]
	OPTIONAL_BILLING_FIELDS = ["zipcode", "state_id", "vat", "company_name"]

	@http.route(['/my/account'], type='http', auth='user', website=True)
	def account(self, redirect=None, **post):
		res = super(LeaveCustomerPortal, self).account(redirect=redirect, **post)
		partner = request.env.user.partner_id
		timezones = request.env.user.sudo()._fields['tz']._description_selection(request.env)
		res.qcontext.update({'timezones': timezones})

		if post:
			values = {}
			error, error_message = self.details_form_validate(post)
			values.update({'error': error, 'error_message': error_message})
			values.update(post)
			if not error:
				values = {key: post[key] for key in self.MANDATORY_BILLING_FIELDS}
				values.update({key: post[key] for key in self.OPTIONAL_BILLING_FIELDS if key in post})
				values.update({'zip': values.pop('zipcode', '')})
				partner.sudo().write(values)
				# Timezone Update using website user employee
				employee_id = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.uid)], limit=1)
				if employee_id:
					employee_id.tz = values.get('tz')
				if redirect:
					return request.redirect(redirect)
				return request.redirect('/my/home')
		return res

	def _prepare_home_portal_values(self, counters):
		values = super()._prepare_home_portal_values(counters)
		user = request.env.user
		leave_obj = request.env['hr.leave'].sudo()
		if 'employee_leaves_count' in counters:
			if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
				domain = []
				values['employee_leaves_count'] = leave_obj.search_count([])
			else:
				domain = leave_obj._leave_get_portal_domain() or []
				values['employee_leaves_count'] = leave_obj.search_count([('employee_id.user_id', '=', request.env.user.id)])
		return values

	def _leave_get_page_view_values(self, leave, access_token, **kwargs):
		values = {
			'page_name': 'leave',
			'leave': leave,
		}
		return self._get_page_view_values(leave, access_token, values, 'my_leaves_history', False, **kwargs)

	
	@http.route(['/my/leaves', '/my/leaves/page/<int:page>'], type='http', auth="user", website=True)
	def portal_my_leaves(self, page=1, sortby=None, filterby=None, search=None, search_in='my_leave', groupby='type', **kw):
		leave_sudo = request.env['hr.leave'].sudo()
		values = self._prepare_portal_layout_values()
		domain = leave_sudo._leave_get_portal_domain()
		domain = [('employee_id.user_id', '=', request.env.user.id)]

		searchbar_sortings = {
			'date': {'label': _('Newest'), 'order': 'id desc, request_date_from desc'},
			'name': {'label': _('Name'), 'order': 'name'},
		}

		searchbar_inputs = {
			'my_leave': {'input': 'my_leave', 'label': _('Search My Leave')},
			'all': {'input': 'all', 'label': _('Search in All')},
			'employee': {'input': 'employee', 'label': _('Search in Employee')},
			'type': {'input': 'type', 'label': _('Search in Type')},
		}

		searchbar_groupby = {
			'none': {'input': 'none', 'label': _('None')},
			'type': {'input': 'type', 'label': _('Leave Type')},
			'employee': {'input': 'employee', 'label': _('Employee')},
		}
		today = fields.Date.today()
		quarter_start, quarter_end = date_utils.get_quarter(today)
		last_week = today + relativedelta(weeks=-1)
		last_month = today + relativedelta(months=-1)
		last_year = today + relativedelta(years=-1)

		searchbar_filters = {
			'my_leave': {'label': _('My Leave'), 'domain': [('user_id', '=', request.env.user.id)]},
			'all': {'label': _('All'), 'domain': []},
			'today': {'label': _('Today'), 'domain': [("request_date_from", "=", today)]},
			'week': {'label': _('This week'), 'domain': [('request_date_from', '>=', date_utils.start_of(today, "week")), ('request_date_from', '<=', date_utils.end_of(today, 'week'))]},
			'month': {'label': _('This month'), 'domain': [('request_date_from', '>=', date_utils.start_of(today, 'month')), ('request_date_from', '<=', date_utils.end_of(today, 'month'))]},
			'year': {'label': _('This year'), 'domain': [('request_date_from', '>=', date_utils.start_of(today, 'year')), ('request_date_from', '<=', date_utils.end_of(today, 'year'))]},
			'quarter': {'label': _('This Quarter'), 'domain': [('request_date_from', '>=', quarter_start), ('request_date_from', '<=', quarter_end)]},
			'last_week': {'label': _('Last week'), 'domain': [('request_date_from', '>=', date_utils.start_of(last_week, "week")), ('request_date_from', '<=', date_utils.end_of(last_week, 'week'))]},
			'last_month': {'label': _('Last month'), 'domain': [('request_date_from', '>=', date_utils.start_of(last_month, 'month')), ('request_date_from', '<=', date_utils.end_of(last_month, 'month'))]},
			'last_year': {'label': _('Last year'), 'domain': [('request_date_from', '>=', date_utils.start_of(last_year, 'year')), ('request_date_from', '<=', date_utils.end_of(last_year, 'year'))]},
		}
		# default sort by value
		if not sortby:
			sortby = 'date'
		order = searchbar_sortings[sortby]['order']
		# default filter by value
		if not filterby:
			filterby = 'my_leave'
		domain = AND([domain, searchbar_filters[filterby]['domain']])

		# search
		if search and search_in:
			search_domain = []
			if search_in in ('employee', 'all'):
				search_domain = OR([search_domain, ['|', ('name', 'ilike', search),('employee_id', 'ilike', search)]])
			if search_in in ('type', 'all'):
				search_domain = OR([search_domain, [('holiday_status_id', 'ilike', search)]])
			if search_in in ('my_leave', 'all'):
				search_domain = OR([search_domain, [('user_id', 'ilike', search)]])
			domain += search_domain

		employee_leaves_count = leave_sudo.search_count(domain)
		# pager
		pager = portal_pager(
			url="/my/leaves",
			url_args={'sortby': sortby, 'search_in': search_in, 'search': search, 'filterby': filterby},
			total=employee_leaves_count,
			page=page,
			step=self._items_per_page
		)

		if groupby == 'type':
			order = "holiday_status_id, %s" % order

		leaves = leave_sudo.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
		grouped_leaves = [leaves]
		if groupby == 'employee':
			grouped_leaves = [leave_sudo.concat(*g) for k, g in groupbyelem(leaves, itemgetter('employee_id'))]
		if groupby == 'type':
			grouped_leaves = [leave_sudo.concat(*g) for k, g in groupbyelem(leaves, itemgetter('holiday_status_id'))]

		values.update(self.get_values_leaves_vals())
		# Leaves types Calculation
		if values.get('employees'):
			# leave_types = request.env['hr.leave.type'].sudo().search([]).filtered(lambda x:x.requires_allocation == 'no' or x.has_valid_allocation == True or x.company_id.id == request.env.user.company_id.id)
			leave_types = request.env['hr.leave.type'].sudo().search([])
			employee_id = values.get('employees')[:1]
			values.update({'leave_types': leave_types, 'employee_id': employee_id})

		if not values.get('employees'):
			raise request.not_found()

		# content according to pager and archive selected
		leaves = leave_sudo.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
		request.session['my_leaves_history'] = leaves.ids[:100]
		values.update({
			'leaves': leaves,
			'grouped_leaves': grouped_leaves,
			'page_name': 'leave',
			'default_url': '/my/leaves',
			'pager': pager,
			'searchbar_sortings': searchbar_sortings,
			'search_in': search_in,
			'sortby': sortby,
			'groupby': groupby,
			'searchbar_inputs': searchbar_inputs,
			'searchbar_groupby': searchbar_groupby,
			'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
			'filterby': filterby,
		})
		if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.render("employee_hr_portal.portal_my_leaves", values)
		else:
			return request.redirect('/my')

	@http.route(['/create/leave'], type='http', auth="user", website=True, csrf=False)
	def create_leave(self, **post):
		"""
			Create method for leave.
		"""
		Leave = request.env['hr.leave'].sudo()
		redirect = ('/create/my_leave')
		vals = {}
		try:
			vals = self.get_leave_dict(post, is_create=True)

			if 'date_from' in vals:
				date_from = vals['date_from'].split('.')
				vals['date_from'] = datetime.strptime(date_from[0], '%Y-%m-%d %H:%M:%S') - timedelta(hours=5)
			if 'date_to' in vals:
				date_to = vals['date_to'].split('.')
				vals['date_to'] = datetime.strptime(date_to[0], '%Y-%m-%d %H:%M:%S') - timedelta(hours=5)
			leave_id = Leave.sudo().create(vals)
			if post.get('ufile') and leave_id:
				attached_files = request.httprequest.files.getlist('ufile')
				self.create_document(attached_files, leave_id)
			_logger.info(_('Successfully Create Leave : %s' % (request.env.user.name)))

			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				return request.redirect("/my/leaves")
			else:
				return request.redirect('/my')
		except Exception as e:
			request.env.cr.rollback()
			return request.redirect("%s?error_msg=%s" % (redirect, (Leave.error_msg(e))))

	@http.route(['/create/my_leave'], type='http', auth="public", website=True, csrf=False)
	def portal_create_my_leave(self, create_from_header=None, **kw):
		Leave = request.env['hr.leave'].sudo()
		redirect = ("/my/leaves")
		try:
			values = self.get_values_leaves_vals()
			employee_id = values.get('employees')
			if employee_id:
				values.update({'page_name': 'leave_create'})
				if create_from_header:
					values['create_from_header'] = True

				if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
					return request.render("employee_hr_portal.portal_my_leave_create", values)
				else:
					return request.redirect('/my')
			else:
				return request.redirect("%s?error_msg=%s" % (redirect, 'The employee and department of this request is missing. Please make sure that your user login is linked to an employee.'))
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, (Leave.error_msg(e))))

	@http.route(['/my/leave/<int:leave_id>'], type='http', auth="user", website=True, csrf=False)
	def portal_my_leave(self, leave_id=None, access_token=None, **kw):
		Leave = request.env['hr.leave'].sudo().search([('id','=',int(leave_id))])
		redirect = ("/my/leaves")
		try:
			values = self.get_values_leaves_vals()
			employee_id = values.get('employees')
			leave_sudo = Leave
			# leave_sudo = self._document_check_access('hr.leave', leave_id, access_token=access_token)
			if not leave_sudo:
				if not employee_id:
					return request.redirect("%s?error_msg=%s" % (redirect, 'The employee and department of this request is missing. Please make sure that your user login is linked to an employee.'))
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, (Leave.error_msg(e))))

		values.update(self._leave_get_page_view_values(leave_sudo, access_token, **kw))

		if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.render("employee_hr_portal.portal_my_leave", values)
		else:
			return request.redirect('/my')

	@http.route(['/my/leave/delete/<int:leave_id>'], type='http', auth="user", website=True)
	def portal_unlink_leave(self, leave_id=None, access_token=None, **kw):
		Leave = request.env['hr.leave'].sudo().search([('id','=',int(leave_id))])
		redirect = '/my/leaves'
		try:
			# leave_sudo = self._document_check_access('hr.leave', leave_id, access_token)

			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				leave_sudo = Leave
				if leave_sudo:
					leave_sudo.unlink()
				return request.redirect(redirect)
			else:
				return request.redirect('/my')
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, (Leave.error_msg(e))))

	@http.route(['/my/leave/set_state/<int:leave_id>'], type='http', auth="user", website=True)
	def portal_set_leave_state(self, leave_id=None, access_token=None, **kw):
		Leave = request.env['hr.leave'].sudo()
		redirect = ("/my/leave/%s" % leave_id)
		try:
			leaves = request.env['hr.leave'].sudo().browse(int(leave_id))
			leave_sudo = leaves
			# leave_sudo = self._document_check_access('hr.leave', leave_id, access_token)


			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				if leave_sudo and leave_sudo.state in ['confirm', 'refuse']:
					if leave_sudo.user_id.id == request.env.uid and leave_sudo.state == 'refuse':
						return request.redirect("%s?error_msg=%s" % (redirect, 'Not Allowed.'))
					leave_sudo.action_draft()
				elif leave_sudo and leave_sudo.state == 'draft':
					leave_sudo.action_confirm()
				return request.redirect(redirect)
			else:
				return request.redirect('/my')
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, (Leave.error_msg(e))))

	@http.route(['/my/leave/resetdraft/<int:leave_id>'], type='http', auth="user", website=True)
	def portal_leave_resetdraft(self, leave_id=None, access_token=None, **kw):
		Leave = request.env['hr.leave'].sudo()
		redirect = ("/my/leave/%s" % leave_id)
		try:
			leaves = request.env['hr.leave'].sudo().browse(int(leave_id))
			leave_sudo = leaves


			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				if leave_sudo.user_id.id == request.env.uid:
					return request.redirect("%s?error_msg=%s" % (redirect, 'Not Allowed.'))

				if leave_sudo and leave_sudo.user_id.id != request.env.uid:
					leave_sudo.action_draft()
				return request.redirect(redirect)
			else:
				return request.redirect('/my')
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, (Leave.error_msg(e))))

	
	@http.route(['/leave/update/<model("hr.leave"):leave_id>'], type='http', auth="user", methods=['POST'], website=True, csrf=False)
	def update_leave(self, leave_id, access_token=None, **post):
		"""
			Update method for leave.
		"""
		Leave = request.env['hr.leave'].sudo()
		redirect = ("/my/leave/%s" % leave_id.id)
		try:
			if leave_id:
				vals = self.get_leave_dict(post, leave_id)
				if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
					# Leave.check_access_rights('write')
					leave_id.sudo().write(vals)
					if post.get('confirm', False):
						leave_id.sudo().action_confirm()
					return request.redirect(redirect)#("/my/leaves")
				else:
					return request.redirect('/my')
		except Exception as e:
			request.env.cr.rollback()
			return request.redirect("%s?error_msg=%s" % (redirect, (Leave.error_msg(e))))

	def get_leave_dict(self, post, leave_id=None, is_create=False):
		vals = dict()
		if post:
			number_of_days = 0.0
			if is_create:
				vals.update({
					'request_unit_hours': False,
					'request_unit_half': False,
				})
				employee_id = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
				if employee_id:
					vals.update({'employee_id': employee_id.id, 'department_id': employee_id.department_id and employee_id.department_id.id })
				else:
					employee_id = request.env.user.employee_ids[:1]
					vals.update({'employee_id': employee_id.id, 'department_id': employee_id.department_id and employee_id.department_id.id})


			if post.get('number_of_days'):
				number_of_days = float(post.get('number_of_days'))

			if not number_of_days > 0:
				raise ValidationError("There is no Duration(Days/Hours).")

			if post.get('holiday_status_id'):
				vals.update({'holiday_status_id': literal_eval(post.get('holiday_status_id'))})

			if post.get('request_unit_half') == 'true':
				vals.update({
					'request_unit_half': True,
					'request_date_from_period': post.get('request_date_from_period'),
					'request_unit_hours': False,
				})
			elif post.get('request_unit_hours') == 'true':
				vals.update({
					'request_unit_hours': True,
					'request_hour_to': post.get('request_hour_to'),
					'request_hour_from': post.get('request_hour_from'),
					'request_unit_half': False,
					'number_of_days': number_of_days,
				})
			elif not post.get('request_unit_half') and not post.get('request_unit_hours'):
				vals.update({
					'request_unit_hours': False,
					'request_unit_half': False,
				})

			if not post.get('request_unit_hours'):
				vals.update({
					'number_of_days': number_of_days,
				})

			vals.update({
				'name': post.get('name') ,
				'request_date_from': post.get('request_date_from'),
				'request_date_to': post.get('request_date_to'),
				'date_from': post.get('date_from') or fields.Datetime.now(),
				'date_to': post.get('date_to') or fields.Datetime.now(),
			})
			if post.get('ufile') and leave_id:
				attached_files = request.httprequest.files.getlist('ufile')
				self.create_document(attached_files, leave_id)
		return vals

	@http.route(['/leave/number_of_days'], type='json', auth="public", website=True)
	def get_number_of_days(self, **post):
		vals = {}
		emp_obj = request.env['hr.employee'].sudo()
		employee_id = attendance_from = attendance_to = False
		if post.get('employee_id'):
			employee_id = literal_eval(post.get('employee_id'))
		if not employee_id:
			employee_id = request.env.user.employee_ids[:1].id

		employee_id = emp_obj.browse(employee_id)

		date_from = post.get('date_from') or fields.Datetime.now()
		date_to = post.get('date_to') or fields.Datetime.now()
		request_hour_from = request_unit_hours = False
		request_hour_to = request_date_to = False
		request_date_from = request_unit_half = number_of_days= False
		holiday_status_id = request.env['hr.leave.type'].sudo()

		if post.get('request_date_from'):
			request_date_from = datetime.strptime(post.get('request_date_from'), DF)
		if post.get('request_date_to'):
			request_date_to = datetime.strptime(post.get('request_date_to'), DF)
		if post.get('request_hour_from'):
			request_hour_from = post.get('request_hour_from')
		if post.get('request_hour_to'):
			request_hour_to = post.get('request_hour_to')
		if post.get('request_unit_half'):
			request_unit_half = post.get('request_unit_half')
		if post.get('request_unit_hours'):
			request_unit_hours = post.get('request_unit_hours')

		if post.get('leave_types'):
			leave_types = literal_eval(post.get('leave_types'))
			holiday_status_id = holiday_status_id.browse(leave_types)

		if not request_date_from:
			vals.update({'date_from': False})
		if request_unit_half or request_unit_hours:
			request_date_to = request_date_from
			vals.update({'request_date_to': request_date_to,
						'request_date_from': request_date_from})

		if not request_date_to:
			vals.update({'date_to': False})

		domain = [('calendar_id', '=', employee_id.resource_calendar_id.id or request.env.user.company_id.resource_calendar_id.id)]
		attendances = request.env['resource.calendar.attendance'].sudo().search(domain, order='dayofweek, day_period DESC')

		# find first attendance coming after first_day
		if request_date_from and attendances:
			attendance_from = next((att for att in attendances if int(att.dayofweek) >= request_date_from.weekday()), attendances[0])
		# find last attendance coming before last_day
		if request_date_to and attendances:
			attendance_to = next((att for att in reversed(attendances) if int(att.dayofweek) <= request_date_to.weekday()), attendances[-1])
		hour_from = hour_to = False
		if attendance_from and attendance_to:
			if request_unit_half:
				if post.get('request_date_from_period') == 'am':
					hour_from = float_to_time(attendance_from.hour_from)
					hour_to = float_to_time(attendance_from.hour_to)
				else:
					hour_from = float_to_time(attendance_to.hour_from)
					hour_to = float_to_time(attendance_to.hour_to)
			elif request_unit_hours:
				if request_hour_from:
					request_hour_from = literal_eval(request_hour_from)
					hour_from = float_to_time(abs(request_hour_from) - 0.5 if request_hour_from < 0 else request_hour_from)
				if request_hour_to:
					request_hour_to = literal_eval(request_hour_to)
					hour_to = float_to_time(abs(request_hour_to) - 0.5 if request_hour_to < 0 else request_hour_to)
			else:
				hour_from = float_to_time(attendance_from.hour_from)
				hour_to = float_to_time(attendance_to.hour_to)

			if request.env.user.tz:
				tz = request.env.user.tz if request.env.user.tz else 'UTC'  # custom -> already in UTC
			else:
				tz = request.env.user._context.get('tz') or 'UTC'

			if hour_from:
				date_from = timezone(tz).localize(datetime.combine(request_date_from, hour_from)).astimezone(UTC).replace(tzinfo=None)
			if hour_to:
				date_to = timezone(tz).localize(datetime.combine(request_date_to, hour_to)).astimezone(UTC).replace(tzinfo=None)

			new_leave_id = request.env['hr.leave'].sudo().new({
				'holiday_status_id': holiday_status_id.id,
				'employee_id': employee_id.id,
				'date_to': date_to,
				'date_from': date_from,
				'request_unit_hours': request_unit_hours,
				'request_unit_half': request_unit_half,
			})
			number_of_days = {
				'days': round(float(new_leave_id.number_of_days or 0.0), 2),
				'hours': round(float(new_leave_id.number_of_hours or 0.0), 2)
			}
			vals.update({
				'date_from': date_from,
				'date_to': date_to,
				'number_of_days': number_of_days,
				'support_document': holiday_status_id.support_document
			})
		return vals

	def get_values_leaves_vals(self):
		values = {}
		leave_sudo = request.env['hr.leave'].sudo()
		employees = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.uid)], limit=1)
		hours_selection = [(float(i/2), f"{i//2:02d}:00" if i % 2 == 0 else f"{i//2:02d}:30") for i in range(48)]
		request_hour_from = hours_selection
		request_hour_to = hours_selection
		request_date_from_period = leave_sudo._fields['request_date_from_period']._description_selection(request.env)
		# leave_types = request.env['hr.leave.type'].sudo().search([]).filtered(lambda x:x.requires_allocation == 'no' or x.has_valid_allocation == True or x.company_id.id == request.env.user.company_id.id)
		leave_types = request.env['hr.leave.type'].sudo().search([])
		child_employees = request.env['hr.employee'].sudo().search([('parent_id.user_id', 'in', [request.env.uid])])
		values.update({
			'employees': employees,
			'child_employees': child_employees,
			'request_hour_from': request_hour_from,
			'request_hour_to': request_hour_to,
			'request_date_from_period': request_date_from_period,
			'leave_types': leave_types,
		})
		return values

	def create_document(self, attached_files, leave_id):

		def _get_allowed_message_post_params_website_leave():
			return {'attachment_ids', 'body', 'message_type', 'partner_ids', 'subtype_xmlid', 'parent_id','author_id','sub_type_id'}

		for file in attached_files:
			ufile = file.read()
			vals = {
				'res_model': 'hr.leave',
				'res_id': leave_id,
				'datas': base64.b64encode(ufile),
				'type': 'binary',
				'name': file.filename
			}
			if file.filename:
				attachment_id = request.env['ir.attachment'].sudo().create(vals)
				post_data = {
					'attachment_ids': [attachment_id.id],
					'body': "Leave Attachment Added!",
					'message_type': 'email',
					'partner_ids': [],
					'author_id': request.env.user.partner_id.id if request.env.user.partner_id else False,
					'sub_type_id': request.env.ref('mail.mt_comment').id,
					'subtype_xmlid': 'mail.mt_comment',
				}
				if leave_id:
					data = leave_id.sudo().message_post(**{key: value for key, value in post_data.items() if key in _get_allowed_message_post_params_website_leave()}).message_format()[0]