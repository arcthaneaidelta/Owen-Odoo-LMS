from odoo import models, fields, api, _

class ExaminationGradeEntry(models.Model):
    _name = 'examination.grade.entry'
    _description = 'Examination Grade Entry'
    _rec_name = 'student_id'

    student_id = fields.Many2one('university.student', string='Student', required=True)
    batch_id = fields.Many2one('university.batch', string='Batch', related='student_id.batch_id', store=True)
    cycle_id = fields.Many2one('examination.cycle', string='Exam Cycle', required=True)
    exam_type = fields.Selection(related='cycle_id.exam_type', store=True)
    
    line_ids = fields.One2many('examination.grade.entry.line', 'entry_id', string='Subject Grades')

class ExaminationGradeEntryLine(models.Model):
    _name = 'examination.grade.entry.line'
    _description = 'Examination Grade Entry Line'

    entry_id = fields.Many2one('examination.grade.entry', required=True, ondelete='cascade')
    subject_id = fields.Many2one('university.subject', string='Subject', required=True)
    
    assignment_score = fields.Float('Assignment Score (Max 30)')
    attendance_score = fields.Float('Attendance Score (Max 10)')
    exam_score = fields.Float('Exam Score (Max 60)')
    
    total_score = fields.Float('Total Score', compute='_compute_total_score', store=True)
    effective_max = fields.Float('Effective Max Score', compute='_compute_total_score', store=True)
    is_pass = fields.Boolean('Pass?', compute='_compute_total_score', store=True)
    
    @api.depends('assignment_score', 'attendance_score', 'exam_score', 'entry_id.exam_type')
    def _compute_total_score(self):
        for rec in self:
            exam_type = rec.entry_id.exam_type
            
            a_score = min(rec.assignment_score, 30.0)
            att_score = min(rec.attendance_score, 10.0)
            e_score = min(rec.exam_score, 60.0)
            
            if exam_type == 'supplementary':
                # Supplementary Exam reduces exam component by half
                e_score = e_score / 2.0
                rec.total_score = a_score + att_score + e_score
                rec.effective_max = 50.0 # 30 + 10 + 30 = 70, mapped to 50
                # Pass requires 50% usually
                rec.is_pass = (rec.total_score / rec.effective_max) >= 0.5
            else:
                rec.total_score = a_score + att_score + e_score
                rec.effective_max = 100.0
                rec.is_pass = rec.total_score >= 50.0

    def action_push_to_results(self):
        # Push these grades to the official student subject scores
        for rec in self:
            score_env = self.env['university.student.subject.score']
            student = rec.entry_id.student_id
            cycle = rec.entry_id.cycle_id
            
            existing = score_env.search([
                ('student_id', '=', student.id),
                ('subject_id', '=', rec.subject_id.id),
                ('exam_round', '=', cycle.exam_type),
                ('academic_year_name', '=', cycle.academic_year_name)
            ])
            vals = {
                'student_id': student.id,
                'subject_id': rec.subject_id.id,
                'academic_year_name': cycle.academic_year_name,
                'level': student.current_level or '1',
                'exam_round': cycle.exam_type,
                'score': rec.total_score,
                'is_pass': rec.is_pass,
            }
            if existing:
                existing.write(vals)
            else:
                score_env.create(vals)
