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


class PunchesRequestsPortalExt(portal.CustomerPortal):


	def _prepare_home_portal_values(self, counters):
		values = super()._prepare_home_portal_values(counters)
		user = request.env.user
		missing_punch = request.env['missing.punch'].sudo()

		if 'employee_missing_punches_count' in counters:
			if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
				missing_punch_count = missing_punch.search_count([])
			else:
				missing_punch_count = missing_punch.search_count([('employee_id.user_id', '=', user.id)])
			values['employee_missing_punches_count'] = missing_punch_count
		return values

	def _missing_punch_get_page_view_values(self, missing_punch, access_token, **kwargs):
		values = {
			'page_name': 'my_missing_punches',
			'missing_punch': missing_punch,
		}
		return self._get_page_view_values(missing_punch, access_token, values, 'my_missing_punch_history', False, **kwargs)
	

	def get_values_mp(self):
		values = {}
		employees = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.uid)], limit=1)
		values.update({
			'employees': employees,
		})
		return values


	@http.route(['/my/my_missing_punches','/my/my_missing_punches/page/<int:page>'], type='http', auth="user", website=True)
	def portal_my_missing_punches(self, page=1, sortby=None, filterby=None, search=None, search_in='my_missing_punches', groupby='none', **kw):
		
		if not request.env.user.sudo().has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.not_found()

		user = request.env.user
		missing_punch = request.env['missing.punch'].sudo()


		searchbar_sortings = {
			'punch_type': {'label': _('Punch Type'), 'order': 'punch_type desc'},
			'date': {'label': _('Date'), 'order': 'punch_datetime desc'},
		}

		searchbar_inputs = {
			'my_missing_punches': {'input': 'my_missing_punches', 'label': _('Search My Mising Punches')},
			'all': {'input': 'all', 'label': _('Search in All')},
			'employee': {'input': 'employee', 'label': _('Search in Employee')},
		}

		if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
			domain = []
		else:
			domain = []
			domain.append(('employee_id.user_id', '=', user.id))

		today = datetime.today()
		last_month = date_utils.subtract(today, months=1)
		last_year = date_utils.subtract(today, years=1)
		quarter_start, quarter_end = date_utils.get_quarter(today)

		searchbar_filters = {
			'my_missing_punches': {
				'label': _('My Missing Punches'),
				'domain': [('employee_id.user_id', '=', user.id)]
			},
			'all': {
				'label': _('All'),
				'domain': []
			},
			'punch_datetime': {
				'label': _('This month'),
				'domain': [
					('punch_datetime', '>=', date_utils.start_of(today, 'month')),
					('punch_datetime', '<=', date_utils.end_of(today, 'month'))
				]
			},
			'year': {
				'label': _('This year'),
				'domain': [
					('punch_datetime', '>=', date_utils.start_of(today, 'year')),
					('punch_datetime', '<=', date_utils.end_of(today, 'year'))
				]
			},
			'quarter': {
				'label': _('This Quarter'),
				'domain': [
					('punch_datetime', '>=', quarter_start),
					('punch_datetime', '<=', quarter_end)
				]
			},
			'last_month': {
				'label': _('Last month'),
				'domain': [
					('punch_datetime', '>=', date_utils.start_of(last_month, 'month')),
					('punch_datetime', '<=', date_utils.end_of(last_month, 'month'))
				]
			},
			'last_year': {
				'label': _('Last year'),
				'domain': [
					('punch_datetime', '>=', date_utils.start_of(last_year, 'year')),
					('punch_datetime', '<=', date_utils.end_of(last_year, 'year'))
				]
			},
		}
		if not sortby:
			sortby = 'date'
		order = searchbar_sortings[sortby]['order']
		if not filterby:
			filterby = 'my_missing_punches'
		domain = AND([domain, searchbar_filters[filterby]['domain']])

		if search and search_in:
			search_domain = []
			if search_in in ('employee', 'all'):
				search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
			if search_in in ('my_missing_punches', 'all'):
				search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
			domain += search_domain

		missing_punch = missing_punch.sudo().search(domain,order=order)
		missing_punch_count = len(missing_punch)

		pager = portal_pager(
			url="/my/my_missing_punches",
			url_args={'sortby': sortby, 'search_in': search_in, 'search': search, 'filterby': filterby},
			total=missing_punch_count,
			page=page,
			step=self._items_per_page,
		)

		missing_punch = missing_punch.sudo().search(domain,order=order, limit=self._items_per_page, offset=pager['offset'])
		missing_punch_count = len(missing_punch)

		request.session['my_missing_punch_history'] = missing_punch.ids[:100]

		values = {
			'missing_punch_requests': missing_punch,
			'page_name': 'my_missing_punches',
			'pager': pager,
			'default_url': '/my/my_missing_punches',
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

		return request.render("employee_hr_portal.portal_my_missing_punches", values)

	@http.route(['/create/missing_punch'], type='http', auth="user", website=True, csrf=False)
	def create_missing_punch_request(self, **post):
		missing_punch = request.env['missing.punch'].sudo()
		redirect = ('/create/my_missing_punch')
		vals = {}
		try:
			punch_datetime = datetime.strptime(post['punch_datetime'], '%Y-%m-%dT%H:%M') - timedelta(hours=5)
			punch_type = post['punch_type']
			break_slot = post['break_slot']
			reason = post['reason']
			employee_id = request.env.user.employee_id.id

			existing_request = missing_punch.search([
				('employee_id', '=', employee_id),
				('punch_datetime', '=', punch_datetime),
			], limit=1)

			if existing_request:
				error_msg = "You already have an missing punch request for this date."
				return request.redirect("%s?error_msg=%s" % (redirect, error_msg))

			vals_to_pass = {
				'punch_datetime': punch_datetime,
				'punch_type': punch_type,
				'break_slot': break_slot,
				'reason': reason,
				'employee_id': employee_id,
			}

			missing_punch_id = missing_punch.create(vals_to_pass)
			_logger.info(_('Successfully Created missing punch: %s' % request.env.user.name))

			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				return request.redirect("/my/my_missing_punches")
			else:
				return request.redirect('/my')

		except Exception as e:
			request.env.cr.rollback()
			return request.redirect("%s?error_msg=%s" % (redirect, e))

	@http.route(['/create/my_missing_punch'], type='http', auth="public", website=True, csrf=False)
	def portal_create_my_missing_punch(self, **kw):
		missing_punch = request.env['missing.punch'].sudo()
		redirect = ("/my/my_missing_punches")
		try:
			values = self.get_values_mp()
			employee_id = values.get('employees')
			if employee_id:
				values.update({'page_name': 'my_missing_punches_create'})

				if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
					return request.render("employee_hr_portal.portal_my_missing_punch_create", values)
				else:
					return request.redirect('/my')
			else:
				return request.redirect("%s?error_msg=%s" % (redirect, 'The employee of this request is missing. Please make sure that your user login is linked to an employee.'))
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, e))

	@http.route(['/my/missing_punch/<int:missing_punch_id>'], type='http', auth="user", website=True, csrf=False)
	def portal_my_missing_punch(self, missing_punch_id=None, access_token=None, **kw):
		missing_punch = request.env['missing.punch'].sudo().search([('id','=',int(missing_punch_id))])
		redirect = ("/my/my_missing_punches")
		try:
			values = self.get_values_mp()
			employee_id = values.get('employees')
			missing_punch_sudo = missing_punch
			if not missing_punch_sudo:
				if not employee_id:
					return request.redirect("%s?error_msg=%s" % (redirect, 'The employee of this request is missing. Please make sure that your user login is linked to an employee.'))
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, e))

		values.update(self._missing_punch_get_page_view_values(missing_punch_sudo, access_token, **kw))
		values['missing_punch_datetime'] = missing_punch_sudo.punch_datetime + timedelta(hours=5)

		history = request.session.get('my_missing_punch_history', [])

		current_task_index = history.index(missing_punch.id)
		total_orders = len(history)
		try:
			prev_record = "/my/missing_punch/{0}".format(str(history[current_task_index - 1]))
			values['prev_record'] = current_task_index != 0 and prev_record
		except:
			pass
		try:
			next_record = "/my/missing_punch/{0}".format(str(history[current_task_index + 1]))
			values['next_record'] = current_task_index < total_orders - 1 and next_record
		except:
			pass


		if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.render("employee_hr_portal.portal_my_missing_punch", values)
		else:
			return request.redirect('/my')

	@http.route(['/my/missing_punch/delete/<int:missing_punch_id>'], type='http', auth="user", website=True)
	def portal_unlink_missing_punch(self, missing_punch_id=None, access_token=None, **kw):
		missing_punch = request.env['missing.punch'].sudo().search([('id','=',int(missing_punch_id))])
		redirect = '/my/my_missing_punches'
		try:
			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				missing_punch_sudo = missing_punch
				if missing_punch_sudo:
					missing_punch_sudo.unlink()
				return request.redirect(redirect)
			else:
				return request.redirect('/my')
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, e))
	
	@http.route(['/missing_punch/update/<model("missing.punch"):missing_punch_id>'], type='http', auth="user", methods=['POST'], website=True, csrf=False)
	def update_missing_punch(self, missing_punch_id, access_token=None, **post):
		missing_punch = request.env['missing.punch'].sudo()
		redirect = ("/my/missing_punch/%s" % missing_punch_id.sudo().id)
		try:
			punch_datetime = datetime.strptime(post['punch_datetime'], '%Y-%m-%dT%H:%M') - timedelta(hours=5)
			punch_type = post['punch_type']
			break_slot = post['break_slot']
			reason = post['reason']
			employee_id = missing_punch_id.sudo().employee_id.id
			existing_request = missing_punch.search([
				('employee_id', '=', employee_id),
				('punch_datetime', '=', punch_datetime),
				('id', '!=', missing_punch_id.sudo().id),
			], limit=1)

			if existing_request:
				error_msg = "You already have an missing punch request for this date."
				return request.redirect("%s?error_msg=%s" % (redirect, error_msg))

			vals_to_pass = {
				'punch_datetime': punch_datetime,
				'punch_type': punch_type,
				'break_slot': break_slot,
				'reason': reason,
			}

			missing_punch_id = missing_punch_id.sudo().write(vals_to_pass)
			_logger.info(_('Successfully Updated missing_punch: %s' % request.env.user.name))

			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				return request.redirect("/my/my_missing_punches")
			else:
				return request.redirect('/my')

		except Exception as e:
			request.env.cr.rollback()
			return request.redirect("%s?error_msg=%s" % (redirect, e))