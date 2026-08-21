# -*- coding: utf-8 -*-
from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers import portal
from datetime import datetime, time, timedelta
import pytz
import logging

_logger = logging.getLogger(__name__)


class EmployeeCheckinCheckoutPortal(portal.CustomerPortal):
    def _get_employee_tz_datetime(self, employee, user):
        tz_name = employee.tz or user.tz or 'UTC'
        tz = pytz.timezone(tz_name)
        utc_now = fields.Datetime.now()
        utc_time = pytz.utc.localize(utc_now)
        return utc_time.astimezone(tz)

    def _get_employee_tz_date_range(self, employee, user):
        employee_now = self._get_employee_tz_datetime(employee, user)
        employee_date = employee_now.date()
        start_of_day = datetime.combine(employee_date, time.min)
        end_of_day = datetime.combine(employee_date, time.max)
        tz = pytz.timezone(employee.tz or user.tz or 'UTC')
        start_of_day = tz.localize(start_of_day)
        end_of_day = tz.localize(end_of_day)
        start_utc = start_of_day.astimezone(pytz.utc)
        end_utc = end_of_day.astimezone(pytz.utc)
        return start_utc, end_utc

    @http.route(['/my/checkin_checkout'], type='http', auth="user", website=True)
    def portal_checkin_checkout_page(self, **kw):
        if not request.env.user.sudo().has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
            return request.not_found()
        user = request.env.user
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not employee:
            return request.render("employee_hr_portal.checkin_checkout_no_employee")
        if not employee.allow_checkin_checkout:
            return request.render("employee_hr_portal.checkin_checkout_not_allowed")

        start_utc, end_utc = self._get_employee_tz_date_range(employee, user)

        # Check for open attendance (checked in but not out)
        open_attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
        ], limit=1, order='check_in desc')

        # Check if employee has any attendance record for today (both check-in and check-out)
        has_attendance_today = request.env['hr.attendance'].sudo().search_count([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
        ]) > 0

        values = {
            'page_name': 'checkin_checkout',
            'employee': employee,
            'open_attendance': open_attendance,
            'has_attendance_today': has_attendance_today,
        }
        return request.render("employee_hr_portal.portal_checkin_checkout", values)

    @http.route(['/my/attendance/checkin'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_attendance_checkin(self, **kw):
        """Handle employee check-in - Only allows one check-in per day"""
        user = request.env.user
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not employee:
            return request.redirect('/my/checkin_checkout?error=no_employee')
        if not employee.allow_checkin_checkout:
            return request.redirect('/my/checkin_checkout?error=not_allowed')

        # Get today's date range in UTC based on employee's timezone
        start_utc, end_utc = self._get_employee_tz_date_range(employee, user)

        # Check if already checked in today
        open_attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
        ], limit=1)
        if open_attendance:
            return request.redirect('/my/checkin_checkout?error=already_checkedin')

        # Check if already completed attendance for today (both check-in and check-out)
        completed_attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
            ('check_out', '!=', False),
        ], limit=1)
        if completed_attendance:
            return request.redirect('/my/checkin_checkout?error=already_completed')

        # Get current datetime in UTC
        current_datetime = fields.Datetime.now()

        # Create attendance record
        try:
            attendance_vals = {
                'employee_id': employee.id,
                'check_in': current_datetime,
            }
            attendance = request.env['hr.attendance'].sudo().create(attendance_vals)
            _logger.info(f'Employee {employee.name} checked in at {current_datetime}. Attendance ID: {attendance.id}')
            return request.redirect('/my/checkin_checkout?success=checkedin')
        except Exception as e:
            _logger.error(f'Error creating attendance for employee {employee.name}: {str(e)}')
            return request.redirect('/my/checkin_checkout?error=system_error')

    @http.route(['/my/attendance/checkout'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_attendance_checkout(self, **kw):
        user = request.env.user
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not employee:
            return request.redirect('/my/checkin_checkout?error=no_employee')
        if not employee.allow_checkin_checkout:
            return request.redirect('/my/checkin_checkout?error=not_allowed')

        start_utc, end_utc = self._get_employee_tz_date_range(employee, user)
        open_attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
        ], limit=1, order='check_in desc')

        if not open_attendance:
            open_attendance = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False),
            ], limit=1, order='check_in desc')
            if not open_attendance:
                return request.redirect('/my/checkin_checkout?error=no_checkin')

        current_datetime = fields.Datetime.now()
        try:
            attendance_record = open_attendance.sudo()
            attendance_record.write({
                'check_out': current_datetime
            })
            _logger.info(
                f'Employee {employee.name} checked out at {current_datetime}. Attendance ID: {open_attendance.id}')
            return request.redirect('/my/checkin_checkout?success=checkedout')
        except Exception as e:
            _logger.error(f'Error updating attendance for employee {employee.name}: {str(e)}')
            return request.redirect('/my/checkin_checkout?error=system_error')

    @http.route(['/my/employee_checkin_status'], type='http', auth="user", website=True)
    def employee_checkin_status(self, **kw):
        """Display employee check-in status - Shows only today's status"""
        if not request.env.user.sudo().has_group('employee_hr_portal.access_to_employee_portal_custom_user'):
            return request.not_found()
        user = request.env.user
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not employee:
            return request.render("employee_hr_portal.checkin_checkout_no_employee")
        if not employee.allow_checkin_checkout:
            return request.render("employee_hr_portal.checkin_checkout_not_allowed")

        start_utc, end_utc = self._get_employee_tz_date_range(employee, user)
        open_attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
        ], limit=1, order='check_in desc')

        status = "Checked Out"
        check_in_time = False
        if open_attendance:
            status = "Checked In"
            check_in_time = open_attendance.check_in

        values = {
            'page_name': 'checkin_status',
            'employee': employee,
            'status': status,
            'check_in_time': check_in_time,
        }
        return request.render("employee_hr_portal.employee_checkin_status_template", values)

    @http.route(['/my/attendance/today'], type='json', auth="user", website=True)
    def get_today_attendance(self, **kw):
        """Get today's attendance data for AJAX calls - Returns only today's records"""
        user = request.env.user
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not employee:
            return {'error': 'No employee found'}

        # Get today's date range in UTC based on employee's timezone
        start_utc, end_utc = self._get_employee_tz_date_range(employee, user)

        # Get today's attendance records only
        today_attendances = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
        ], order='check_in desc')

        attendance_data = []
        for att in today_attendances:
            attendance_data.append({
                'id': att.id,
                'check_in': att.check_in.strftime('%Y-%m-%d %H:%M:%S') if att.check_in else False,
                'check_out': att.check_out.strftime('%Y-%m-%d %H:%M:%S') if att.check_out else False,
                'worked_hours': att.worked_hours,
            })

        return {
            'employee_name': employee.name,
            'today_attendances': attendance_data,
            'current_status': 'checked_in' if today_attendances and not today_attendances[
                0].check_out else 'checked_out'
        }