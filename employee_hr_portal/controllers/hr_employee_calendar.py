from odoo import http
from odoo.http import request
from datetime import datetime, date, timedelta
import json
import calendar
from odoo.tools.image import image_data_uri

class AttendanceDashboardController(http.Controller):

	@http.route('/attendance/get_month_data', type='json', auth='user', methods=['POST'])
	def get_month_data(self, **kwargs):
		try:
			data = json.loads(request.httprequest.data)
			year = int(data.get('year'))
			month = int(data.get('month'))
			try:
				employee_id = int(data.get('employee_id'))
			except:
				employee_id = 0
			# today = date.today()
			today = (datetime.today() + timedelta(hours=5)).date()
			
			# Get current employee
			if employee_id:
				employee = request.env['hr.employee'].sudo().browse(employee_id)
			else:
				employee = request.env.user.employee_id.sudo()
			if not employee:
				return {'success': False, 'error': 'No employee associated with this user'}
			
			# Get current contract
			contract = employee.contract_id
			if not contract:
				return {'success': False, 'error': 'No active contract found'}
			
			# Get work schedule from contract
			work_schedule = contract.resource_calendar_id.sudo()
			if not work_schedule:
				return {'success': False, 'error': 'No work schedule defined in contract'}
			
			# Date range for the month
			month_start = date(year, month, 1)
			month_end = date(year, month, calendar.monthrange(year, month)[1])
			
			# Get all attendance records
			attendances = request.env['hr.attendance'].sudo().search([
				('employee_id', '=', employee.id),
				('check_in', '>=', month_start.strftime('%Y-%m-%d 00:00:00')),
				('check_in', '<=', month_end.strftime('%Y-%m-%d 23:59:59'))
			])

			attendances_absents = request.env['hr.attendance.absents'].sudo().search([
				('employee_id', '=', employee.id),
				('time', '>=', month_start.strftime('%Y-%m-%d')),
				('time', '<=', month_end.strftime('%Y-%m-%d'))
			])
			
			# Get leaves
			hr_leaves = request.env['hr.leave'].sudo().search([
				('employee_id', '=', employee.id),
				('state', '=', 'validate'),
				('date_from', '<=', month_end),
				('date_to', '>=', month_start)
			])
			
			# Get calendar leaves
			calendar_leaves = request.env['resource.calendar.leaves'].sudo().search([
				'|',
				('calendar_id', '=', work_schedule.id),
				('calendar_id', '=', False),
				('date_from', '<=', month_end.strftime('%Y-%m-%d 23:59:59')),
				('date_to', '>=', month_start.strftime('%Y-%m-%d 00:00:00')),
				('resource_id', '=', False)
			])

			response_data = {}
			
			for day in range(1, calendar.monthrange(year, month)[1] + 1):
				current_date = date(year, month, day)
				date_key = f"{year}-{month}-{day}"
				weekday = current_date.weekday()
				
				# Check work schedule
				work_schedule_lines = work_schedule.attendance_ids.filtered(
					lambda x: int(x.dayofweek) == weekday
				)

				if not work_schedule_lines:
					response_data[date_key] = {
						'status': 'off',
						'display_status': 'OFF DUTY',
						'shift': work_schedule.name
					}
					continue
				
				# Check calendar leaves (public holidays)
				calendar_leave = None
				for leave in calendar_leaves:
					leave_date_from = (leave.date_from + timedelta(hours=5)).date()
					leave_date_to = (leave.date_to + timedelta(hours=5)).date()
					if leave_date_from <= current_date <= leave_date_to:
						calendar_leave = leave
						break

				if calendar_leave:
					response_data[date_key] = {
						'status': 'leave',
						'display_status': calendar_leave.name.upper() if calendar_leave.name else 'PUBLIC HOLIDAY',
						'leave_type': calendar_leave.name or 'Public Holiday',
						'shift': work_schedule.name
					}
					continue
				
				# Check HR leaves
				hr_leave = None
				for leave in hr_leaves:
					leave_date_from = (leave.date_from + timedelta(hours=5)).date()
					leave_date_to = (leave.date_to + timedelta(hours=5)).date()
					if leave_date_from <= current_date <= leave_date_to:
						hr_leave = leave
						break

				if hr_leave:
					response_data[date_key] = {
						'status': 'leave',
						'display_status': hr_leave.holiday_status_id.name.upper(),
						'leave_type': hr_leave.holiday_status_id.name,
						'shift': work_schedule.name
					}
					continue
				
				# Only check attendance for past/current dates
				if current_date > today:
					response_data[date_key] = {
						'status': 'future',
						'shift': work_schedule.name
					}
					continue
				
				# Check attendance
				attendance = None
				attendance_absent = None
				for att in attendances:
					if (att.check_in + timedelta(hours=5)).date() == current_date:
						attendance = att
						break

				if not attendance:
					if employee.isExecutive:
						response_data[date_key] = {
							'status': 'present',
							'display_status': 'ON DUTY (EXECUTIVE)',
							'timings': 'Auto Marked Present',
							'shift': work_schedule.name,
							'late_arrival': False,
							'early_left': False,
							'over_time': 0.0
						}
						continue
						
					for att in attendances_absents:
						if att.time == current_date:
							attendance_absent = att
							break
					if attendance_absent:
						response_data[date_key] = {
							'status': 'absent',
							'display_status': 'ABSENT',
							'shift': work_schedule.name
						}
						continue
					else:
						response_data[date_key] = {
							'status': 'no-record',
							'shift': work_schedule.name
						}
						continue
				
				# Format attendance data
				check_in = (attendance.check_in + timedelta(hours=5)).strftime('%H:%M')
				check_out = (attendance.check_out + timedelta(hours=5)).strftime('%H:%M') if attendance.check_out else None
				
				all_break_ins = []
				all_break_outs = []

				# Source 1: biometric device (breaks JSON field)
				raw_breaks = attendance.breaks
				if raw_breaks:
				    try:
				        pairs = json.loads(raw_breaks) if isinstance(raw_breaks, str) else raw_breaks
				        for pair in pairs:
				            bi = pair.get('break_in')
				            bo = pair.get('break_out')
				            if bi:
				                try:
				                    # parse time-only strings like "12:30" or datetime strings
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

				# Source 2: missing punch (break_ids One2many) - already in UTC, convert to local
				for br in attendance.break_ids:
				    if br.break_checkin:
				        all_break_ins.append(br.break_checkin.strftime('%H:%M'))
				    if br.break_checkout:
				        all_break_outs.append(br.break_checkout.strftime('%H:%M'))
				    if br.break_checkin2:
				        all_break_ins.append(br.break_checkin2.strftime('%H:%M'))
				    if br.break_checkout2:
				        all_break_outs.append(br.break_checkout2.strftime('%H:%M'))

				# Pick earliest of each
				earliest_break_in  = min(all_break_ins)  if all_break_ins  else None
				earliest_break_out = min(all_break_outs) if all_break_outs else None

				# Build display string
				break_parts = []
				if earliest_break_in:
				    break_parts.append(f"Break In: {earliest_break_in}")
				if earliest_break_out:
				    break_parts.append(f"Break Out: {earliest_break_out}")
				breaks_combined = '\n'.join(break_parts)

				response_data[date_key] = {
					'status': 'present',
					'display_status': 'ON DUTY',
					'timings': f"Check In: {check_in}" + (f" & Check Out: {check_out}" if check_out else ""),
					'shift': work_schedule.name,
					'late_arrival': attendance.late_arrival,
					'early_left': attendance.early_left,
					'over_time': attendance.over_time,
					'breaks': breaks_combined,          # single unified field
    				'missing_punch_breaks': '', 
				}

			job = employee.job_id.name if employee.job_id else 'N/A'
			response_data['employee'] = {'name':employee.name,'job_position': str(job) + ' | ' + str(request.env.company.name),'image':image_data_uri(employee.image_1920) if employee.image_1920 else False}
			
			return {'success': True, 'data': response_data}
			
		except Exception as e:
			return {'success': False, 'error': str(e)}


	@http.route('/attendance/get_attendance_employees', type='json', auth='user', methods=['POST'])
	def get_attendance_employees(self, **kwargs):
		try:
			employees = request.env['hr.employee'].sudo().search([])
			current_employee = request.env.user.employee_id
			employee_list = []
			for emp in employees:
				employee_list.append({
					'id': emp.id,
					'name': emp.name,
					'is_current_user': emp.id == current_employee.id
				})
			return {'success': True, 'employees': employee_list}
		except Exception as e:
			return {'success': False, 'error': str(e)}