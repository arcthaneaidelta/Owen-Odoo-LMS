# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class UniversityStudentSubjectScore(models.Model):
    _name = 'university.student.subject.score'
    _description = 'Student Subject Exam Score'
    _order = 'academic_year_id desc, level desc, subject_id, exam_round'

    student_id = fields.Many2one(
        'university.student', 
        string='Student', 
        required=True, 
        ondelete='cascade',
        index=True,
    )
    subject_id = fields.Many2one(
        'university.subject', 
        string='Subject', 
        required=True,
        index=True,
    )
    academic_year_id = fields.Many2one(
        'university.academic_year', 
        string='Academic Year', 
        required=True,
        index=True,
    )
    level = fields.Selection(
        [
            ('1', 'Level 1'),
            ('2', 'Level 2'),
            ('3', 'Level 3'),
            ('4', 'Level 4'),
            ('5', 'Level 5'),
            ('6', 'Level 6'),
        ],
        string='Level',
        required=True,
    )
    exam_round = fields.Selection(
        [
            ('main', 'Main Round'),
            ('second', 'Second Round'),
            ('supplementary', 'Supplementary Round'),
            ('makeup', 'Make-up Exam'),
        ],
        string='Examination Round',
        required=True,
        default='main',
    )
    score = fields.Float(string='Score', required=True, default=0.0)
    is_pass = fields.Boolean(
        string='Is Pass', 
        compute='_compute_is_pass', 
        store=True,
    )
    result_status = fields.Selection(
        [('pass', 'Pass'), ('fail', 'Fail')],
        string='Result Status',
        compute='_compute_result_status',
        store=True
    )

    @api.depends('score', 'subject_id.passing_score')
    def _compute_is_pass(self):
        for rec in self:
            passing = rec.subject_id.passing_score or 50.0
            rec.is_pass = rec.score >= passing

    @api.depends('is_pass')
    def _compute_result_status(self):
        for rec in self:
            rec.result_status = 'pass' if rec.is_pass else 'fail'

    _sql_constraints = [
        (
            'student_subject_round_year_uniq',
            'unique(student_id, subject_id, academic_year_id, exam_round)',
            'A score for this student, subject, year, and round already exists.'
        ),
    ]
