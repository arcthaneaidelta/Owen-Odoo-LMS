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
from lxml import etree, html
import re


class ExpensesRequestsPortalExt(portal.CustomerPortal):


	def _prepare_home_portal_values(self, counters):
		values = super()._prepare_home_portal_values(counters)
		user = request.env.user
		expense = request.env['hr.expense'].sudo()

		if 'employee_expenses_count' in counters:
			if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
				expense_count = expense.search_count([])
			else:
				expense_count = expense.search_count([('employee_id.user_id', '=', user.id)])
			values['employee_expenses_count'] = expense_count
		return values

	@http.route(['/my/my_expenses','/my/my_expenses/page/<int:page>'], type='http', auth="user", website=True)
	def portal_my_expenses(self, page=1, sortby=None, filterby=None, search=None, search_in='my_expenses', groupby='none', **kw):
		
		if not request.env.user.sudo().has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.not_found()

		user = request.env.user
		expense = request.env['hr.expense'].sudo()


		searchbar_sortings = {
			'name': {'label': _('Name'), 'order': 'name desc'},
			'category': {'label': _('Category'), 'order': 'product_id desc'},
			'employee': {'label': _('Employee'), 'order': 'employee_id desc'},
			'date': {'label': _('Date'), 'order': 'date desc'},
		}

		searchbar_inputs = {
			'my_expenses': {'input': 'my_expenses', 'label': _('Search My Expenses')},
			'all': {'input': 'all', 'label': _('Search in All')},
			'employee': {'input': 'employee', 'label': _('Search in Employee')},
			'category': {'input': 'category', 'label': _('Search in Category')},
			'payment_mode': {'input': 'payment_mode', 'label': _('Search in Paid By')},
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
			'my_expenses': {
				'label': _('My Expenses'),
				'domain': [('employee_id.user_id', '=', user.id)]
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
			sortby = 'date'
		order = searchbar_sortings[sortby]['order']
		if not filterby:
			filterby = 'my_expenses'
		domain = AND([domain, searchbar_filters[filterby]['domain']])

		if search and search_in:
			search_domain = []
			if search_in in ('employee', 'all'):
				search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
			if search_in in ('my_expenses', 'all'):
				search_domain = OR([search_domain, ['|',('name', 'ilike', search),('employee_id.name', 'ilike', search)]])
			if search_in in ('category', 'all'):
				search_domain = OR([search_domain, [('product_id.name', 'ilike', search)]])
			if search_in in ('payment_mode', 'all'):
				search_domain = OR([search_domain, [('payment_mode', 'ilike', search)]])
			domain += search_domain

		expense = expense.sudo().search(domain,order=order)
		expense_count = len(expense)

		pager = portal_pager(
			url="/my/my_expenses",
			url_args={'sortby': sortby, 'search_in': search_in, 'search': search, 'filterby': filterby},
			total=expense_count,
			page=page,
			step=self._items_per_page,
		)

		expense = expense.sudo().search(domain,order=order, limit=self._items_per_page, offset=pager['offset'])
		expense_count = len(expense)

		request.session['my_expense_history'] = expense.ids[:100]

		values = {
			'expense_requests': expense,
			'page_name': 'my_expenses',
			'pager': pager,
			'default_url': '/my/my_expenses',
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

		return request.render("employee_hr_portal.portal_my_expenses", values)

	@http.route(['/create/my_expenses'], type='http', auth="public", website=True, csrf=False)
	def portal_create_my_expense(self, **kw):
		expense = request.env['hr.expense'].sudo()
		redirect = ("/my/my_expenses")
		try:
			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				return request.render("employee_hr_portal.portal_my_expense_create", {'page_name':'my_expenses_create'})
			else:
				return request.redirect('/my')
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, e))

	@http.route(['/my/expense/<int:expense_id>'], type='http', auth="user", website=True, csrf=False)
	def portal_my_expense(self, expense_id=None, access_token=None, **kw):
		expense = request.env['hr.expense'].sudo().search([('id','=',int(expense_id))])
		redirect = ("/my/my_expenses")
		values = {
			'page_name': 'my_expenses',
			'expense': expense,
			'no_breadcrumbs': False
		}
		values = self._get_page_view_values(expense, access_token, values,'my_expense_history', False, **kw)
		history = request.session.get('my_expense_history', [])
		current_task_index = history.index(expense.id)
		total_orders = len(history)
		try:
			prev_record = "/my/expense/{0}".format(str(history[current_task_index - 1]))
			values['prev_record'] = current_task_index != 0 and prev_record
		except:
			pass
		try:
			next_record = "/my/expense/{0}".format(str(history[current_task_index + 1]))
			values['next_record'] = current_task_index < total_orders - 1 and next_record
		except:
			pass
		if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
			return request.render("employee_hr_portal.portal_my_expense", values)
		else:
			return request.redirect('/my')

	@http.route(['/my/expense/delete/<int:expense_id>'], type='http', auth="user", website=True)
	def portal_unlink_expense(self, expense_id=None, access_token=None, **kw):
		expense = request.env['hr.expense'].sudo().search([('id','=',int(expense_id))])
		redirect = '/my/my_expenses'
		try:
			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				expense_sudo = expense
				if expense_sudo:
					expense_sudo.unlink()
				return request.redirect(redirect)
			else:
				return request.redirect('/my')
		except Exception as e:
			return request.redirect("%s?error_msg=%s" % (redirect, e))
	
	@http.route(['/expense/update/<model("hr.expense"):expense_id>'], type='http', auth="user", methods=['POST'], website=True, csrf=False)
	def update_expense(self, expense_id, access_token=None, **post):
		expense = request.env['hr.expense'].sudo()
		redirect = ("/my/expense/%s" % expense_id.sudo().id)
		try:
			employee_id = expense_id.sudo().employee_id.id
			name = post['name']
			date = datetime.strptime(post['date'], '%Y-%m-%d')
			total_amount = float(post['total_amount'])
			category = int(post['category'])
			paid_by = post['paid_by']
			reference = post['reference']
			description = post['description']

			existing_request = expense.search([
				('employee_id', '=', employee_id),
				('date', '=', date),
				('id', '!=', expense_id.sudo().id),
			], limit=1)

			if existing_request:
				error_msg = "You already have an expense request for this date."
				return request.redirect("%s?error_msg=%s" % (redirect, error_msg))

			vals_to_pass = {
				'name':name,
				'date':date,
				'total_amount':total_amount,
				'product_id':category,
				'payment_mode':paid_by,
				'reference':reference,
				'description':description,
			}

			expense_id = expense_id.sudo().write(vals_to_pass)
			_logger.info(_('Successfully Updated Expense: %s' % request.env.user.name))

			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				return request.redirect("/my/my_expenses")
			else:
				return request.redirect('/my')

		except Exception as e:
			request.env.cr.rollback()
			return request.redirect("%s?error_msg=%s" % (redirect, e))

	@http.route(['/create/expense'], type='http', auth="user", website=True, csrf=False)
	def create_expense_request(self, **post):
		expense = request.env['hr.expense'].sudo()
		redirect = ("/create/my_expenses")
		try:
			employee_id = request.env.user.sudo().employee_id.id
			name = post['name']
			date = datetime.strptime(post['date'], '%Y-%m-%d')
			total_amount = float(post['total_amount'])
			category = int(post['category'])
			paid_by = post['paid_by']
			reference = post['reference']
			description = post['description']

			existing_request = expense.search([
				('employee_id', '=', employee_id),
				('date', '=', date),
			], limit=1)

			if existing_request:
				error_msg = "You already have an expense request for this date."
				return request.redirect("%s?error_msg=%s" % (redirect, error_msg))

			vals_to_pass = {
				'name':name,
				'date':date,
				'total_amount':total_amount,
				'product_id':category,
				'payment_mode':paid_by,
				'reference':reference,
				'description':description,
				'employee_id':employee_id,
			}

			expense_id = expense.sudo().create(vals_to_pass)
			_logger.info(_('Successfully Created Expense: %s' % request.env.user.name))
			if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
				return request.redirect("/my/my_expenses")
			else:
				return request.redirect('/my')
		except Exception as e:
			request.env.cr.rollback()
			return request.redirect("%s?error_msg=%s" % (redirect, e))