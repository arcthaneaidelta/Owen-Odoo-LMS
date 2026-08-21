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


class ContractsPortalExt(portal.CustomerPortal):

	def _prepare_home_portal_values(self, counters):
		values = super()._prepare_home_portal_values(counters)
		user = request.env.user
		Contracts = request.env['hr.contract'].sudo()
		if 'employee_contracts_count' in counters:
			if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
				contracts_count = Contracts.search_count([])
			else:
				contracts_count = Contracts.search_count([('employee_id.user_id', '=', user.id)])
			values['employee_contracts_count'] = contracts_count
		return values
	
		
	@http.route(['/my/my_contracts','/my/my_contracts/page/<int:page>'], type='http', auth="user", website=True)
	def portal_my_contracts(self, page=1, sortby=None, filterby=None, search=None, search_in='my_contracts', groupby='none', **kw):
		
		if not request.env.user.sudo().has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.not_found()

		user = request.env.user
		Contracts = request.env['hr.contract'].sudo()


		searchbar_sortings = {
			'date': {'label': _('Date'), 'order': 'date_start desc'},
			'name': {'label': _('Reference'), 'order': 'name desc'},
			'state': {'label': _('Status'), 'order': 'state'},
		}

		searchbar_inputs = {
			'my_contracts': {'input': 'my_contracts', 'label': _('Search My Contracts')},
			'all': {'input': 'all', 'label': _('Search in All')},
			'employee': {'input': 'employee', 'label': _('Search in Employee')},
			'department': {'input': 'department', 'label': _('Search in Department')},
			'job_position': {'input': 'job_position', 'label': _('Search in Job Position')},
			'hr_responsible': {'input': 'hr_responsible', 'label': _('Search in Hr Responsible')},
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
			'my_contracts': {'label': _('My Contracts'), 'domain': [('employee_id.user_id', '=', user.id)]},
			'all': {'label': _('All'), 'domain': []},
			'month': {'label': _('This month'), 'domain': [('date_start', '>=', date_utils.start_of(today, 'month')), ('date_start', '<=', date_utils.end_of(today, 'month'))]},
			'year': {'label': _('This year'), 'domain': [('date_start', '>=', date_utils.start_of(today, 'year')), ('date_start', '<=', date_utils.end_of(today, 'year'))]},
			'quarter': {'label': _('This Quarter'), 'domain': [('date_start', '>=', quarter_start), ('date_start', '<=', quarter_end)]},
			'last_month': {'label': _('Last month'), 'domain': [('date_start', '>=', date_utils.start_of(last_month, 'month')), ('date_start', '<=', date_utils.end_of(last_month, 'month'))]},
			'last_year': {'label': _('Last year'), 'domain': [('date_start', '>=', date_utils.start_of(last_year, 'year')), ('date_start', '<=', date_utils.end_of(last_year, 'year'))]},
		}
		if not sortby:
			sortby = 'date'
		order = searchbar_sortings[sortby]['order']
		if not filterby:
			filterby = 'my_contracts'
		domain = AND([domain, searchbar_filters[filterby]['domain']])

		# search
		if search and search_in:
			search_domain = []
			if search_in in ('employee', 'all'):
				search_domain = OR([search_domain, ['|', ('name', 'ilike', search),('employee_id.name', 'ilike', search)]])
			if search_in in ('my_contracts', 'all'):
				search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
			if search_in in ('department', 'all'):
				search_domain = OR([search_domain, ['|', ('name', 'ilike', search),('department_id.name', 'ilike', search)]])
			if search_in in ('job_position', 'all'):
				search_domain = OR([search_domain, ['|', ('name', 'ilike', search),('job_id.name', 'ilike', search)]])
			if search_in in ('hr_responsible', 'all'):
				search_domain = OR([search_domain, ['|', ('name', 'ilike', search),('hr_responsible_id.name', 'ilike', search)]])
			domain += search_domain

		contracts = Contracts.sudo().search(domain,order=order)
		contracts_count = len(contracts)

		pager = portal_pager(
			url="/my/my_contracts",
			url_args={'sortby': sortby, 'search_in': search_in, 'search': search, 'filterby': filterby},
			total=contracts_count,
			page=page,
			step=self._items_per_page,
		)

		contracts = Contracts.sudo().search(domain,order=order, limit=self._items_per_page, offset=pager['offset'])
		contracts_count = len(contracts)
		request.session['my_contracts_history'] = contracts.ids[:100]

		values = {
			'contracts': contracts,
			'page_name': 'my_contracts',
			'pager': pager,
			'default_url': '/my/my_contracts',
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

		return request.render("employee_hr_portal.portal_my_contracts", values)


	@http.route(['/my/my_contract/<int:contract_id>'], type='http', auth='user', website=True)
	def portal_my_contract(self, contract_id, access_token=None, **kwargs):
		user_id = request.env.user
		Contracts = request.env['hr.contract'].sudo().browse(contract_id)
		if not Contracts.exists():
			return request.redirect('/my/')
		values = {
			'page_name': 'my_contracts',
			'contract': Contracts,
			'no_breadcrumbs': False
		}
		history_session_key = 'my_contracts_history'
		values = self._get_page_view_values(Contracts, access_token, values,'my_contracts_history', False, **kwargs)
		history = request.session.get('my_contracts_history', [])
		current_task_index = history.index(Contracts.id)
		total_orders = len(history)
		try:
			prev_record = "/my/my_contract//{0}".format(str(history[current_task_index - 1]))
			values['prev_record'] = current_task_index != 0 and prev_record
		except:
			pass
		try:
			next_record = "/my/my_contract//{0}".format(str(history[current_task_index + 1]))
			values['next_record'] = current_task_index < total_orders - 1 and next_record
		except:
			pass
		return request.render('employee_hr_portal.portal_contract_details', values)