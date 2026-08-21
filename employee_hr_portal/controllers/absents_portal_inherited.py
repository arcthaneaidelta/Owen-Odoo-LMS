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


class absentsPortalExt(portal.CustomerPortal):

	def _prepare_home_portal_values(self, counters):
		values = super()._prepare_home_portal_values(counters)
		user = request.env.user
		absents = request.env['hr.attendance.absents'].sudo()

		if 'employee_absents_count' in counters:
			if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
				absents_count = absents.search_count([])
			else:
				absents_count = absents.search_count([('employee_id.user_id', '=', user.id)])
			values['employee_absents_count'] = absents_count
		return values
	
		
	@http.route(['/my/my_absents','/my/my_absents/page/<int:page>'], type='http', auth="user", website=True)
	def portal_my_absents(self, page=1, sortby=None, filterby=None, search=None, search_in='my_absents', groupby='none', **kw):
		
		if not request.env.user.sudo().has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.not_found()

		user = request.env.user
		absents = request.env['hr.attendance.absents'].sudo()


		searchbar_sortings = {
			'date': {'label': _('Date'), 'order': 'time desc'},
		}

		searchbar_inputs = {
			'my_absents': {'input': 'my_absents', 'label': _('Search My absents')},
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
			'my_absents': {'label': _('My absents'), 'domain': [('employee_id.user_id', '=', user.id)]},
			'all': {'label': _('All'), 'domain': []},
			'month': {'label': _('This month'), 'domain': [('time', '>=', date_utils.start_of(today, 'month')), ('time', '<=', date_utils.end_of(today, 'month'))]},
			'year': {'label': _('This year'), 'domain': [('time', '>=', date_utils.start_of(today, 'year')), ('time', '<=', date_utils.end_of(today, 'year'))]},
			'quarter': {'label': _('This Quarter'), 'domain': [('time', '>=', quarter_start), ('time', '<=', quarter_end)]},
			'last_month': {'label': _('Last month'), 'domain': [('time', '>=', date_utils.start_of(last_month, 'month')), ('time', '<=', date_utils.end_of(last_month, 'month'))]},
			'last_year': {'label': _('Last year'), 'domain': [('time', '>=', date_utils.start_of(last_year, 'year')), ('time', '<=', date_utils.end_of(last_year, 'year'))]},
		}
		if not sortby:
			sortby = 'date'
		order = searchbar_sortings[sortby]['order']
		if not filterby:
			filterby = 'my_absents'
		domain = AND([domain, searchbar_filters[filterby]['domain']])

		# search
		if search and search_in:
			search_domain = []
			if search_in in ('employee', 'all'):
				search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
			if search_in in ('my_absents', 'all'):
				search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
			domain += search_domain

		absents = absents.sudo().search(domain,order=order)
		absents_count = len(absents)

		pager = portal_pager(
			url="/my/my_absents",
			url_args={'sortby': sortby, 'search_in': search_in, 'search': search, 'filterby': filterby},
			total=absents_count,
			page=page,
			step=self._items_per_page,
		)

		absents = absents.sudo().search(domain,order=order, limit=self._items_per_page, offset=pager['offset'])
		absents_count = len(absents)

		values = {
			'absents': absents,
			'page_name': 'my_absents',
			'pager': pager,
			'default_url': '/my/my_absents',
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

		return request.render("employee_hr_portal.portal_my_absents", values)