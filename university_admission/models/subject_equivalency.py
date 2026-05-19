# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class UniversitySubjectEquivalency(models.Model):
    _name = 'university.subject.equivalency'
    _description = 'Transfer Student Subject Equivalency'
    _order = 'admission_id, previous_subject_name'

    admission_id = fields.Many2one(
        'university.admission',
        string='Admission Application',
        required=True,
        ondelete='cascade',
        index=True,
    )
    student_id = fields.Many2one(
        'university.student',
        string='Student',
        related='admission_id.student_id',
        store=True,
        readonly=True,
    )

    # Previous subject (from their old university)
    previous_subject_name = fields.Char(
        string='Previous Subject Name',
        required=True,
    )
    previous_subject_code = fields.Char(string='Previous Subject Code')
    previous_credit_hours = fields.Float(string='Previous Credit Hours')
    previous_grade = fields.Char(string='Previous Grade')
    previous_institution = fields.Char(string='Previous Institution')

    # Mapped to current curriculum
    current_subject_id = fields.Many2one(
        'university.subject',
        string='Equivalent Subject (Current Curriculum)',
    )
    equivalency_status = fields.Selection(
        [
            ('pending', 'Pending Review'),
            ('approved', 'Approved'),
            ('rejected', 'Not Equivalent'),
            ('partial', 'Partial Credit'),
            ('exempt', 'Exempt (Full Credit)'),
        ],
        string='Equivalency Status',
        default='pending',
        tracking=True,
    )
    awarded_credit_hours = fields.Float(string='Awarded Credit Hours')
    reviewer_id = fields.Many2one(
        'res.users',
        string='Reviewed By',
    )
    review_date = fields.Date(string='Review Date')
    notes = fields.Text(string='Notes')
