from odoo import models, fields, api

class StudentOutcome(models.Model):
    _inherit = 'university.student'

    academic_status = fields.Selection([
        ('pass', 'Pass'),
        ('repeat_specific', 'Repeat Specific Subjects'),
        ('repeat_all', 'Repeat All Subjects'),
        ('dismissed', 'Dismissed (Expelled)'),
    ], string='End of Year Status', tracking=True)
    
    cumulative_gpa = fields.Float('Cumulative GPA', compute='_compute_gpa', store=True)

    def _compute_gpa(self):
        for rec in self:
            scores = self.env['university.student.subject.score'].search([
                ('student_id', '=', rec.id),
                ('is_pass', '=', True)
            ])
            total_points = sum(score.score for score in scores)
            count = len(scores)
            # Basic GPA calculation; adjust to full formula if needed
            rec.cumulative_gpa = (total_points / count / 20.0) if count > 0 else 0.0

    def process_end_of_year_outcome(self):
        for student in self:
            # Check all subjects for the current level
            active_curriculum = student.batch_id.curriculum_id if student.batch_id and student.batch_id.curriculum_id.state == 'active' else False
            if not active_curriculum and student.batch_id and student.batch_id.curriculum_id.parent_id:
                active_curriculum = student.batch_id.curriculum_id.parent_id
                
            if not active_curriculum:
                continue
                
            level = int(student.current_level or 1)
            subjects = active_curriculum.line_ids.filtered(lambda l: l.year_level == level).mapped('subject_id')
            
            failed_subjects = []
            passed_subjects = []
            
            for subject in subjects:
                passed = self.env['university.student.subject.score'].search_count([
                    ('student_id', '=', student.id),
                    ('subject_id', '=', subject.id),
                    ('is_pass', '=', True)
                ])
                if passed:
                    passed_subjects.append(subject)
                else:
                    failed_subjects.append(subject)
                    
            if not failed_subjects:
                student.academic_status = 'pass'
                # Do not promote here, promotion happens via Roadmap
                student.registration_status = 'unregistered'
            else:
                # If they failed more than 3 subjects (or based on policy), Repeat All
                if len(failed_subjects) > 3:
                    student.academic_status = 'repeat_all'
                else:
                    student.academic_status = 'repeat_specific'
                
                # Apply repeater logic from university_student
                if not student.is_repeater:
                    student.is_repeater = True
                
                # Add history
                self.env['university.student.repeat.history'].create({
                    'student_id': student.id,
                    'level_repeated': str(level),
                    'status': 'active'
                })
                
                student.registration_status = 'unregistered'
