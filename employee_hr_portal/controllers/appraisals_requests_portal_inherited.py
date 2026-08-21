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


class AppraisalsRequestsPortalExt(portal.CustomerPortal):

    def text_from_html(self, html_content, fail=False):
        try:
            doc = html.fromstring(html_content)
        except (TypeError, etree.XMLSyntaxError, etree.ParserError):
            if fail:
                raise
            else:
                _logger.exception("Failure parsing this HTML:\n%s", html_content)
                return ""

        raw_text = html.tostring(doc, encoding="unicode", method="text", with_tail=False)
        return raw_text

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        user = request.env.user
        appraisal = request.env['hr.appraisal'].sudo()

        if 'employee_appraisals_count' in counters:
            if user.has_group('employee_hr_portal.access_to_quot_manager_custom'):
                appraisal_count = appraisal.search_count([])
            else:
                appraisal_count = appraisal.search_count([('employee_id.user_id', '=', user.id)])
            values['employee_appraisals_count'] = appraisal_count
        return values

    @http.route(['/my/my_appraisals', '/my/my_appraisals/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_appraisals(self, page=1, sortby=None, filterby=None, search=None, search_in='my_appraisals',
                             groupby='none', **kw):

        if not request.env.user.sudo().has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
            return request.not_found()

        user = request.env.user
        appraisal = request.env['hr.appraisal'].sudo()

        searchbar_sortings = {
            'employee': {'label': _('Employee'), 'order': 'employee_id desc'},
            'date': {'label': _('Date'), 'order': 'date_close desc'},
        }

        searchbar_inputs = {
            'my_appraisals': {'input': 'my_appraisals', 'label': _('Search My Appraisals')},
            'all': {'input': 'all', 'label': _('Search in All')},
            'employee': {'input': 'employee', 'label': _('Search in Employee')},
            'department': {'input': 'department', 'label': _('Search in Department')},
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
            'my_appraisals': {
                'label': _('My Appraisals'),
                'domain': [('employee_id.user_id', '=', user.id)]
            },
            'all': {
                'label': _('All'),
                'domain': []
            },
            'date_close': {
                'label': _('This month'),
                'domain': [
                    ('date_close', '>=', date_utils.start_of(today, 'month')),
                    ('date_close', '<=', date_utils.end_of(today, 'month'))
                ]
            },
            'year': {
                'label': _('This year'),
                'domain': [
                    ('date_close', '>=', date_utils.start_of(today, 'year')),
                    ('date_close', '<=', date_utils.end_of(today, 'year'))
                ]
            },
            'quarter': {
                'label': _('This Quarter'),
                'domain': [
                    ('date_close', '>=', quarter_start),
                    ('date_close', '<=', quarter_end)
                ]
            },
            'last_month': {
                'label': _('Last month'),
                'domain': [
                    ('date_close', '>=', date_utils.start_of(last_month, 'month')),
                    ('date_close', '<=', date_utils.end_of(last_month, 'month'))
                ]
            },
            'last_year': {
                'label': _('Last year'),
                'domain': [
                    ('date_close', '>=', date_utils.start_of(last_year, 'year')),
                    ('date_close', '<=', date_utils.end_of(last_year, 'year'))
                ]
            },
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        if not filterby:
            filterby = 'my_appraisals'
        domain = AND([domain, searchbar_filters[filterby]['domain']])

        if search and search_in:
            search_domain = []
            if search_in in ('employee', 'all'):
                search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
            if search_in in ('my_appraisals', 'all'):
                search_domain = OR([search_domain, [('employee_id.name', 'ilike', search)]])
            if search_in in ('department', 'all'):
                search_domain = OR([search_domain, [('department_id.name', 'ilike', search)]])
            domain += search_domain

        appraisal = appraisal.sudo().search(domain, order=order)
        appraisal_count = len(appraisal)

        pager = portal_pager(
            url="/my/my_appraisals",
            url_args={'sortby': sortby, 'search_in': search_in, 'search': search, 'filterby': filterby},
            total=appraisal_count,
            page=page,
            step=self._items_per_page,
        )

        appraisal = appraisal.sudo().search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        appraisal_count = len(appraisal)

        request.session['my_appraisal_history'] = appraisal.ids[:100]

        values = {
            'appraisal_requests': appraisal,
            'page_name': 'my_appraisals',
            'pager': pager,
            'default_url': '/my/my_appraisals',
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

        return request.render("employee_hr_portal.portal_my_appraisals", values)

    @http.route(['/create/appraisal'], type='http', auth="user", website=True, csrf=False)
    def create_appraisal_request(self, **post):
        appraisal = request.env['hr.appraisal'].sudo()
        redirect = ("/create/my_appraisals")
        try:
            date_close = datetime.strptime(post['date_close'], '%Y-%m-%d')
            manager = int(post['manager'])
            appraisal_employee_feedback = post['appraisal_employee_feedback']
            employee_id = request.env.user.sudo().employee_id.id

            existing_request = appraisal.search([
                ('employee_id', '=', employee_id),
                ('date_close', '=', date_close),
            ], limit=1)

            if existing_request:
                error_msg = "You already have an appraisal request for this date."
                return request.redirect("%s?error_msg=%s" % (redirect, error_msg))

            vals_to_pass = {
                'date_close': date_close,
                'manager_ids': [(manager)],
                'employee_id': employee_id,
                'employee_feedback': appraisal_employee_feedback.replace("\n", '<br/>'),
                'company_id': request.env.user.company_id.id,
            }

            appraisal = appraisal.sudo().create(vals_to_pass)
            _logger.info(_('Successfully Updated appraisal: %s' % request.env.user.name))

            if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
                return request.redirect("/my/my_appraisals")
            else:
                return request.redirect('/my')
        except Exception as e:
            request.env.cr.rollback()
            return request.redirect("%s?error_msg=%s" % (redirect, e))

    @http.route(['/create/my_appraisals'], type='http', auth="public", website=True, csrf=False)
    def portal_create_my_appraisal(self, **kw):
        appraisal = request.env['hr.appraisal'].sudo()
        redirect = ("/my/my_appraisals")
        employee_feedback = request.env.user.company_id.sudo().appraisal_employee_feedback_template or '''<p><b>Does my company recognize my value ?</b></p><p><br><br></p>
	<p><b>What are the elements that would have the best impact on my work performance?</b></p><p><br><br></p>
	<p><b>What are my best achievement(s) since my last appraisal?</b></p><p><br><br></p>
	<p><b>What do I like / dislike about my job, the company or the management?</b></p><p><br><br></p>
	<p><b>How can I improve (skills, attitude, etc)?</b></p><p><br><br></p>'''
        try:
            if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
                return request.render("employee_hr_portal.portal_my_appraisal_create",
                                      {'text_from_html': self.text_from_html, 'employee_feedback': employee_feedback,
                                       'page_name': 'my_appraisals_create'})
            else:
                return request.redirect('/my')
        except Exception as e:
            return request.redirect("%s?error_msg=%s" % (redirect, e))

    @http.route(['/my/appraisal/<int:appraisal_id>'], type='http', auth="user", website=True, csrf=False)
    def portal_my_appraisal(self, appraisal_id=None, access_token=None, **kw):
        appraisal = request.env['hr.appraisal'].sudo().search([('id', '=', int(appraisal_id))])
        redirect = ("/my/my_appraisals")
        values = {
            'page_name': 'my_appraisals',
            'appraisal': appraisal,
            'no_breadcrumbs': False
        }
        values = self._get_page_view_values(appraisal, access_token, values, 'my_appraisal_history', False, **kw)
        history = request.session.get('my_appraisal_history', [])
        current_task_index = history.index(appraisal.id)
        total_orders = len(history)
        values['text_from_html'] = self.text_from_html
        try:
            prev_record = "/my/appraisal/{0}".format(str(history[current_task_index - 1]))
            values['prev_record'] = current_task_index != 0 and prev_record
        except:
            pass
        try:
            next_record = "/my/appraisal/{0}".format(str(history[current_task_index + 1]))
            values['next_record'] = current_task_index < total_orders - 1 and next_record
        except:
            pass
        if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
            return request.render("employee_hr_portal.portal_my_appraisal", values)
        else:
            return request.redirect('/my')

    @http.route(['/my/appraisal/delete/<int:appraisal_id>'], type='http', auth="user", website=True)
    def portal_unlink_appraisal(self, appraisal_id=None, access_token=None, **kw):
        appraisal = request.env['hr.appraisal'].sudo().search([('id', '=', int(appraisal_id))])
        redirect = '/my/my_appraisals'
        try:
            if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
                appraisal_sudo = appraisal
                if appraisal_sudo:
                    appraisal_sudo.unlink()
                return request.redirect(redirect)
            else:
                return request.redirect('/my')
        except Exception as e:
            return request.redirect("%s?error_msg=%s" % (redirect, e))

    @http.route(['/appraisal/update/<model("hr.appraisal"):appraisal_id>'], type='http', auth="user", methods=['POST'],
                website=True, csrf=False)
    def update_appraisal(self, appraisal_id, access_token=None, **post):
        appraisal = request.env['hr.appraisal'].sudo()
        redirect = ("/my/appraisal/%s" % appraisal_id.sudo().id)
        try:
            date_close = datetime.strptime(post['date_close'], '%Y-%m-%d')
            manager = int(post['manager'])
            appraisal_employee_feedback = post['appraisal_employee_feedback']
            employee_id = appraisal_id.sudo().employee_id.id

            existing_request = appraisal.search([
                ('employee_id', '=', employee_id),
                ('date_close', '=', date_close),
                ('id', '!=', appraisal_id.sudo().id),
            ], limit=1)

            if existing_request:
                error_msg = "You already have an appraisal request for this date."
                return request.redirect("%s?error_msg=%s" % (redirect, error_msg))

            vals_to_pass = {
                'date_close': date_close,
                'manager_ids': [(manager)],
                'employee_feedback': appraisal_employee_feedback.replace("\n", '<br/>'),
            }

            appraisal_id = appraisal_id.sudo().write(vals_to_pass)
            _logger.info(_('Successfully Updated appraisal: %s' % request.env.user.name))

            if request.env.user.has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
                return request.redirect("/my/my_appraisals")
            else:
                return request.redirect('/my')

        except Exception as e:
            request.env.cr.rollback()
            return request.redirect("%s?error_msg=%s" % (redirect, e))