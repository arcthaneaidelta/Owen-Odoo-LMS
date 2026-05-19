from odoo import models, fields, api

class ExaminationGradeEntry(models.Model):
    _name = 'examination.grade.entry'
    _description = 'Examination Grade Entry'
    _rec_name = 'student_id'

    student_id = fields.Many2one('university.student', string='Student', required=True)
    batch_id = fields.Many2one('university.batch', string='Batch', required=True)
    cycle_id = fields.Many2one('examination.cycle', string='Exam Cycle', required=True)
    
    line_ids = fields.One2many('examination.grade.entry.line', 'entry_id', string='Subject Grades')

class ExaminationGradeEntryLine(models.Model):
    _name = 'examination.grade.entry.line'
    _description = 'Examination Grade Entry Line'

    entry_id = fields.Many2one('examination.grade.entry', required=True, ondelete='cascade')
    subject_id = fields.Many2one('university.subject', string='Subject', required=True)
    
    assignment_score = fields.Float('Assignment Score')
    midterm_score = fields.Float('Midterm Score')
    practical_score = fields.Float('Practical/Lab Score')
    attendance_score = fields.Float('Attendance Score')
    exam_score = fields.Float('Exam Score')
    
    total_score = fields.Float('Total Score (Out of 100)', compute='_compute_total_score', store=True)
    subject_point = fields.Float('Subject Point (GPA)', compute='_compute_total_score', store=True)
    
    @api.depends('assignment_score', 'midterm_score', 'practical_score', 'attendance_score', 'exam_score', 'entry_id.batch_id.evaluation_method')
    def _compute_total_score(self):
        for rec in self:
            total = rec.assignment_score + rec.midterm_score + rec.practical_score + rec.attendance_score + rec.exam_score
            rec.total_score = total
            
            # Retrieve the batch evaluation method
            method = rec.entry_id.batch_id.evaluation_method
            if method == 'method_b':
                # Method B (Example: 4.0 scale format -> total / 25.0)
                rec.subject_point = total / 25.0
            else:
                # Method A Default (5.0 scale format -> total / 20.0)
                rec.subject_point = total / 20.0
