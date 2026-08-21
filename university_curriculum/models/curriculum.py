# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityCurriculum(models.Model):
    _name = 'university.curriculum'
    _description = 'Curriculum Blueprint'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'program_id, academic_year_name, name'

    name = fields.Char(
        string='Curriculum Name',
        required=True,
        translate=True,
        tracking=True,
    )
    code = fields.Char(string='Code', tracking=True)
    
    curriculum_type = fields.Selection([
        ('master', 'Master Curriculum'),
        ('batch', 'Batch Draft'),
        ('student', 'Student Copy'),
    ], string='Curriculum Type', default='master', required=True, tracking=True)
    
    parent_id = fields.Many2one('university.curriculum', string='Parent Curriculum', ondelete='set null', help='The curriculum this was copied from')
    child_ids = fields.One2many('university.curriculum', 'parent_id', string='Derived Curriculums')
    batch_id = fields.Many2one('university.batch', string='Linked Batch', ondelete='cascade')
    student_id = fields.Many2one('university.student', string='Linked Student', ondelete='cascade')

    program_id = fields.Many2one(
        'university.program',
        string='Program',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    college_id = fields.Many2one(
        'university.college',
        related='program_id.college_id',
        store=True,
        readonly=True,
    )
    academic_year_name = fields.Char(
        string='Academic Year',
        tracking=True,
    )
    has_specialization = fields.Boolean(
        string='Has Specializations',
        related='program_id.has_specialization',
        store=True,
        readonly=True,
    )
    version = fields.Char(
        string='Version',
        default='1.0',
        tracking=True,
    )

    # Curriculum Lines
    line_ids = fields.One2many(
        'university.curriculum.line',
        'curriculum_id',
        string='Curriculum Subjects',
        copy=True
    )
    
    subject_count = fields.Integer(
        string='Subject Count',
        compute='_compute_subject_count',
    )
    total_credit_hours = fields.Float(
        string='Total Credit Hours',
        compute='_compute_totals',
        store=True,
    )
    total_lecture_hours = fields.Float(
        string='Total Lecture Hours',
        compute='_compute_totals',
        store=True,
    )
    total_practical_hours = fields.Float(
        string='Total Practical Hours',
        compute='_compute_totals',
        store=True,
    )

    is_locked = fields.Boolean(
        string='Locked',
        default=False,
        help='Locked curricula cannot be modified. Auto-locked when active.',
    )

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('deprecated', 'Deprecated'),
        ],
        string='State',
        default='draft',
        tracking=True,
    )

    notes = fields.Text(string='Notes', translate=True)
    active = fields.Boolean(default=True)

    @api.onchange('program_id')
    def _onchange_program_id(self):
        """Clear subjects and auto-populate from the selected program."""
        if self.program_id:
            # 1. Clear existing lines
            self.line_ids = [(5, 0, 0)]
            # 2. Populate new subjects
            self._populate_subjects_from_program()
        else:
            self.line_ids = [(5, 0, 0)]

    def _populate_subjects_from_program(self):
        """Helper to create curriculum lines from program subjects."""
        self.ensure_one()
        if not self.program_id:
            return
            
        subjects = self.env['university.subject'].search([
            ('program_id', '=', self.program_id.id)
        ])
        
        lines = []
        for subject in subjects:
            lines.append((0, 0, {
                'subject_id': subject.id,
                'semester': subject.semester,
                'year_level': subject.year_level,
                'lecture_hours': subject.lecture_hours,
                'tutorial_hours': subject.tutorial_hours,
                'practical_hours': subject.practical_hours,
                'clinical_hours': subject.clinical_hours,
            }))
        self.line_ids = lines

    @api.constrains('program_id', 'line_ids')
    def _check_line_program_consistency(self):
        for rec in self:
            for line in rec.line_ids:
                if line.subject_id and line.subject_id.program_id != rec.program_id:
                    raise ValidationError(_(
                        "Subject '%s' does not belong to the selected program '%s'."
                    ) % (line.subject_id.name, rec.program_id.name))

    @api.depends('line_ids')
    def _compute_subject_count(self):
        for rec in self:
            rec.subject_count = len(rec.line_ids)

    @api.depends('line_ids', 'line_ids.credit_hours',
                 'line_ids.lecture_hours', 'line_ids.practical_hours')
    def _compute_totals(self):
        for rec in self:
            rec.total_credit_hours = sum(rec.line_ids.mapped('credit_hours'))
            rec.total_lecture_hours = sum(rec.line_ids.mapped('lecture_hours'))
            rec.total_practical_hours = sum(rec.line_ids.mapped('practical_hours'))

    def write(self, vals):
        """Prevent changes to locked curricula."""
        if self.filtered(lambda r: r.is_locked) and any(
            k not in ('message_ids', 'activity_ids', 'state', 'is_locked') for k in vals
        ):
            raise ValidationError(_(
                'This curriculum is locked and cannot be modified. '
                'To make changes, create a new curriculum version.'
            ))
        return super().write(vals)

    def action_activate(self):
        self.write({'state': 'active', 'is_locked': True})

    def action_lock(self):
        self.write({'is_locked': True})

    def action_duplicate_as_new_version(self):
        """Create a new unlocked copy for future batches."""
        self.ensure_one()
        new = self.copy({
            'name': f'{self.name} (v{float(self.version or 1) + 1:.1f})',
            'version': str(float(self.version or 1) + 1),
            'is_locked': False,
            'state': 'draft',
            'curriculum_type': 'master',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'university.curriculum',
            'res_id': new.id,
            'view_mode': 'form',
        }

    def name_get(self):
        result = []
        for rec in self:
            prog = rec.program_id.name_ar or rec.program_id.name or ''
            type_str = dict(self._fields['curriculum_type'].selection).get(rec.curriculum_type)
            result.append((rec.id, f'[{type_str}] {rec.name} ({prog})'))
        return result


class UniversityCurriculumLine(models.Model):
    _name = 'university.curriculum.line'
    _description = 'Curriculum Subject Line'
    _order = 'year_level, semester, subject_id'

    curriculum_id = fields.Many2one('university.curriculum', string='Curriculum', required=True, ondelete='cascade')
    subject_id = fields.Many2one(
        'university.subject', 
        string='Master Subject', 
        required=True, 
        ondelete='restrict',
        domain="[('program_id', '=', parent.program_id)]"
    )
    
    # Optional specialization link
    specialization_id = fields.Many2one('university.specialization', string='Specialization', help='Only applicable if the program has specializations.')

    semester = fields.Integer(string='Semester', default=1, required=True)
    year_level = fields.Integer(string='Year Level', default=1, required=True)

    # Copied hours from Master Subject for customization
    lecture_hours = fields.Float(string='Lecture Hours', default=2.0)
    tutorial_hours = fields.Float(string='Tutorial Hours', default=0.0)
    practical_hours = fields.Float(string='Practical Hours', default=0.0)
    clinical_hours = fields.Float(string='Clinical Hours', default=0.0)
    
    # Teacher Allocation and Roles
    lecturer_id = fields.Many2one(
        'hr.employee', 
        string='Lecturer (Theory)', 
        domain="[('is_teacher', '=', True), ('university_subject_ids', 'in', subject_id)]"
    )
    tutor_id = fields.Many2one(
        'hr.employee', 
        string='Tutor (Tutorial)', 
        domain="[('is_teacher', '=', True), ('university_subject_ids', 'in', subject_id)]"
    )
    instructor_id = fields.Many2one(
        'hr.employee', 
        string='Instructor (Lab/Field)', 
        domain="[('is_teacher', '=', True), ('university_subject_ids', 'in', subject_id)]"
    )
    
    credit_hours = fields.Integer(
        string='Credit Hours',
        compute='_compute_credit_hours',
        store=True,
    )

    @api.onchange('subject_id')
    def _onchange_subject_id(self):
        if self.subject_id:
            self.lecture_hours = self.subject_id.lecture_hours
            self.tutorial_hours = self.subject_id.tutorial_hours
            self.practical_hours = self.subject_id.practical_hours
            self.clinical_hours = self.subject_id.clinical_hours
            self.semester = self.subject_id.semester
            self.year_level = self.subject_id.year_level

    @api.depends('lecture_hours', 'tutorial_hours', 'practical_hours', 'clinical_hours')
    def _compute_credit_hours(self):
        """
        Credit Hours = lecture_hours + (tutorial_hours/2) + (practical_hours/3) + (clinical_hours/5)
        Rounded to whole number.
        """
        for rec in self:
            raw_credit = rec.lecture_hours + (rec.tutorial_hours / 2.0) + (rec.practical_hours / 3.0) + (rec.clinical_hours / 5.0)
            rec.credit_hours = round(raw_credit)
