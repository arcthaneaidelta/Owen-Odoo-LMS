from odoo import models, fields, api, _
from datetime import timedelta, datetime
import pytz
from dateutil.relativedelta import relativedelta
from odoo.exceptions import AccessError, UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    over_time = fields.Float(string="Overtime", tracking=True, compute="_compute_overtime")
    early_left = fields.Float(string="Early Left", tracking=True, compute="_compute_overtime")
    late_arrival = fields.Float(string="Late Arrival", tracking=True, compute="_compute_overtime")
    badge_id = fields.Char(related='employee_id.barcode', string='Badge ID', readonly=True)
    total_late_arrival = fields.Float(
        string="Total Late Arrival (Minutes)",
        compute="_compute_total_late_arrival",
    )
    employee_id = fields.Many2one('hr.employee', string='Employee', tracking=True, copy=False)
    unauthorized_leave = fields.Integer(
        string='Unauthorized Leave Days',
        compute='_compute_unauthorized_leave',
        store=True
    )
    late_days = fields.Integer(
        string='Late Arrival Days',
        compute='_compute_late_days',
    )
    break_ids = fields.One2many('employee.break', 'attendance_id', string="Break Logs")
    break_display = fields.Char(
        string="Break Time",
        compute="_compute_break_display",
        store=False
    )

    def _compute_break_display(self):
        for rec in self:
            lines = []
            for br in rec.break_ids:
                if br.break_checkin:
                    lines.append(f"Break In: {br.break_checkin.strftime('%H:%M')}")
                if br.break_checkout:
                    lines.append(f"Break Out: {br.break_checkout.strftime('%H:%M')}")

                if br.break_checkin2:
                    lines.append(f"Break In: {br.break_checkin2.strftime('%H:%M')}")
                if br.break_checkout2:
                    lines.append(f"Break Out: {br.break_checkout2.strftime('%H:%M')}")

            rec.break_display = "\n".join(lines) if lines else "-"

    @api.model
    def search(self, args=None, offset=0, limit=None, order=None):
        current_user = self.env.user
        domain = []
        if not current_user.has_group('employee_attendance.show_all_attendance'):
            domain = ['|',
                ('employee_id.user_id', '=', current_user.id),
                ('employee_id.parent_id.user_id', '=', current_user.id)
            ]
        if args:
            domain = ['&'] + domain + args if domain else args
        return super(HrAttendance, self).search(domain, offset=offset, limit=limit, order=order)

    @api.depends('late_arrival')
    def _compute_late_days(self):
        for record in self:
            record.late_days = 1 if record.late_arrival > 0 else 0

    @api.depends('check_in', 'check_out', 'employee_id.resource_calendar_id')
    def _compute_unauthorized_leave(self):
        for attendance in self:
            attendance.unauthorized_leave = 0
            if not attendance.employee_id.resource_calendar_id:
                continue
            date = attendance.check_in and fields.Date.to_date(attendance.check_in)
            if not date:
                continue
            weekday = str(date.weekday())
            calendar = attendance.employee_id.resource_calendar_id
            try:
                is_working_day = self.env['resource.calendar.attendance'].search_count([
                    ('calendar_id', '=', calendar.id),
                    ('dayofweek', '=', weekday)
                ]) > 0
            except Exception as e:
                _logger.error(f"Error checking working day: {e}")
                is_working_day = False
            if is_working_day and not attendance.check_out:
                start_of_day = fields.Datetime.to_datetime(date)
                time_diff = attendance.check_in - start_of_day
                if time_diff <= timedelta(minutes=5):
                    attendance.unauthorized_leave = 1

    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        if not self.env.context.get('synch_ignore_constraints', False):
            super(HrAttendance, self)._check_validity()


    def _time_to_float(self, dt):
        if not dt:
            return 0.0
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        local_dt = dt.replace(tzinfo=pytz.UTC).astimezone(tz)
        return local_dt.hour + local_dt.minute / 60.0

    def _dt_to_float(self, dt):
        if not dt:
            return 0.0
        return dt.hour + dt.minute / 60.0

    @api.depends(
        'check_in', 'check_out', 'employee_id',
        'break_ids.break_checkin', 'break_ids.break_checkout',
        'break_ids.break_checkin2', 'break_ids.break_checkout2'
    )
    def _compute_overtime(self):
        for rec in self:
            portal_overtime_requests = self.env['hr.overtime.requests'].sudo().search([
                ('employee_id', '=', rec.employee_id.id),
                ('requested_date', '=', rec.check_in.date()),
                ('state', 'in', ['approve', 'attendance_updated'])
            ], limit=1)
            if portal_overtime_requests:
                portal_overtime_requests.state = 'attendance_updated'
                rec.over_time = rec.early_left = rec.late_arrival = 0.0
                continue

            overtime = early_left = late_arrival = 0.0
            employee = rec.employee_id
            group = employee.employee_group_id

            if not (rec.check_in and rec.check_out and employee and group):
                rec.over_time = rec.early_left = rec.late_arrival = 0.0
                continue

            check_in_time = rec._time_to_float(rec.check_in)
            check_out_time = rec._time_to_float(rec.check_out)

            weekday = str(rec.check_in.weekday())

            calendar = employee.resource_calendar_id
            if calendar:
                main_attendances = self.env['resource.calendar.attendance'].search([
                    ('calendar_id', '=', calendar.id),
                    ('dayofweek', '=', weekday),
                    ('day_period', 'not in', ['break1', 'break2'])
                ]).sorted('hour_from')

                if main_attendances:
                    first = main_attendances[0]
                    last = main_attendances[-1]

                    if check_in_time > first.hour_from:
                        late_arrival += (check_in_time - first.hour_from)

                    if check_out_time > last.hour_to:
                        overtime += (check_out_time - last.hour_to)
                    elif check_out_time < last.hour_to:
                        early_left += (last.hour_to - check_out_time)

            for br in rec.break_ids:
                if br.break_slot == '1':
                    _logger.error(f"Slot: {br.break_slot}")
                    if br.break_checkin and group.break_checkin:
                        actual_in = rec._dt_to_float(br.break_checkin)
                        sch_in = group.break_checkin
                        if actual_in > 0 and sch_in > 0 and sch_in <= 24:
                            diff = actual_in - sch_in
                            _logger.error(f"check_in: {diff}")
                            if diff < 0:
                                early_left += abs(diff)
                                _logger.error(f"check_in early_left: {early_left}")

                    if br.break_checkout and group.break_checkout:
                        actual_out = rec._dt_to_float(br.break_checkout)
                        sch_out = group.break_checkout
                        if actual_out > 0 and sch_out > 0 and sch_out <= 24:
                            diff = actual_out - sch_out
                            _logger.error(f"check_out: {diff}")
                            if diff > 0:
                                late_arrival += diff
                                _logger.error(f"check_out late: {late_arrival}")
                            elif diff < 0:
                                early_left += abs(diff)
                                _logger.error(f"check_out early_left: {early_left}")


                elif br.break_slot == '2':
                    _logger.error(f"Slot: {br.break_slot}")
                    if br.break_checkin and group.break_checkin2:
                        actual_in = rec._dt_to_float(br.break_checkin)
                        sch_in = group.break_checkin2
                        if actual_in > 0 and sch_in > 0 and sch_in <= 24:
                            diff = actual_in - sch_in
                            _logger.error(f"check_in2: {diff}")
                            if diff < 0:
                                early_left += abs(diff)
                                _logger.error(f"check_in2: {early_left}")

                    if br.break_checkout and group.break_checkout2:
                        actual_out = rec._dt_to_float(br.break_checkout)
                        sch_out = group.break_checkout2
                        if actual_out > 0 and sch_out > 0 and sch_out <= 24:
                            diff = actual_out - sch_out
                            _logger.error(f"check_in2: {diff}")
                            if diff > 0:
                                late_arrival += diff
                                _logger.error(f"check_out2: {late_arrival}")
                            elif diff < 0:
                                early_left += abs(diff)
                                _logger.error(f"check_out2: {early_left}")

            rec.late_arrival = round(late_arrival, 2)
            rec.early_left = round(early_left, 2)
            rec.over_time = round(overtime, 2)

    @api.depends("late_arrival")
    def _compute_total_late_arrival(self):
        for employee in self:
            employee.total_late_arrival = round(employee.late_arrival * 60, 0)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    isExecutive = fields.Boolean('Is Executive', default=False, track_visibility=True)
    give_pension = fields.Boolean(string="Give Pension", default=False, track_visibility=True)
    employee_group_id = fields.Many2one('employee.group', string="Employee Group", track_visibility=True)
    missing_punch_approver_id = fields.Many2one('hr.employee', string='Missing Punch Approver')
    # expense_manager_id = fields.Many2one(
    #     'res.users', string='Expense',
    #     domain=_group_hr_expense_user_domain,
    #     compute='_compute_expense_manager', track_visibility=True, store=True, readonly=False,
    #     help='Select the user responsible for approving "Expenses" of this employee.\n'
    #          'If empty, the approval is done by an Administrator or Approver (determined in settings/users).')
    parent_id = fields.Many2one('hr.employee', 'Manager', compute="_compute_parent_id", store=True, track_visibility=True, readonly=False,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    coach_id = fields.Many2one(
        'hr.employee', 'Coach', compute='_compute_coach', store=True, track_visibility=True, readonly=False,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Select the "Employee" who is the coach of this employee.\n'
             'The "Coach" has no specific rights or responsibilities by default.')
    work_location_id = fields.Many2one('hr.work.location', 'Work Location', compute="_compute_work_location_id", track_visibility=True, store=True, readonly=False,
    domain="[('address_id', '=', address_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    resource_calendar_id = fields.Many2one('resource.calendar', track_visibility=True, domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    tz = fields.Selection(
        string='Timezone', related='resource_id.tz', track_visibility=True, readonly=False,
        help="This field is used in order to define in which timezone the resources will work.")

    timesheet_manager_id = fields.Many2one('res.users', track_visibility=True,  string='Timesheet',
        help="User responsible of timesheet validation. Should be Timesheet Manager.")



class EmployeeGroup(models.Model):
    _name = 'employee.group'
    _description = 'Employee Group'
    _rec_name = "name"

    name = fields.Char(string="Group Name")
    break_type = fields.Selection([('1', '1'), ('2', '2')], string="Break Schedule")
    break_checkin = fields.Float(string="Break Check-In")
    break_checkout = fields.Float(string="Break Check-Out")
    break_checkin2 = fields.Float(string="Break Check-In 2")
    break_checkout2 = fields.Float(string="Break Check-Out 2")

    @api.constrains('break_checkout', 'break_checkout2')
    def _check_break_times(self):
        for rec in self:
            if rec.break_checkout and (rec.break_checkout < 0 or rec.break_checkout > 24):
                raise ValidationError(_("Break Check-Out must be between 00:00 and 24:00"))
            if rec.break_checkout2 and (rec.break_checkout2 < 0 or rec.break_checkout2 > 24):
                raise ValidationError(_("Break Check-Out 2 must be between 00:00 and 24:00"))


class EmployeeBreak(models.Model):
    _name = 'employee.break'
    _description = 'Employee Break'
    _rec_name = "employee_id"

    employee_id = fields.Many2one('hr.employee', string="Employee")
    attendance_id = fields.Many2one('hr.attendance', string="Attendance Record")
    break_slot = fields.Selection([('1', 'Break 1'), ('2', 'Break 2')], string="Break Slot", required=True, default='1')
    break_checkin = fields.Datetime(string="Break Check-In")
    break_checkout = fields.Datetime(string="Break Check-Out")
    break_checkin2 = fields.Datetime(string="Break Check-In 2")
    break_checkout2 = fields.Datetime(string="Break Check-Out 2")


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    total_absences = fields.Integer('Unauthorized Absences', readonly=True)
    total_late_arrival = fields.Float('Late Arrival (Minutes)', readonly=True)
    late_days = fields.Integer('Late Arrival Days', readonly=True)
    total_overall_absences = fields.Float('Total Absences', readonly=True)
    emergency_leave_days = fields.Integer('Emergency Leave Days', readonly=True)

    date_from = fields.Date(string='From', readonly=False, required=True,
        default=lambda self: fields.Date.to_string(fields.Date.today().replace(day=20)),
        states={'done': [('readonly', True)], 'paid': [('readonly', True)], 'cancel': [('readonly', True)]})
    date_to = fields.Date(string='To', readonly=False, required=True, precompute=True,
        compute="_compute_date_to", store=True,
        states={'done': [('readonly', True)], 'paid': [('readonly', True)], 'cancel': [('readonly', True)]})
    employee_id = fields.Many2one('hr.employee', string='Employee', tracking=True, copy=False)

    @api.model
    def search(self, args=None, offset=0, limit=None, order=None):
        current_user = self.env.user
        domain = []
        if not current_user.has_group('employee_attendance.show_all_payslip'):
            domain = [('employee_id.parent_id.user_id', '=', current_user.id)]
        if args:
            domain = ['&'] + domain + args if domain else args
        return super(HrPayslip, self).search(domain, offset=offset, limit=limit, order=order)

    @api.depends('date_from')
    def _compute_date_to(self):
        for payslip in self:
            if payslip.date_from:
                payslip.date_to = payslip.date_from + relativedelta(months=+1, day=19)
            else:
                payslip.date_to = False

    def _get_or_create_unauth_leave_type(self):
        unauth_type = self.env['hr.work.entry.type'].search([('code', '=', 'UNAUTHLEAV')], limit=1)
        if not unauth_type:
            unauth_type = self.env['hr.work.entry.type'].create({
                'name': 'Unauthorized Leave', 'code': 'UNAUTHLEAV', 'is_leave': True
            })
        return unauth_type

    def _get_or_create_emergency_leave_type(self):
        emergency_type = self.env['hr.work.entry.type'].search([('code', '=', 'EMERGENCY')], limit=1)
        if not emergency_type:
            emergency_type = self.env['hr.work.entry.type'].create({
                'name': 'Emergency Leave', 'code': 'EMERGENCY', 'is_leave': True
            })
        return emergency_type

    def compute_sheet(self):
        for payslip in self:
            employee = payslip.employee_id
            contract = payslip.contract_id
            if not contract:
                continue
            calculated_total_absences = calculated_total_late_minutes = calculated_late_days = calculated_emergency_leaves = 0
            calendar = contract.resource_calendar_id
            if not calendar:
                continue
            current_date = payslip.date_from
            while current_date <= payslip.date_to:
                day_start_utc = pytz.utc.localize(datetime.combine(current_date, datetime.min.time()))
                day_end_utc = pytz.utc.localize(datetime.combine(current_date, datetime.max.time()))
                work_hours = calendar.get_work_hours_count(day_start_utc, day_end_utc, compute_leaves=False)
                if work_hours > 0:
                    attendance = self.env['hr.attendance'].search([
                        ('employee_id', '=', employee.id),
                        ('check_in', '>=', day_start_utc.replace(tzinfo=None)),
                        ('check_in', '<=', day_end_utc.replace(tzinfo=None))
                    ], order='check_in asc', limit=1)
                    valid_leave = self.env['hr.leave'].search([
                        ('employee_id', '=', employee.id),
                        ('date_from', '<=', day_end_utc.replace(tzinfo=None)),
                        ('date_to', '>=', day_start_utc.replace(tzinfo=None)),
                        ('state', '=', 'validate')
                    ], limit=1)
                    emergency_leave = False
                    if valid_leave:
                        emergency_leave = self.env['hr.leave'].search([
                            ('employee_id', '=', employee.id),
                            ('date_from', '<=', day_end_utc.replace(tzinfo=None)),
                            ('date_to', '>=', day_start_utc.replace(tzinfo=None)),
                            ('state', '=', 'validate'),
                            ('holiday_status_id.work_entry_type_id.code', '=', 'EMERGENCY')
                        ], limit=1)
                    if not attendance and not valid_leave and not employee.isExecutive:
                        calculated_total_absences += 1
                    elif emergency_leave:
                        calculated_emergency_leaves += 1
                    elif attendance:
                        late_hours = getattr(attendance, 'late_arrival', 0.0)
                        if late_hours > 0:
                            calculated_late_days += 1
                            calculated_total_late_minutes += late_hours * 60
                current_date += timedelta(days=1)

            net_unauthorized_absences = max(0, calculated_total_absences - calculated_emergency_leaves)
            self._update_unauth_leave_days(payslip, net_unauthorized_absences)
            self._update_emergency_leave_days(payslip, calculated_emergency_leaves)
            current_total_overall_absences = sum(
                line.number_of_days for line in payslip.worked_days_line_ids
                if line.work_entry_type_id and getattr(line.work_entry_type_id, 'is_leave', False)
            )
            payslip.write({
                'total_absences': net_unauthorized_absences,
                'total_late_arrival': calculated_total_late_minutes,
                'late_days': calculated_late_days,
                'emergency_leave_days': calculated_emergency_leaves,
                'total_overall_absences': current_total_overall_absences
            })
        return super(HrPayslip, self).compute_sheet()

    def _update_unauth_leave_days(self, payslip, days):
        unauth_type = self._get_or_create_unauth_leave_type()
        line = payslip.worked_days_line_ids.filtered(lambda l: l.work_entry_type_id == unauth_type)
        if line:
            line.write({'number_of_days': days})
        else:
            self.env['hr.payslip.worked_days'].create({
                'payslip_id': payslip.id,
                'name': 'Unauthorized Absences',
                'code': 'UNAUTHLEAV',
                'work_entry_type_id': unauth_type.id,
                'number_of_days': days,
            })

    def _update_emergency_leave_days(self, payslip, days):
        if days <= 0:
            return
        emergency_type = self._get_or_create_emergency_leave_type()
        line = payslip.worked_days_line_ids.filtered(lambda l: l.work_entry_type_id == emergency_type)
        if line:
            line.write({'number_of_days': days})
        else:
            self.env['hr.payslip.worked_days'].create({
                'payslip_id': payslip.id,
                'name': 'Emergency Leaves',
                'code': 'EMERGENCY',
                'work_entry_type_id': emergency_type.id,
                'number_of_days': days,
            })

    def _get_payslip_lines(self):
        lines = super()._get_payslip_lines()
        for line in lines:
            if line.get('code') == 'LATE':
                line['amount'] = self.total_late_arrival
        return lines


class HrLeaveAllocatoin(models.Model):
    _inherit = 'hr.leave.allocation'

    @api.model
    def search(self, args=None, offset=0, limit=None, order=None):
        current_user = self.env.user
        domain = []
        if not current_user.has_group('employee_attendance.show_all_leave_allocation'):
            domain = ['|',
                ('employee_id.user_id', '=', current_user.id),
                ('employee_id.parent_id.user_id', '=', current_user.id)
            ]
        if args:
            domain = ['&'] + domain + args if domain else args
        return super(HrLeaveAllocatoin, self).search(domain, offset=offset, limit=limit, order=order)


class HrContract(models.Model):
    _inherit = 'hr.contract'
    break_hours = fields.Float(string="Break Hours per Day", default=1.5)

