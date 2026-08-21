from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ExaminationRoom(models.Model):
    _name = 'examination.room'
    _description = 'Examination Room'

    name = fields.Char(string='Room Name', required=True)
    capacity = fields.Integer(string='Capacity', default=30, required=True)

class ExaminationAbsenceRequest(models.Model):
    _name = 'examination.absence.request'
    _description = 'Examination Absence Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    student_id = fields.Many2one('university.student', string='Student', required=True)
    cycle_id = fields.Many2one('examination.cycle', string='Missed Exam Cycle', required=True)
    subject_id = fields.Many2one('university.subject', string='Missed Subject', required=True)
    reason = fields.Text(string='Reason', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved by Committee'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', tracking=True)

    def action_approve(self):
        self.state = 'approved'

    def action_reject(self):
        self.state = 'rejected'


class ExaminationSeating(models.Model):
    _name = 'examination.seating'
    _description = 'Examination Seating'
    _rec_name = 'subject_id'

    cycle_id = fields.Many2one('examination.cycle', string='Cycle', required=True, ondelete='cascade')
    batch_id = fields.Many2one('university.batch', string='Batch', related='cycle_id.batch_id', store=True)
    subject_id = fields.Many2one('university.subject', string='Subject', required=True)
    exam_date = fields.Date(string='Examination Date', required=True)
    start_time = fields.Float(string='Start Time', required=True, help="Time in 24h float format.")
    end_time = fields.Float(string='End Time', required=True)
    seating_line_ids = fields.One2many('examination.seating.line', 'seating_id', string='Seating Lines')

    room_ids = fields.Many2many('examination.room', string='Rooms')
    invigilator_ids = fields.Many2many('hr.employee', string='Invigilators')

    @api.constrains('room_ids', 'exam_date', 'start_time', 'end_time')
    def _check_room_availability(self):
        for record in self:
            if not record.room_ids:
                continue
            # 15 minute buffer = 0.25 hours
            start_check = record.start_time - 0.25
            end_check = record.end_time + 0.25
            
            for room in record.room_ids:
                overlapping = self.env['examination.seating'].search([
                    ('id', '!=', record.id),
                    ('exam_date', '=', record.exam_date),
                    ('room_ids', 'in', room.id),
                    ('start_time', '<', end_check),
                    ('end_time', '>', start_check),
                ])
                if overlapping:
                    raise ValidationError(_("Room '%s' is already occupied (including 15m buffer) on %s. Conflict with another exam.") % (room.name, record.exam_date))

    @api.constrains('invigilator_ids', 'exam_date', 'start_time', 'end_time')
    def _check_invigilator_availability(self):
        for record in self:
            if not record.invigilator_ids:
                continue
            # 15 minute buffer = 0.25 hours
            start_check = record.start_time - 0.25
            end_check = record.end_time + 0.25
            
            for invigilator in record.invigilator_ids:
                overlapping = self.env['examination.seating'].search([
                    ('id', '!=', record.id),
                    ('exam_date', '=', record.exam_date),
                    ('invigilator_ids', 'in', invigilator.id),
                    ('start_time', '<', end_check),
                    ('end_time', '>', start_check),
                ])
                if overlapping:
                    raise ValidationError(_("Invigilator '%s' is already booked (including 15m buffer) on %s.") % (invigilator.name, record.exam_date))

    def generate_seating(self):
        for record in self:
            if not record.room_ids:
                raise ValidationError(_("Please select at least one room."))
                
            batch = record.cycle_id.batch_id
            exam_type = record.cycle_id.exam_type
            students_to_seat = []
            
            # 1. Find students
            students = self.env['university.student'].search([
                ('batch_id', '=', batch.id),
                ('registration_status', '=', 'registered')
            ])
            print("000000001111112222222")
            print(students)
            
            for student in students:
                # Generate troll number if missing
                if not student.troll_number:
                    student.troll_number = self.env['ir.sequence'].next_by_code('university.troll.number') or f"TROLL-{student.id}"
                
                # Check eligibility based on exam type
                eligible = False
                
                if exam_type == 'main':
                    # Has not passed yet
                    passed = self.env['university.student.subject.score'].search_count([
                        ('student_id', '=', student.id),
                        ('subject_id', '=', record.subject_id.id),
                        ('is_pass', '=', True)
                    ])
                    if not passed:
                        eligible = True
                        
                elif exam_type == 'second':
                    # Needs an approved absence request for this subject
                    approved_absence = self.env['examination.absence.request'].search_count([
                        ('student_id', '=', student.id),
                        ('subject_id', '=', record.subject_id.id),
                        ('state', '=', 'approved')
                    ])
                    if approved_absence:
                        eligible = True
                        
                elif exam_type == 'supplementary':
                    # Must have an F grade in this subject (score < 50 typically) and GPA > 2.5
                    # We will check the existing score
                    failing_score = self.env['university.student.subject.score'].search([
                        ('student_id', '=', student.id),
                        ('subject_id', '=', record.subject_id.id),
                        ('is_pass', '=', False),
                        ('exam_type', 'in', ['main', 'second'])
                    ])
                    if failing_score and student.cgpa > 2.5:
                        eligible = True
                
                if eligible:
                    students_to_seat.append(student)

            if not students_to_seat:
                raise ValidationError(_("No eligible students found for this subject and exam type."))

            # 3. Check capacity
            total_capacity = sum(room.capacity for room in record.room_ids)
            if total_capacity < len(students_to_seat):
                raise ValidationError(_("Total capacity of selected rooms (%s) is not enough for the number of students (%s).") % (total_capacity, len(students_to_seat)))

            # 4. Generate Seating Lines
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
                        'seat_number': student.troll_number, # Stable identifier
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
    signature = fields.Char(string='Signature') # Usually physical, but a placeholder here
