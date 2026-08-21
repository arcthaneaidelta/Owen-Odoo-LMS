# -*- coding: utf-8 -*-
from odoo import http,tools, _
from odoo import models, fields, api ,_
from odoo import fields, http, SUPERUSER_ID, _
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF, date_utils, groupby as groupbyelem
from odoo.addons.portal.controllers import portal
from odoo.addons.portal.controllers.portal import pager as portal_pager, get_records_pager
from odoo.http import content_disposition, Controller, request, route
from datetime import datetime, timedelta, date
import calendar
from odoo.osv.expression import AND, OR
from ast import literal_eval
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from collections import OrderedDict
from operator import itemgetter
import logging
_logger = logging.getLogger(__name__)


class OvertimeRequestsPortalExt(portal.CustomerPortal):


	def _prepare_home_portal_values(self, counters):
		values = super()._prepare_home_portal_values(counters)
		user = request.env.user
		overtime_requests = request.env['hr.overtime.requests'].sudo()

		if 'employee_overtime_requests_count' in counters:
			if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
				overtime_requests_count = overtime_requests.search_count([])
			else:
				overtime_requests_count = overtime_requests.search_count([('employee_id.user_id', '=', user.id)])
			values['employee_overtime_requests_count'] = overtime_requests_count
		return values

	def _overtime_get_page_view_values(self, overtime, access_token, **kwargs):
		values = {
			'page_name': 'overtime_requests',
			'overtime': overtime,
		}
		return self._get_page_view_values(overtime, access_token, values, 'my_overtime_requests_history', False, **kwargs)
	

	def get_values_overtime_req(self):
		values = {}
		employees = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.uid)], limit=1)
		values.update({
			'employees': employees,
		})
		return values


	@http.route(['/my/my_overtime_requests','/my/my_overtime_requests/page/<int:page>'], type='http', auth="user", website=True)
	def portal_my_overtime_requests(self, page=1, sortby=None, filterby=None, search=None, search_in='my_overtimes', groupby='none', **kw):
		
		if not request.env.user.sudo().has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.not_found()

		user = request.env.user
		overtime_requests = request.env['hr.overtime.requests'].sudo()


		searchbar_sortings = {
			'name': {'label': _('Name'), 'order': 'name desc'},
			'requested_date': {'label': _('Date'), 'order': 'requested_date desc'},
		}

		searchbar_inputs = {
			'my_overtimes': {'input': 'my_overtimes', 'label': _('Search My overtime Requests')},
			'all': {'input': 'all', 'label': _('Search in All')},
			'employee': {'input': 'employee', 'label': _('Search in Employee')},
		}

		if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
			domain = []
		else:
			domain = []
			domain.append(('employee_id.user_id', '=', user.id))

		today = fields.Date.today()
		quarter_start, quarter_end = date_utils.get_quarter(today)
		last_week = today + relativedelta(weeks=-1)
		last_month = today + relativedelta(months=-1)
		last_year = today + relativedelta(years=-1)

		searchbar_filters = {
			'my_overtimes': {'label': _('My Overtime Requests'), 'domain': [('employee_id.user_id', '=', user.id)]},
			'all': {'label': _('All'), 'domain': []},
			'month': {'label': _('This month'), 'domain': [('requested_date', '>=', date_utils.start_of(today, 'month')), ('requested_date', '<=', date_utils.end_of(today, 'month'))]},
			'year': {'label': _('This year'), 'domain': [('requested_date', '>=', date_utils.start_of(today, 'year')), ('requested_date', '<=', date_utils.end_of(today, 'year'))]},
			'quarter': {'label': _('This Quarter'), 'domain': [('requested_date', '>=', quarter_start), ('requested_date', '<=', quarter_end)]},
			'last_month': {'label': _('Last month'), 'domain': [('requested_date', '>=', date_utils.start_of(last_month, 'month')), ('requested_date', '<=', date_utils.end_of(last_month, 'month'))]},
			'last_year': {'label': _('Last year'), 'domain': [('requested_date', '>=', date_utils.start_of(last_year, 'year')), ('requested_date', '<=', date_utils.end_of(last_year, 'year'))]},
		}
		if not sortby:
			sortby = 'name'
		order = searchbar_sortings[sortby]['order']
		if not filterby:
			filterby = 'my_overtimes'
		domain = AND([domain, searchbar_filters[filterby]['domain']])

		if search and search_in:
			search_domain = []
			if search_in in ('employee', 'all'):
				search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
			if search_in in ('my_overtimes', 'all'):
				search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
			domain += search_domain

		overtime_requests = overtime_requests.sudo().search(domain,order=order)
		overtime_requests_count = len(overtime_requests)

		pager = portal_pager(
			url="/my/my_overtime_requests",
			url_args={'sortby': sortby, 'search_in': search_in, 'search': search, 'filterby': filterby},
			total=overtime_requests_count,
			page=page,
			step=self._items_per_page,
		)

		overtime_requests = overtime_requests.sudo().search(domain,order=order, limit=self._items_per_page, offset=pager['offset'])
		overtime_requests_count = len(overtime_requests)
		request.session['my_overtime_requests_history'] = overtime_requests.ids[:100]

		values = {
			'overtime_requests': overtime_requests,
			'page_name': 'my_overtimes',
			'pager': pager,
			'default_url': '/my/my_overtime_requests',
			'searchbar_filters': {},
			'sortby': sortby,
			'searchbar_sortings': searchbar_sortings,
			'search_in': search_in,
			'sortby': sortby,
			'groupby': groupby,
			'searchbar_inputs': searchbar_inputs,
			'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
			'filterby': filterby,
		}

		return request.render("employee_hr_portal.portal_my_overtime_requests", values)

	@http.route(['/create/overtime'], type='http', auth="user", website=True, csrf=False)
	def create_overtime_request(self, **post):
		overtime = request.env['hr.overtime.requests'].sudo()
		redirect = ('/create/my_overtime')
		vals = {}
		try:
			name = post['name']
			date = datetime.strptime(post['date'], '%Y-%m-%d')
			reason = post['reason']
			employee_id = request.env.user.employee_id.id

			existing_request = overtime.search([
				('employee_id', '=', employee_id),
				('requested_date', '<=', date),
				('requested_date', '>=', date)
			], limit=1)

			if existing_request:
				error_msg = "You already have an overtime request for this date."
				return request.redirect("%s?error_msg=%s" % (redirect, error_msg))

			vals_to_pass = {
				'name': name,
				'employee_id': employee_id,
				'requested_date':date,
				'reason':reason,
			}

			overtime_id = overtime.create(vals_to_pass)
			_logger.info(_('Successfully Created overtime: %s' % request.env.user.name))

			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				return request.redirect("/my/my_overtime_requests")
			else:
				return request.redirect('/my')

		except Exception as e:
			request.env.cr.rollback()
			return request.redirect("%s?error_msg=%s" % (redirect, e))

	@http.route(['/create/my_overtime'], type='http', auth="public", website=True, csrf=False)
	def portal_create_my_overtime(self, **kw):
		overtime = request.env['hr.overtime.requests'].sudo()
		redirect = ("/my/my_overtime_requests")
		try:
			values = self.get_values_overtime_req()
			employee_id = values.get('employees')
			if employee_id:
				values.update({'page_name': 'my_overtimes_create'})

				if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
					return request.render("employee_hr_portal.portal_my_overtime_create", values)
				else:
					return request.redirect('/my')
			else:
				return request.redirect("%s?error_msg=%s" % (redirect, 'The employee of this request is missing. Please make sure that your user login is linked to an employee.'))
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, e))

	@http.route(['/my/overtime/<int:overtime_id>'], type='http', auth="user", website=True, csrf=False)
	def portal_my_overtime(self, overtime_id=None, access_token=None, **kw):
		overtime = request.env['hr.overtime.requests'].sudo().search([('id','=',int(overtime_id))])
		redirect = ("/my/my_overtime_requests")
		try:
			values = self.get_values_overtime_req()
			employee_id = values.get('employees')
			overtime_sudo = overtime
			if not overtime_sudo:
				if not employee_id:
					return request.redirect("%s?error_msg=%s" % (redirect, 'The employee of this request is missing. Please make sure that your user login is linked to an employee.'))
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, e))

		values.update(self._overtime_get_page_view_values(overtime_sudo, access_token, **kw))
		history = request.session.get('my_overtime_requests_history', [])
		current_task_index = history.index(overtime.id)
		total_orders = len(history)
		try:
			prev_record = "/my/overtime/{0}".format(str(history[current_task_index - 1]))
			values['prev_record'] = current_task_index != 0 and prev_record
		except:
			pass
		try:
			next_record = "/my/overtime/{0}".format(str(history[current_task_index + 1]))
			values['next_record'] = current_task_index < total_orders - 1 and next_record
		except:
			pass

		if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.render("employee_hr_portal.portal_my_overtime", values)
		else:
			return request.redirect('/my')

	@http.route(['/my/overtime/delete/<int:overtime_id>'], type='http', auth="user", website=True)
	def portal_unlink_overtime(self, overtime_id=None, access_token=None, **kw):
		overtime = request.env['hr.overtime.requests'].sudo().search([('id','=',int(overtime_id))])
		redirect = '/my/my_overtime_requests'
		try:
			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				overtime_sudo = overtime
				if overtime_sudo:
					overtime_sudo.unlink()
				return request.redirect(redirect)
			else:
				return request.redirect('/my')
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, e))
	
	@http.route(['/overtime/update/<model("hr.overtime.requests"):overtime_id>'], type='http', auth="user", methods=['POST'], website=True, csrf=False)
	def update_overtime(self, overtime_id, access_token=None, **post):
		overtime = request.env['hr.overtime.requests'].sudo()
		redirect = ("/my/overtime/%s" % overtime_id.sudo().id)
		try:
			name = post['name']
			date = datetime.strptime(post['date'], '%Y-%m-%d')
			reason = post['reason']
			employee_id = overtime_id.sudo().employee_id.id

			existing_request = overtime.search([
				('employee_id', '=', employee_id),
				('requested_date', '<=', date),
				('requested_date', '>=', date),
				('id', '!=', overtime_id.sudo().id),
			], limit=1)

			if existing_request:
				error_msg = "You already have an overtime request for this date."
				return request.redirect("%s?error_msg=%s" % (redirect, error_msg))

			vals_to_pass = {
				'name': name,
				'reason': reason,
				'requested_date':date,
			}

			overtime_id = overtime_id.sudo().write(vals_to_pass)
			_logger.info(_('Successfully Updated Overtime: %s' % request.env.user.name))

			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				return request.redirect("/my/my_overtime_requests")
			else:
				return request.redirect('/my')

		except Exception as e:
			request.env.cr.rollback()
			return request.redirect("%s?error_msg=%s" % (redirect, e))