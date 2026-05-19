# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityProgram(models.Model):
    _name = 'university.program'
    _description = 'Academic Program'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'college_id, name'

    name = fields.Char(
        string='Program Name',
        required=True,
        translate=True,
        tracking=True,
    )
    name_ar = fields.Char(string='Arabic Name', tracking=True)
    name_en = fields.Char(string='English Name', tracking=True)
    code = fields.Char(string='Program Code', tracking=True)

    college_id = fields.Many2one(
        'university.college',
        string='College',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    department_id = fields.Many2one(
        'university.department',
        string='Department',
        domain="[('college_id', '=', college_id)]",
        ondelete='restrict',
        tracking=True,
    )
    university_id = fields.Many2one(
        'university.university',
        string='University',
        related='college_id.university_id',
        store=True,
        readonly=True,
    )

    degree_type = fields.Selection(
        [
            ('bachelor', 'Bachelor'),
            ('diploma', 'Diploma'),
            ('higher_diploma', 'Higher Diploma'),
            ('master', 'Master'),
            ('phd', 'PhD'),
        ],
        string='Degree Type',
        required=True,
        default='bachelor',
        tracking=True,
    )
    duration_years = fields.Integer(
        string='Duration (Years)',
        required=True,
        default=4,
        tracking=True,
    )
    max_duration_years = fields.Integer(
        string='Max Study Duration (Years)',
        required=True,
        default=10,
        tracking=True,
        help='Maximum allowed chronological years for a student to study. Excludes frozen years.'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env['res.currency'].search([('name', '=', 'SDG')], limit=1)
    )
    registration_fee = fields.Monetary(
        string='Default Registration Fee',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
    )
    tuition_fee = fields.Monetary(
        string='Default Tuition Fee',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
    )
    repetition_fee_per_subject = fields.Monetary(
        string='Repetition Fee (Per Subject)',
        currency_field='currency_id',
        default=0.0,
        help='Fee charged per subject when a student is repeating some subjects.',
        tracking=True,
    )
    external_exam_fee = fields.Monetary(
        string='External Exam Fee',
        currency_field='currency_id',
        default=0.0,
        help='Fee charged when an expelled student requests an external exam.',
        tracking=True,
    )

    # Attendance threshold configurable per program
    attendance_threshold_pct = fields.Float(
        string='Attendance Threshold (%)',
        default=75.0,
        help='Minimum attendance percentage required for exam eligibility.',
    )
    attendance_warning_pct = fields.Float(
        string='Attendance Warning (%)',
        default=80.0,
        help='Attendance percentage below which warnings are sent.',
    )

    # Credit hour ratio
    practical_credit_ratio = fields.Float(
        string='Practical Credit Ratio',
        default=0.5,
        help='Ratio used to calculate credit hours from practical hours. '
             'Default: practical_hours * 0.5',
    )

    has_specialization = fields.Boolean(
        string='Has Specializations',
        default=False,
        help='If True, indicates this program branches into specializations in later semesters. Uses different transcript/certificate templates.',
        tracking=True,
    )
    specialization_ids = fields.One2many(
        'university.specialization',
        'program_id',
        string='Specializations',
    )
    batch_ids = fields.One2many(
        'university.batch',
        'program_id',
        string='Batches',
    )
    batch_count = fields.Integer(string='Batch Count', compute='_compute_batch_count')

    @api.depends('batch_ids')
    def _compute_batch_count(self):
        for rec in self:
            rec.batch_count = len(rec.batch_ids)

    def action_view_batches(self):
        self.ensure_one()
        return {
            'name': _('Batches for %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'university.batch',
            'view_mode': 'list,form',
            'domain': [('program_id', '=', self.id)],
            'context': {'default_program_id': self.id},
        }

    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes', translate=True)

    _sql_constraints = [
        (
            'code_college_uniq',
            'unique(code, college_id)',
            'Program code must be unique per college.',
        ),
        (
            'duration_positive',
            'CHECK(duration_years > 0)',
            'Duration must be a positive number.',
        ),
    ]

    @api.constrains('attendance_threshold_pct', 'attendance_warning_pct')
    def _check_attendance_pct(self):
        for rec in self:
            if not (0 < rec.attendance_threshold_pct <= 100):
                raise ValidationError(_('Attendance threshold must be between 0 and 100.'))
            if not (0 < rec.attendance_warning_pct <= 100):
                raise ValidationError(_('Attendance warning percentage must be between 0 and 100.'))
            if rec.attendance_warning_pct < rec.attendance_threshold_pct:
                raise ValidationError(_(
                    'Warning percentage must be greater than or equal to the threshold percentage.'
                ))

    def name_get(self):
        result = []
        for rec in self:
            name = rec.name_ar or rec.name or rec.name_en or ''
            result.append((rec.id, name))
        return result
