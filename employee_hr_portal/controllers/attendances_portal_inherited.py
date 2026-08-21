# -*- coding: utf-8 -*-
from odoo import http, tools, _
from odoo import models, fields, api, _
from odoo import fields, http, SUPERUSER_ID, _
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF, date_utils, groupby as groupbyelem
from odoo.addons.portal.controllers import portal
from odoo.addons.portal.controllers.portal import pager as portal_pager, get_records_pager
from odoo.http import content_disposition, Controller, request, route
import calendar
from odoo.osv.expression import AND, OR
from ast import literal_eval
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from collections import OrderedDict
from operator import itemgetter


class AttendancesPortalExt(portal.CustomerPortal):

	def _get_earliest_breaks(self, attendance):
	    import json
	    all_break_ins = []
	    all_break_outs = []

	    # Source 1: biometric device (breaks JSON - already local time as HH:MM)
	    raw = attendance.breaks
	    if raw:
	        try:
	            pairs = json.loads(raw) if isinstance(raw, str) else raw
	            for pair in pairs:
	                bi = pair.get('break_in')
	                bo = pair.get('break_out')
	                if bi:
	                    try:
	                        parts = str(bi).strip().split(' ')
	                        time_part = parts[1] if len(parts) == 2 else parts[0]
	                        hh, mm = time_part.split(':')[:2]
	                        all_break_ins.append(f"{hh}:{mm}")
	                    except Exception:
	                        pass
	                if bo:
	                    try:
	                        parts = str(bo).strip().split(' ')
	                        time_part = parts[1] if len(parts) == 2 else parts[0]
	                        hh, mm = time_part.split(':')[:2]
	                        all_break_outs.append(f"{hh}:{mm}")
	                    except Exception:
	                        pass
	        except Exception:
	            pass

	    # Source 2: missing punch (break_ids - stored as local time naive datetime)
	    for br in attendance.break_ids:
	        if br.break_checkin:
	            all_break_ins.append(br.break_checkin.strftime('%H:%M'))
	        if br.break_checkout:
	            all_break_outs.append(br.break_checkout.strftime('%H:%M'))
	        if br.break_checkin2:
	            all_break_ins.append(br.break_checkin2.strftime('%H:%M'))
	        if br.break_checkout2:
	            all_break_outs.append(br.break_checkout2.strftime('%H:%M'))

	    earliest_in  = min(all_break_ins)  if all_break_ins  else None
	    earliest_out = min(all_break_outs) if all_break_outs else None

	    parts = []
	    if earliest_in:
	        parts.append(f"Break In: {earliest_in}")
	    if earliest_out:
	        parts.append(f"Break Out: {earliest_out}")
	    return '\n'.join(parts)
	

	def _prepare_home_portal_values(self, counters):
		values = super()._prepare_home_portal_values(counters)
		user = request.env.user
		Attendances = request.env['hr.attendance'].sudo()

		if 'employee_attendances_count' in counters:
			if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
				attendances_count = Attendances.search_count([])
			else:
				attendances_count = Attendances.search_count([('employee_id.user_id', '=', user.id)])
			values['employee_attendances_count'] = attendances_count
		return values

	def _get_month_range_20_to_19(self, target_month, current_year):
		"""
		Get date range from 20th of previous month to 19th of target month
		For example: January -> Dec 20 to Jan 19
		"""
		if target_month == 1:  # January
			prev_month = 12
			prev_year = current_year - 1
		else:
			prev_month = target_month - 1
			prev_year = current_year

		# Start date: 28th of previous month
		start_date = date(prev_year, prev_month, 28)

		# End date: 19th of target month
		end_date = date(current_year, target_month, 28)

		return start_date, end_date

	@http.route(['/my/my_attendances', '/my/my_attendances/page/<int:page>'], type='http', auth="user", website=True)
	def portal_my_attendances(self, page=1, sortby=None, filterby=None, search=None, search_in='my_attendances',
							  groupby='none', **kw):

		if not request.env.user.sudo().has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.not_found()

		# Initialize variables safely
		user = request.env.user
		Attendances = request.env['hr.attendance'].sudo()

		# Extract date parameters safely
		date_from = kw.get('date_from', '')
		date_to = kw.get('date_to', '')

		# Clean empty strings
		if not date_from:
			date_from = None
		if not date_to:
			date_to = None

		# Updated searchbar_sortings with months dropdown
		searchbar_sortings = {
			'date': {'label': _('Date'), 'order': 'check_in desc'},
			'january': {'label': _('January'), 'order': 'check_in desc'},
			'february': {'label': _('February'), 'order': 'check_in desc'},
			'march': {'label': _('March'), 'order': 'check_in desc'},
			'april': {'label': _('April'), 'order': 'check_in desc'},
			'may': {'label': _('May'), 'order': 'check_in desc'},
			'june': {'label': _('June'), 'order': 'check_in desc'},
			'july': {'label': _('July'), 'order': 'check_in desc'},
			'august': {'label': _('August'), 'order': 'check_in desc'},
			'september': {'label': _('September'), 'order': 'check_in desc'},
			'october': {'label': _('October'), 'order': 'check_in desc'},
			'november': {'label': _('November'), 'order': 'check_in desc'},
			'december': {'label': _('December'), 'order': 'check_in desc'},
		}

		searchbar_inputs = {
			'my_attendances': {'input': 'my_attendances', 'label': _('Search My Attendances')},
			'all': {'input': 'all', 'label': _('Search in All')},
			'employee': {'input': 'employee', 'label': _('Search in Employee')},
		}

		if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
			domain = []
		else:
			domain = []
			domain.append(('employee_id.user_id', '=', user.id))

		today = fields.Date.today()
		start_date = (today - relativedelta(months=1)).replace(day=29)
		end_date = today
		current_year = today.year
		quarter_start, quarter_end = date_utils.get_quarter(today)
		last_week = today + relativedelta(weeks=-1)
		last_month = today + relativedelta(months=-1)
		last_year = today + relativedelta(years=-1)

		# Custom periods for this month and last month
		current_month_start = today.replace(day=1)
		prev_month = current_month_start - relativedelta(months=1)
		this_month_start = prev_month.replace(day=20)
		this_month_end = today.replace(day=19)

		last_last_month = last_month + relativedelta(months=-1)
		last_month_start = last_last_month.replace(day=20)
		last_month_end = last_month.replace(day=19)

		searchbar_filters = {
			'my_attendances': {'label': _('My Attendances'), 'domain': [('employee_id.user_id', '=', user.id)]},
			'all': {'label': _('All'), 'domain': []},
			'month': {'label': _('This month'),
					  'domain': [('check_in', '>=', this_month_start), ('check_in', '<=', this_month_end)]},
			'year': {'label': _('This year'), 'domain': [('check_in', '>=', date_utils.start_of(today, 'year')),
														 ('check_in', '<=', date_utils.end_of(today, 'year'))]},
			'quarter': {'label': _('This Quarter'),
						'domain': [('check_in', '>=', quarter_start), ('check_in', '<=', quarter_end)]},
			'last_month': {'label': _('Last month'),
						   'domain': [('check_in', '>=', last_month_start), ('check_in', '<=', last_month_end)]},
			'last_year': {'label': _('Last year'),
						  'domain': [('check_in', '>=', date_utils.start_of(last_year, 'year')),
									 ('check_in', '<=', date_utils.end_of(last_year, 'year'))]},
		}

		if not sortby:
			sortby = 'date'
		order = searchbar_sortings[sortby]['order']

		# Handle date range filtering first
		date_filter_applied = False

		if date_from:
			try:
				date_from_obj = fields.Date.from_string(date_from)
				domain = AND([domain, [('check_in', '>=', date_from_obj)]])
				date_filter_applied = True
			except:
				date_from = None

		if date_to:
			try:
				date_to_obj = fields.Date.from_string(date_to)
				# Add one day to include the entire end date
				date_to_obj = date_to_obj + timedelta(days=1)
				domain = AND([domain, [('check_in', '<', date_to_obj)]])
				date_filter_applied = True
			except:
				date_to = None

		# Handle month-specific sorting/filtering with 20th to 19th range
		month_filters = {
			'january': 1, 'february': 2, 'march': 3, 'april': 4,
			'may': 5, 'june': 6, 'july': 7, 'august': 8,
			'september': 9, 'october': 10, 'november': 11, 'december': 12
		}

		month_filter_applied = False
		if sortby in month_filters:
			month_num = month_filters[sortby]
			month_start, month_end = self._get_month_range_20_to_19(month_num, current_year)

			domain = AND([domain, [('check_in', '>=', month_start), ('check_in', '<=', month_end)]])
			month_filter_applied = True

		if not filterby:
			filterby = 'my_attendances'

		# Apply filter domain only if no date or month filtering
		if not date_filter_applied and not month_filter_applied:
			domain = AND([domain, searchbar_filters[filterby]['domain']])

			if filterby in ['my_attendances', 'all']:
				current_month_start = today.replace(day=1)
				prev_month_start = current_month_start - relativedelta(months=1)
				start_date = start_date
				end_date = today
				domain = AND([domain, [('check_in', '>=', start_date), ('check_in', '<=', end_date)]])

		# search
		if search and search_in:
			search_domain = []
			if search_in in ('employee', 'all'):
				search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
			if search_in in ('my_attendances', 'all'):
				search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
			domain += search_domain

		attendances = Attendances.sudo().search(domain, order=order)
		attendances_count = len(attendances)

		pager = portal_pager(
			url="/my/my_attendances",
			url_args={'sortby': sortby, 'search_in': search_in, 'search': search, 'filterby': filterby,
					  'date_from': date_from or '', 'date_to': date_to or ''},
			total=attendances_count,
			page=page,
			step=self._items_per_page,
		)

		attendances = Attendances.sudo().search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])

		values = {
			'attendances': attendances,
			'page_name': 'my_attendances',
			'pager': pager,
			'default_url': '/my/my_attendances',
			'searchbar_filters': {},
			'sortby': sortby,
			'searchbar_sortings': searchbar_sortings,
			'search_in': search_in,
			'groupby': groupby,
			'searchbar_inputs': searchbar_inputs,
			'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
			'filterby': filterby,
			'date_from': date_from or '',
			'date_to': date_to or '',
		}

		# Compute unified break display for each attendance
		attendance_breaks = {}
		for att in attendances:
		    attendance_breaks[att.id] = self._get_earliest_breaks(att)

		values['attendance_breaks'] = attendance_breaks

		return request.render("employee_hr_portal.portal_my_attendances", values)