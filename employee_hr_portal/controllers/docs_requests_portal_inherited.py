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


class hr_docRequestssPortalExt(portal.CustomerPortal):


	def _prepare_home_portal_values(self, counters):
		values = super()._prepare_home_portal_values(counters)
		user = request.env.user
		hr_docs_mails = request.env['mail.mail'].sudo()

		if 'employee_docs_count' in counters:
			if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
				hr_docs_mails_count = hr_docs_mails.search_count([])
			else:
				hr_docs_mails_count = hr_docs_mails.search_count([('recipient_ids', 'in', user.sudo().partner_id.sudo().id)])
			values['employee_docs_count'] = hr_docs_mails_count
		return values


	@http.route(['/my/my_hr_docs','/my/my_hr_docs/page/<int:page>'], type='http', auth="user", website=True)
	def portal_my_hr_docs(self, page=1, sortby=None, filterby=None, search=None, search_in='my_hr_docs', groupby='none', **kw):
		
		if not request.env.user.sudo().has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.not_found()

		user = request.env.user
		hr_docs_mails = request.env['mail.mail'].sudo()

		searchbar_sortings = {
			'subject': {'label': _('Subject'), 'order': 'subject desc'},
			'date': {'label': _('Date'), 'order': 'date desc'},
		}

		searchbar_inputs = {
			'my_hr_docs': {'input': 'my_hr_docs', 'label': _('Search My Docs')},
			'all': {'input': 'all', 'label': _('Search in All')},
			'author': {'input': 'author', 'label': _('Search Author or Sender')},
			'subject': {'input': 'subject', 'label': _('Search Subject')},
		}

		if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
			domain = []
		else:
			domain = []
			domain.append(('recipient_ids', 'in', user.sudo().partner_id.sudo().id))

		today = datetime.today()
		last_month = date_utils.subtract(today, months=1)
		last_year = date_utils.subtract(today, years=1)
		quarter_start, quarter_end = date_utils.get_quarter(today)

		searchbar_filters = {
			'my_hr_docs': {
				'label': _('My Docs'),
				'domain': [('recipient_ids', 'in', user.sudo().partner_id.sudo().id)]
			},
			'all': {
				'label': _('All'),
				'domain': []
			},
			'date': {
				'label': _('This month'),
				'domain': [
					('date', '>=', date_utils.start_of(today, 'month')),
					('date', '<=', date_utils.end_of(today, 'month'))
				]
			},
			'year': {
				'label': _('This year'),
				'domain': [
					('date', '>=', date_utils.start_of(today, 'year')),
					('date', '<=', date_utils.end_of(today, 'year'))
				]
			},
			'quarter': {
				'label': _('This Quarter'),
				'domain': [
					('date', '>=', quarter_start),
					('date', '<=', quarter_end)
				]
			},
			'last_month': {
				'label': _('Last month'),
				'domain': [
					('date', '>=', date_utils.start_of(last_month, 'month')),
					('date', '<=', date_utils.end_of(last_month, 'month'))
				]
			},
			'last_year': {
				'label': _('Last year'),
				'domain': [
					('date', '>=', date_utils.start_of(last_year, 'year')),
					('date', '<=', date_utils.end_of(last_year, 'year'))
				]
			},
		}

		if not sortby:
			sortby = 'subject'
		order = searchbar_sortings[sortby]['order']
		if not filterby:
			filterby = 'my_hr_docs'
		domain = AND([domain, searchbar_filters[filterby]['domain']])

		if search and search_in:
			search_domain = []
			if search_in in ('author', 'all'):
				search_domain = OR([search_domain, [('author_id.name', 'ilike', search)]])
			if search_in in ('my_hr_docs', 'all'):
				search_domain = OR([search_domain, ['|',('subject', 'ilike', search),('author_id.name', 'ilike', search)]])
			if search_in in ('subject', 'all'):
				search_domain = OR([search_domain, [('subject', 'ilike', search)]])
			domain += search_domain

		hr_docs_mails = hr_docs_mails.sudo().search(domain,order=order)
		hr_docs_mails_count = len(hr_docs_mails)

		pager = portal_pager(
			url="/my/my_hr_docs",
			url_args={'sortby': sortby, 'search_in': search_in, 'search': search, 'filterby': filterby},
			total=hr_docs_mails_count,
			page=page,
			step=self._items_per_page,
		)

		hr_docs_mails = hr_docs_mails.sudo().search(domain,order=order, limit=self._items_per_page, offset=pager['offset'])
		hr_docs_mails_count = len(hr_docs_mails)
		request.session['my_hr_docs_mails_history'] = hr_docs_mails.ids[:100]

		values = {
			'hr_docs_mails': hr_docs_mails,
			'page_name': 'my_hr_docs',
			'pager': pager,
			'default_url': '/my/my_hr_docs',
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
		return request.render("employee_hr_portal.portal_my_hr_docs", values)

	@http.route(['/my/hr_doc/<int:hr_doc_id>'], type='http', auth="user", website=True, csrf=False)
	def portal_my_hr_doc(self, hr_doc_id=None, access_token=None, **kw):
		hr_doc = request.env['mail.mail'].sudo().search([('id','=',int(hr_doc_id))])

		values = {
			'page_name': 'my_hr_docs',
			'hr_doc': hr_doc,
			'no_breadcrumbs': False
		}

		values = self._get_page_view_values(hr_doc, access_token, values,'my_hr_docs_mails_history', False, **kw)
		history = request.session.get('my_hr_docs_mails_history', [])
		current_task_index = history.index(hr_doc.id)
		total_orders = len(history)
		try:
			prev_record = "/my/hr_doc/{0}".format(str(history[current_task_index - 1]))
			values['prev_record'] = current_task_index != 0 and prev_record
		except:
			pass
		try:
			next_record = "/my/hr_doc/{0}".format(str(history[current_task_index + 1]))
			values['next_record'] = current_task_index < total_orders - 1 and next_record
		except:
			pass

		print(values)
		if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.render("employee_hr_portal.portal_my_hr_doc", values)
		else:
			return request.redirect('/my')