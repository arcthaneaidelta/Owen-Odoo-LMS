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


class ADvanceRequestssPortalExt(portal.CustomerPortal):


	def _prepare_home_portal_values(self, counters):
		values = super()._prepare_home_portal_values(counters)
		user = request.env.user
		advance_requests = request.env['advance.requests'].sudo()

		if 'employee_advance_requests_count' in counters:
			if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
				advance_requests_count = advance_requests.search_count([])
			else:
				advance_requests_count = advance_requests.search_count([('employee_id.user_id', '=', user.id)])
			values['employee_advance_requests_count'] = advance_requests_count
		return values

	def _advance_get_page_view_values(self, advance, access_token, **kwargs):
		values = {
			'page_name': 'advance_requests',
			'advance': advance,
		}
		return self._get_page_view_values(advance, access_token, values, 'my_advance_requests_history', False, **kwargs)
	

	def get_values_adv(self):
		values = {}
		employees = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.uid)], limit=1)
		values.update({
			'employees': employees,
		})
		return values


	@http.route(['/my/my_advances','/my/my_advances/page/<int:page>'], type='http', auth="user", website=True)
	def portal_my_advances(self, page=1, sortby=None, filterby=None, search=None, search_in='my_advances', groupby='none', **kw):
		
		if not request.env.user.sudo().has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.not_found()

		user = request.env.user
		advance_requests = request.env['advance.requests'].sudo()


		searchbar_sortings = {
			'name': {'label': _('Name'), 'order': 'name desc'},
			'date': {'label': _('Date'), 'order': 'month desc'},
		}

		searchbar_inputs = {
			'my_advances': {'input': 'my_advances', 'label': _('Search My Advance Requests')},
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
			'my_advances': {'label': _('My Advance Requests'), 'domain': [('employee_id.user_id', '=', user.id)]},
			'all': {'label': _('All'), 'domain': []},
			'month': {'label': _('This month'), 'domain': [('month', '>=', date_utils.start_of(today, 'month')), ('month', '<=', date_utils.end_of(today, 'month'))]},
			'year': {'label': _('This year'), 'domain': [('month', '>=', date_utils.start_of(today, 'year')), ('month', '<=', date_utils.end_of(today, 'year'))]},
			'quarter': {'label': _('This Quarter'), 'domain': [('month', '>=', quarter_start), ('month', '<=', quarter_end)]},
			'last_month': {'label': _('Last month'), 'domain': [('month', '>=', date_utils.start_of(last_month, 'month')), ('month', '<=', date_utils.end_of(last_month, 'month'))]},
			'last_year': {'label': _('Last year'), 'domain': [('month', '>=', date_utils.start_of(last_year, 'year')), ('month', '<=', date_utils.end_of(last_year, 'year'))]},
		}
		if not sortby:
			sortby = 'name'
		order = searchbar_sortings[sortby]['order']
		if not filterby:
			filterby = 'my_advances'
		domain = AND([domain, searchbar_filters[filterby]['domain']])

		if search and search_in:
			search_domain = []
			if search_in in ('employee', 'all'):
				search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
			if search_in in ('my_advances', 'all'):
				search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
			domain += search_domain

		advance_requests = advance_requests.sudo().search(domain,order=order)
		advance_requests_count = len(advance_requests)

		pager = portal_pager(
			url="/my/my_advances",
			url_args={'sortby': sortby, 'search_in': search_in, 'search': search, 'filterby': filterby},
			total=advance_requests_count,
			page=page,
			step=self._items_per_page,
		)

		advance_requests = advance_requests.sudo().search(domain,order=order, limit=self._items_per_page, offset=pager['offset'])
		advance_requests_count = len(advance_requests)
		request.session['my_advance_requests_history'] = advance_requests.ids[:100]

		values = {
			'advance_requests': advance_requests,
			'page_name': 'my_advances',
			'pager': pager,
			'default_url': '/my/my_advances',
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

		return request.render("employee_hr_portal.portal_my_advances", values)

	@http.route(['/create/advance'], type='http', auth="user", website=True, csrf=False)
	def create_advance_request(self, **post):
		Advance = request.env['advance.requests'].sudo()
		redirect = ('/create/my_advance')
		vals = {}
		try:
			name = post['name']
			month = datetime.strptime(post['month'], '%Y-%m')
			amount = float(post['amount'])
			reason = post['reason']
			employee_id = request.env.user.employee_id.id

			existing_request = Advance.search([
				('employee_id', '=', employee_id),
				('month', '<=', month),
				('month', '>=', month)
			], limit=1)

			if existing_request:
				error_msg = "You already have an advance request for this month."
				return request.redirect("%s?error_msg=%s" % (redirect, error_msg))

			vals_to_pass = {
				'name': name,
				'month': month,
				'amount': amount,
				'reason': reason,
				'employee_id': employee_id,
				'contract_id':request.env.user.employee_id.sudo().contract_id.sudo().id,
				'requested_date':datetime.now()
			}

			advance_id = Advance.create(vals_to_pass)
			_logger.info(_('Successfully Created Advance: %s' % request.env.user.name))

			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				return request.redirect("/my/my_advances")
			else:
				return request.redirect('/my')

		except Exception as e:
			request.env.cr.rollback()
			return request.redirect("%s?error_msg=%s" % (redirect, e))

	@http.route(['/create/my_advance'], type='http', auth="public", website=True, csrf=False)
	def portal_create_my_advance(self, **kw):
		Advance = request.env['advance.requests'].sudo()
		redirect = ("/my/my_advances")
		try:
			values = self.get_values_adv()
			employee_id = values.get('employees')
			if employee_id:
				values.update({'page_name': 'my_advances_create'})

				if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
					return request.render("employee_hr_portal.portal_my_advance_create", values)
				else:
					return request.redirect('/my')
			else:
				return request.redirect("%s?error_msg=%s" % (redirect, 'The employee of this request is missing. Please make sure that your user login is linked to an employee.'))
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, e))

	@http.route(['/my/advance/<int:advance_id>'], type='http', auth="user", website=True, csrf=False)
	def portal_my_advance(self, advance_id=None, access_token=None, **kw):
		Advance = request.env['advance.requests'].sudo().search([('id','=',int(advance_id))])
		redirect = ("/my/my_advances")
		try:
			values = self.get_values_adv()
			employee_id = values.get('employees')
			advance_sudo = Advance
			if not advance_sudo:
				if not employee_id:
					return request.redirect("%s?error_msg=%s" % (redirect, 'The employee of this request is missing. Please make sure that your user login is linked to an employee.'))
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, e))

		values.update(self._advance_get_page_view_values(advance_sudo, access_token, **kw))
		history = request.session.get('my_advance_requests_history', [])
		current_task_index = history.index(Advance.id)
		total_orders = len(history)
		try:
			prev_record = "/my/advance/{0}".format(str(history[current_task_index - 1]))
			values['prev_record'] = current_task_index != 0 and prev_record
		except:
			pass
		try:
			next_record = "/my/advance/{0}".format(str(history[current_task_index + 1]))
			values['next_record'] = current_task_index < total_orders - 1 and next_record
		except:
			pass

		if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.render("employee_hr_portal.portal_my_advance", values)
		else:
			return request.redirect('/my')

	@http.route(['/my/advance/delete/<int:advance_id>'], type='http', auth="user", website=True)
	def portal_unlink_Advance(self, advance_id=None, access_token=None, **kw):
		Advance = request.env['advance.requests'].sudo().search([('id','=',int(advance_id))])
		redirect = '/my/my_advances'
		try:
			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				advance_sudo = Advance
				if advance_sudo:
					advance_sudo.unlink()
				return request.redirect(redirect)
			else:
				return request.redirect('/my')
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, e))
	
	@http.route(['/advance/update/<model("advance.requests"):advance_id>'], type='http', auth="user", methods=['POST'], website=True, csrf=False)
	def update_advance(self, advance_id, access_token=None, **post):
		Advance = request.env['advance.requests'].sudo()
		redirect = ("/my/advance/%s" % advance_id.sudo().id)
		try:
			name = post['name']
			month = datetime.strptime(post['month'], '%Y-%m-%d')
			amount = float(post['amount'])
			reason = post['reason']
			employee_id = advance_id.sudo().employee_id.id

			existing_request = Advance.search([
				('employee_id', '=', employee_id),
				('month', '<=', month),
				('month', '>=', month),
				('id', '!=', advance_id.sudo().id),
			], limit=1)

			if existing_request:
				error_msg = "You already have an advance request for this month."
				return request.redirect("%s?error_msg=%s" % (redirect, error_msg))

			vals_to_pass = {
				'name': name,
				'month': month,
				'amount': amount,
				'reason': reason,
				'requested_date':datetime.now(),
				'contract_id':advance_id.sudo().employee_id.sudo().contract_id.sudo().id
			}

			advance_id = advance_id.sudo().write(vals_to_pass)
			_logger.info(_('Successfully Updated Advance: %s' % request.env.user.name))

			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				return request.redirect("/my/my_advances")
			else:
				return request.redirect('/my')

		except Exception as e:
			request.env.cr.rollback()
			return request.redirect("%s?error_msg=%s" % (redirect, e))