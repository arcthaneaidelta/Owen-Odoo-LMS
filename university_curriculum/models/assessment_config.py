# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityAssessmentConfig(models.Model):
    _name = 'university.assessment.config'
    _description = 'Subject Assessment Configuration'
    _order = 'subject_id'

    subject_id = fields.Many2one(
        'university.subject',
        string='Subject',
        required=True,
        ondelete='cascade',
        index=True,
    )
    curriculum_id = fields.Many2one(
        'university.curriculum',
        string='Curriculum',
        help='If set, this config applies only to this curriculum. '
             'Leave empty for a default config for the subject.',
    )
    # Assessment components - must sum to 100%
    assignment_pct = fields.Float(
        string='Assignment (%)',
        default=10.0,
    )
    midterm_pct = fields.Float(
        string='Midterm (%)',
        default=20.0,
    )
    practical_pct = fields.Float(
        string='Practical/Lab (%)',
        default=0.0,
    )
    attendance_pct = fields.Float(
        string='Attendance (%)',
        default=5.0,
    )
    final_pct = fields.Float(
        string='Final Exam (%)',
        default=65.0,
    )
    total_pct = fields.Float(
        string='Total (%)',
        compute='_compute_total_pct',
        store=True,
    )

    @api.depends(
        'assignment_pct', 'midterm_pct', 'practical_pct',
        'attendance_pct', 'final_pct'
    )
    def _compute_total_pct(self):
        for rec in self:
            rec.total_pct = (
                rec.assignment_pct
                + rec.midterm_pct
                + rec.practical_pct
                + rec.attendance_pct
                + rec.final_pct
            )

    @api.constrains(
        'assignment_pct', 'midterm_pct', 'practical_pct',
        'attendance_pct', 'final_pct'
    )
    def _check_percentages(self):
        for rec in self:
            total = (
                rec.assignment_pct
                + rec.midterm_pct
                + rec.practical_pct
                + rec.attendance_pct
                + rec.final_pct
            )
            if abs(total - 100.0) > 0.01:
                raise ValidationError(_(
                    'Assessment percentages must sum to exactly 100%%. '
                    'Current total: %.2f%%'
                ) % total)
            for fname in (
                'assignment_pct', 'midterm_pct', 'practical_pct',
                'attendance_pct', 'final_pct'
            ):
                if rec[fname] < 0:
                    raise ValidationError(_('Assessment percentages cannot be negative.'))
