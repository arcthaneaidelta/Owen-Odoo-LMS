# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
from werkzeug.exceptions import Forbidden


def _is_in_group(user, *group_xmlids):
    """Check if a user belongs to any of the given groups."""
    for xmlid in group_xmlids:
        group = request.env.ref(xmlid, raise_if_not_found=False)
        if group and user.has_group(xmlid):
            return True
    return False


ADMIN_GROUPS = [
    'university_core.group_university_super_admin',
    'university_core.group_university_manager',
    'university_core.group_academic_coordinator',
]

DAYS_ORDER = ['0', '1', '2', '3', '4', '5', '6']
DAY_LABELS = {
    '0': 'Monday', '1': 'Tuesday', '2': 'Wednesday',
    '3': 'Thursday', '4': 'Friday', '5': 'Saturday', '6': 'Sunday',
}


def _build_grid(sessions):
    grid = {d: [] for d in DAYS_ORDER}
    for s in sessions:
        grid[s.day_of_week].append(s)
    return grid


class TimetablePortal(http.Controller):

    # ─── Student Portal: /my/schedule ─────────────────────────────────────────

    @http.route('/my/schedule', type='http', auth='user', website=True)
    def student_schedule(self, **kwargs):
        """Personal class schedule — PORTAL STUDENTS ONLY."""
        user = request.env.user
        # Block non-portal users (internal backend users without student group)
        is_student = user.has_group('university_core.group_student_portal') or user.has_group('base.group_portal')
        if not is_student:
            return request.render('http_routing.404')

        # Find the linked student record
        student = request.env['university.student'].sudo().search([
            ('partner_id', '=', user.partner_id.id),
        ], limit=1)
        if not student and user.email:
            student = request.env['university.student'].sudo().search([
                ('email', '=', user.email),
            ], limit=1)

        sessions = []
        if student and student.batch_id:
            sessions = request.env['university.timetable'].sudo().search([
                ('batch_id', '=', student.batch_id.id),
                ('state', '=', 'published'),
            ], order='day_of_week, start_time')

        return request.render('university_curriculum.portal_student_schedule', {
            'student': student,
            'sessions': sessions,
            'grid': _build_grid(sessions),
            'day_labels': DAY_LABELS,
            'days_order': DAYS_ORDER,
            'page_name': 'My Class Schedule',
        })

    # ─── Teacher Portal: /my/timetable ────────────────────────────────────────

    @http.route('/my/timetable', type='http', auth='user', website=True)
    def teacher_timetable(self, **kwargs):
        """Teaching schedule. Teachers see their own; admins see all teachers."""
        user = request.env.user
        is_admin = any(user.has_group(g) for g in ADMIN_GROUPS)
        is_teacher = user.has_group('university_core.group_teacher')

        if not is_teacher and not is_admin:
            return request.render('http_routing.404')

        if is_admin:
            # Admin/Manager view: show a list of all teachers to browse
            # Teachers are identified by the university_core.group_teacher security group
            teacher_group = request.env.ref('university_core.group_teacher', raise_if_not_found=False)
            teacher_user_ids = teacher_group.users.ids if teacher_group else []
            all_teachers = request.env['hr.employee'].sudo().search([
                ('user_id', 'in', teacher_user_ids)
            ], order='name')
            return request.render('university_curriculum.portal_admin_teacher_list', {
                'all_teachers': all_teachers,
                'page_name': 'All Teachers\' Schedules',
                'is_admin': True,
            })

        # Teacher personal view — find the employee linked to this user
        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', user.id),
        ], limit=1)

        sessions = []
        if employee:
            sessions = request.env['university.timetable'].sudo().search([
                ('teacher_id', '=', employee.id),
                ('state', '=', 'published'),
            ], order='day_of_week, start_time')

        return request.render('university_curriculum.portal_teacher_timetable', {
            'employee': employee,
            'sessions': sessions,
            'grid': _build_grid(sessions),
            'day_labels': DAY_LABELS,
            'days_order': DAYS_ORDER,
            'page_name': 'My Teaching Schedule',
            'is_admin': False,
        })

    @http.route('/my/timetable/<int:teacher_id>', type='http', auth='user', website=True)
    def teacher_timetable_by_id(self, teacher_id, **kwargs):
        """Admin/manager view of a specific teacher's schedule."""
        user = request.env.user
        is_admin = any(user.has_group(g) for g in ADMIN_GROUPS)
        is_same_teacher = False

        if not is_admin:
            # Allow a teacher (by group) to view their own page via this URL too
            employee_self = request.env['hr.employee'].sudo().search([
                ('user_id', '=', user.id),
            ], limit=1)
            is_same_teacher = employee_self and employee_self.id == teacher_id

        if not is_admin and not is_same_teacher:
            return request.render('http_routing.404')

        employee = request.env['hr.employee'].sudo().browse(teacher_id)
        if not employee.exists():
            return request.render('http_routing.404')
        # Verify the target employee belongs to the teacher group
        teacher_group = request.env.ref('university_core.group_teacher', raise_if_not_found=False)
        if teacher_group and employee.user_id not in teacher_group.users:
            return request.render('http_routing.404')

        sessions = request.env['university.timetable'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'published'),
        ], order='day_of_week, start_time')

        return request.render('university_curriculum.portal_teacher_timetable', {
            'employee': employee,
            'sessions': sessions,
            'grid': _build_grid(sessions),
            'day_labels': DAY_LABELS,
            'days_order': DAYS_ORDER,
            'page_name': f'{employee.name}\'s Teaching Schedule',
            'is_admin': is_admin,
        })

    # ─── Room/Admin Portal ────────────────────────────────────────────────────

    @http.route('/schedule/rooms', type='http', auth='user', website=True)
    def room_occupancy(self, room_id=None, **kwargs):
        """Room occupancy view — admin/manager only."""
        user = request.env.user
        is_admin = any(user.has_group(g) for g in ADMIN_GROUPS) or user.has_group('university_core.group_teacher')
        if not is_admin:
            return request.render('http_routing.404')

        rooms = request.env['university.room'].sudo().search([('is_active', '=', True)])
        selected_room = None
        sessions = []

        if room_id:
            selected_room = request.env['university.room'].sudo().browse(int(room_id))
            sessions = request.env['university.timetable'].sudo().search([
                ('room_id', '=', selected_room.id),
                ('state', '=', 'published'),
            ], order='day_of_week, start_time')

        return request.render('university_curriculum.portal_room_occupancy', {
            'rooms': rooms,
            'selected_room': selected_room,
            'sessions': sessions,
            'grid': _build_grid(sessions),
            'day_labels': DAY_LABELS,
            'days_order': DAYS_ORDER,
            'page_name': 'Room Occupancy',
        })
