# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class UniversityTimetable(models.Model):
    _name = 'university.timetable'
    _description = 'Timetable / Class Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'day_of_week, start_time'

    name = fields.Char(string='Session Ref', default=lambda self: _('New'), readonly=True, copy=False)
    
    # Core Data
    batch_id = fields.Many2one(
        'university.batch', 
        string='Batch', 
        required=True, 
        domain="[('state', '=', 'active')]", 
        tracking=True
    )
    program_id = fields.Many2one('university.program', related='batch_id.program_id', store=True)
    department_id = fields.Many2one('university.department', related='program_id.department_id', store=True)
    academic_year_id = fields.Many2one(
        'university.academic_year', 
        string='Academic Year', 
        required=True,
        domain="[('state', '=', 'active')]"
    )
    
    subject_id = fields.Many2one(
        'university.subject', 
        string='Subject', 
        required=True, 
        domain="[('program_id', '=', program_id)]",
        tracking=True
    )
    
    # The teacher domain: Only teachers related to the selected subject
    teacher_id = fields.Many2one(
        'hr.employee', 
        string='Teacher / Instructor', 
        required=True, 
        domain="[('is_teacher', '=', True), ('university_subject_ids', 'in', subject_id)]",
        tracking=True
    )
    
    # Room Allocation
    room_id = fields.Many2one('university.room', string='Room / Facility', required=True, tracking=True)
    
    @api.onchange('batch_id')
    def _onchange_batch_id(self):
        self.subject_id = False 
        self.teacher_id = False
        if self.batch_id:
            # Filter subjects to only those in the batch curriculum
            curriculum = self.env['university.curriculum'].search([
                ('batch_id', '=', self.batch_id.id),
                ('state', '=', 'active')
            ], limit=1)
            if curriculum:
                subject_ids = curriculum.line_ids.mapped('subject_id').ids
                return {'domain': {'subject_id': [('id', 'in', subject_ids)]}}
        return {'domain': {'subject_id': []}}

    @api.onchange('subject_id')
    def _onchange_subject_id_reset(self):
        """Clear teacher when subject changes."""
        self.teacher_id = False

    @api.onchange('subject_id', 'session_type')
    def _onchange_assignment_details(self):
        # Auto-fill teacher from the Batch Curriculum based on Session Type
        if self.batch_id and self.subject_id and self.session_type:
            curriculum = self.env['university.curriculum'].search([
                ('batch_id', '=', self.batch_id.id),
                ('state', '=', 'active')
            ], limit=1)
            
            if curriculum:
                line = curriculum.line_ids.filtered(lambda l: l.subject_id == self.subject_id)
                if line:
                    line = line[0] # Take the first one if multiple (unlikely)
                    
                    if self.session_type == 'theory':
                        self.teacher_id = line.lecturer_id
                    elif self.session_type == 'tutorial':
                        self.teacher_id = line.tutor_id
                    elif self.session_type in ('practical', 'lab'):
                        self.teacher_id = line.instructor_id
                    
                    # If the specific role isn't filled, fallback to general search
                    if not self.teacher_id:
                        teachers = self.env['hr.employee'].search([
                            ('is_teacher', '=', True),
                            ('university_subject_ids', 'in', self.subject_id.id)
                        ])
                        if len(teachers) == 1:
                            self.teacher_id = teachers.id
    
    # Scheduling Details
    session_type = fields.Selection([
        ('theory', 'Theoretical Lecture'),
        ('practical', 'Practical Session'),
        ('lab', 'Laboratory'),
        ('tutorial', 'Tutorial'),
    ], string='Session Type', required=True, default='theory', tracking=True)
    
    day_of_week = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
    ], string='Day of Week', required=True, tracking=True)
    
    start_time = fields.Float(string='Start Time', required=True, help="Time in 24h float format. E.g., 14.5 = 14:30")
    end_time = fields.Float(string='End Time', required=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted to Academic Affairs'),
        ('approved', 'Approved'),
        ('published', 'Published')
    ], string='Status', default='draft', tracking=True)
    
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                # Quick fallback if sequence is not defined yet
                vals['name'] = self.env['ir.sequence'].next_by_code('university.timetable') or _('Session')
        return super().create(vals_list)

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for rec in self:
            if rec.start_time >= rec.end_time:
                raise ValidationError(_("End time must be after start time."))
            if not (0 <= rec.start_time < 24) or not (0 < rec.end_time <= 24):
                raise ValidationError(_("Times must be valid 24h values (0 to 24)."))
            
            # Duration limit 2-3 hours rule logic (Can be a soft warning, but let's just ensure it's not absurdly long)
            duration = rec.end_time - rec.start_time
            if duration > 5:
                raise ValidationError(_("A single session cannot exceed 5 hours."))

    @api.constrains('room_id', 'batch_id')
    def _check_room_capacity(self):
        for rec in self:
            if rec.room_id and rec.batch_id:
                # capacity limit logic: Check against batch capacity or known student count
                # The user specified hard capacity limits
                if rec.batch_id.capacity > rec.room_id.capacity:
                    raise ValidationError(
                        _("Hard Capacity Limit Exceeded! The batch '%(batch)s' has a capacity/size of %(batch_cap)s, but the selected room '%(room)s' can only hold %(room_cap)s students.") % {
                            'batch': rec.batch_id.name,
                            'batch_cap': rec.batch_id.capacity,
                            'room': rec.room_id.name,
                            'room_cap': rec.room_id.capacity
                        }
                    )

    @api.constrains('room_id', 'day_of_week', 'start_time', 'end_time', 'academic_year_id')
    def _check_room_double_booking(self):
        GAP = 0.166  # 10 minutes
        for rec in self:
            if rec.room_id:
                domain = [
                    ('id', '!=', rec.id),
                    ('room_id', '=', rec.room_id.id),
                    ('day_of_week', '=', rec.day_of_week),
                    ('academic_year_id', '=', rec.academic_year_id.id),
                    ('start_time', '<', rec.end_time + GAP), 
                    ('end_time', '>', rec.start_time - GAP)
                ]
                conflicts = self.search(domain)
                for conflict in conflicts:
                    # Check for direct overlap
                    if max(rec.start_time, conflict.start_time) < min(rec.end_time, conflict.end_time):
                        raise ValidationError(
                            _("Double Booking Error: Room '%(room)s' is already occupied by another session on %(day)s at this exact time.") % {
                                'room': rec.room_id.name,
                                'day': dict(self._fields['day_of_week'].selection).get(rec.day_of_week)
                            }
                        )
                    else:
                        raise ValidationError(
                            _("Mandatory Gap Violation: Room '%(room)s' needs a 10-minute transition gap between sessions. A session ends/starts too close to this one on %(day)s.") % {
                                'room': rec.room_id.name,
                                'day': dict(self._fields['day_of_week'].selection).get(rec.day_of_week)
                            }
                        )

    @api.constrains('teacher_id', 'day_of_week', 'start_time', 'end_time', 'academic_year_id')
    def _check_teacher_double_booking(self):
        GAP = 0.166
        for rec in self:
            if rec.teacher_id:
                domain = [
                    ('id', '!=', rec.id),
                    ('teacher_id', '=', rec.teacher_id.id),
                    ('day_of_week', '=', rec.day_of_week),
                    ('academic_year_id', '=', rec.academic_year_id.id),
                    ('start_time', '<', rec.end_time + GAP), 
                    ('end_time', '>', rec.start_time - GAP)
                ]
                conflicts = self.search(domain)
                for conflict in conflicts:
                    if max(rec.start_time, conflict.start_time) < min(rec.end_time, conflict.end_time):
                        raise ValidationError(
                            _("Double Booking Error: Teacher '%(teacher)s' is already scheduled for another session on %(day)s at this exact time.") % {
                                'teacher': rec.teacher_id.name,
                                'day': dict(self._fields['day_of_week'].selection).get(rec.day_of_week)
                            }
                        )
                    else:
                        raise ValidationError(
                            _("Mandatory Gap Violation: Teacher '%(teacher)s' needs a 10-minute transition gap between sessions. A session ends/starts too close to this one on %(day)s.") % {
                                'teacher': rec.teacher_id.name,
                                'day': dict(self._fields['day_of_week'].selection).get(rec.day_of_week)
                            }
                        )

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})
        
    def action_publish(self):
        self.write({'state': 'published'})

    def action_draft(self):
        self.write({'state': 'draft'})
