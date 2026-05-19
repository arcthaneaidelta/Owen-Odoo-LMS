# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversitySubject(models.Model):
    _name = 'university.subject'
    _description = 'Academic Subject'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code'

    # ─── Names ────────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Subject Name',
        required=True,
        translate=True,
        tracking=True,
    )
    name_ar = fields.Char(
        string='Arabic Name',
        required=True,
        tracking=True,
    )
    name_en = fields.Char(
        string='English Name',
        tracking=True,
    )
    code = fields.Char(
        string='Subject Code',
        required=True,
        index=True,
        tracking=True,
    )

    # ─── Placement ────────────────────────────────────────────────────────────
    department_id = fields.Many2one(
        'university.department',
        string='Department',
        ondelete='restrict',
        tracking=True,
    )

    @api.onchange('department_id')
    def _onchange_department_id(self):
        self.program_id = False

    program_id = fields.Many2one(
        'university.program',
        string='Program',
        domain="[('department_id', '=', department_id)]",
        help='The main program this subject belongs to.'
    )

    # ─── Hours ────────────────────────────────────────────────────────────────
    lecture_hours = fields.Float(
        string='Lecture Hours (per week)',
        required=True,
        default=2.0,
    )
    tutorial_hours = fields.Float(
        string='Tutorial/Follow-up Hours (per week)',
        default=0.0,
    )
    practical_hours = fields.Float(
        string='Practical/Lab Hours (per week)',
        default=0.0,
    )
    clinical_hours = fields.Float(
        string='Clinical Hours (per week)',
        default=0.0,
    )
    credit_hours = fields.Integer(
        string='Credit Hours',
        compute='_compute_credit_hours',
        store=True,
        help='Computed and rounded: lecture + (tutorial / 2) + (practical / 3) + (clinical / 5).',
    )
    # Semester placement
    semester = fields.Integer(
        string='Semester',
        default=1,
        help='Which semester this subject belongs to (1, 2, etc.)',
    )
    year_level = fields.Integer(
        string='Year Level',
        default=1,
        help='Which year this subject is taught (1st year, 2nd year, etc.)',
    )

    # ─── Subject Type ─────────────────────────────────────────────────────────
    subject_type = fields.Selection(
        [
            ('theory', 'Theory'),
            ('practical', 'Practical'),
            ('mixed', 'Mixed (Theory + Practical)'),
            ('clinical', 'Clinical'),
            ('seminar', 'Seminar'),
        ],
        string='Subject Type',
        default='theory',
        required=True,
    )
    is_elective = fields.Boolean(string='Elective', default=False)
    is_prerequisite_required = fields.Boolean(string='Has Prerequisites', default=False)
    prerequisite_ids = fields.Many2many(
        'university.subject',
        'university_subject_prerequisite_rel',
        'subject_id',
        'prerequisite_id',
        string='Prerequisites',
    )

    # ─── Assessment Config ────────────────────────────────────────────────────
    assessment_config_ids = fields.One2many(
        'university.assessment.config',
        'subject_id',
        string='Assessment Configuration',
    )
    passing_score = fields.Float(
        string='Passing Score (%)',
        default=50.0,
        help='Minimum weighted total score to pass this subject.',
    )

    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes', translate=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Subject code must be unique.'),
    ]

    @api.depends('lecture_hours', 'tutorial_hours', 'practical_hours', 'clinical_hours')
    def _compute_credit_hours(self):
        """
        Credit Hours = lecture_hours + (tutorial_hours/2) + (practical_hours/3) + (clinical_hours/5)
        Rounded to whole number.
        """
        for rec in self:
            raw_credit = rec.lecture_hours + (rec.tutorial_hours / 2.0) + (rec.practical_hours / 3.0) + (rec.clinical_hours / 5.0)
            rec.credit_hours = round(raw_credit)


    @api.constrains('lecture_hours', 'tutorial_hours', 'practical_hours', 'clinical_hours')
    def _check_hours_positive(self):
        for rec in self:
            if any(h < 0 for h in [rec.lecture_hours, rec.tutorial_hours, rec.practical_hours, rec.clinical_hours]):
                raise ValidationError(_('Hours cannot be negative.'))

    def name_get(self):
        result = []
        for rec in self:
            name = f'[{rec.code}] {rec.name_ar or rec.name}'
            result.append((rec.id, name))
        return result
