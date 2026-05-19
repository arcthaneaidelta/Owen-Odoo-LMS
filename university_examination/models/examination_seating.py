from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ExaminationRoom(models.Model):
    _name = 'examination.room'
    _description = 'Examination Room'

    name = fields.Char(string='Room Name', required=True)
    capacity = fields.Integer(string='Capacity', default=30, required=True)

class ExaminationSeating(models.Model):
    _name = 'examination.seating'
    _description = 'Examination Seating'
    _rec_name = 'subject_id'

    cycle_id = fields.Many2one('examination.cycle', string='Cycle', required=True)
    subject_id = fields.Many2one('university.subject', string='Subject', required=True)
    exam_date = fields.Date(string='Examination Date', required=True)
    start_time = fields.Float(string='Start Time', required=True, help="Time in 24h float format.")
    end_time = fields.Float(string='End Time', required=True)
    seating_line_ids = fields.One2many('examination.seating.line', 'seating_id', string='Seating Lines')

    room_ids = fields.Many2many('examination.room', string='Rooms')

    def generate_seating(self):
        for record in self:
            if not record.room_ids:
                raise ValidationError(_("Please select at least one room."))
                
            # 1. Find students taking this subject
            students_to_seat = []
            students = self.env['university.student'].search([('registration_status', '=', 'registered')])
            for student in students:
                if not student.batch_id or not student.batch_id.curriculum_id:
                    continue
                
                # Determine the active curriculum to use
                active_curriculum = False
                if student.curriculum_id and student.curriculum_id.state == 'active':
                    active_curriculum = student.curriculum_id
                elif student.batch_id and student.batch_id.curriculum_id and student.batch_id.curriculum_id.state == 'active':
                    active_curriculum = student.batch_id.curriculum_id
                elif student.batch_id and student.batch_id.curriculum_id and student.batch_id.curriculum_id.parent_id:
                    # Fallback to the master curriculum from which the batch curriculum was derived
                    active_curriculum = student.batch_id.curriculum_id.parent_id
                    
                if not active_curriculum:
                    continue
                
                # Subject must be in the active curriculum for their current level
                subject_lines = active_curriculum.line_ids.filtered(
                    lambda l: l.subject_id.id == record.subject_id.id and l.year_level == int(student.current_level or 0)
                )
                
                if subject_lines:
                    # Exclude if already passed
                    passed = self.env['university.student.subject.score'].search_count([
                        ('student_id', '=', student.id),
                        ('subject_id', '=', record.subject_id.id),
                        ('is_pass', '=', True)
                    ])
                    if not passed:
                        students_to_seat.append(student)

            if not students_to_seat:
                raise ValidationError(_("No registered students found taking this subject for their current level."))

            # 2. Check room availability
            for room in record.room_ids:
                overlapping = self.env['examination.seating'].search([
                    ('id', '!=', record.id),
                    ('exam_date', '=', record.exam_date),
                    ('room_ids', 'in', room.id),
                    ('start_time', '<', record.end_time),
                    ('end_time', '>', record.start_time),
                ])
                if overlapping:
                    raise ValidationError(_("Room '%s' is already occupied by another examination on %s between %02d:%02d and %02d:%02d.") % (
                        room.name, record.exam_date,
                        int(record.start_time), int((record.start_time % 1) * 60),
                        int(record.end_time), int((record.end_time % 1) * 60)
                    ))

            # 3. Check capacity
            total_capacity = sum(room.capacity for room in record.room_ids)
            if total_capacity < len(students_to_seat):
                raise ValidationError(_("Total capacity of selected rooms (%s) is not enough for the number of students (%s).") % (total_capacity, len(students_to_seat)))

            # 3.5 Check for student exam conflicts
            student_ids = [s.id for s in students_to_seat]
            if student_ids:
                conflicting_lines = self.env['examination.seating.line'].search([
                    ('student_id', 'in', student_ids),
                    ('seating_id', '!=', record.id),
                    ('seating_id.exam_date', '=', record.exam_date),
                    ('seating_id.start_time', '<', record.end_time),
                    ('seating_id.end_time', '>', record.start_time),
                ])
                if conflicting_lines:
                    conflicting_student_names = set(conflicting_lines.mapped('student_id.display_name'))
                    names_str = ", ".join(name for name in conflicting_student_names if name)
                    raise ValidationError(_("The following students have an exam conflict on this date and time: %s") % names_str)

            # 4. Generate Seating Lines
            # Clear existing lines first
            record.seating_line_ids.unlink()
            
            lines = []
            student_idx = 0
            for room in record.room_ids:
                for seat_num in range(1, room.capacity + 1):
                    if student_idx >= len(students_to_seat):
                        break
                    
                    student = students_to_seat[student_idx]
                    lines.append((0, 0, {
                        'student_id': student.id,
                        'room_id': room.id,
                        'seat_number': f"{room.name}-{seat_num}",
                    }))
                    student_idx += 1
                    
                if student_idx >= len(students_to_seat):
                    break
                    
            record.write({'seating_line_ids': lines})

class ExaminationSeatingLine(models.Model):
    _name = 'examination.seating.line'
    _description = 'Examination Seating Line'
    _rec_name = 'seat_number'

    seating_id = fields.Many2one('examination.seating', required=True, ondelete='cascade')
    student_id = fields.Many2one('university.student', string='Student', required=True)
    seat_number = fields.Char(string='Seat Number (Troll Number)')
    room_id = fields.Many2one('examination.room', string='Room', required=True)
