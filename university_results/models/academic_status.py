# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class UniversityAcademicStatus(models.Model):
    _name = 'university.student.academic.status'
    _description = 'Student Academic Status / Results'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'student_id'

    student_id = fields.Many2one(
        'university.student', 
        string='Student', 
        required=True, 
        tracking=True,
    )
    academic_year_name = fields.Char(
        string='Academic Year',
        required=True,
        tracking=True,
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
        tracking=True,
    )
    
    status_result = fields.Selection(
        [
            ('promoted', 'Promoted'),
            ('repeating_all', 'Repeating All Subjects'),
            ('repeating_some', 'Repeating Some Subjects'),
            ('expelled', 'Expelled'),
        ],
        string='Academic Status Result',
        required=True,
        tracking=True,
    )

    failed_subject_ids = fields.Many2many(
        'university.subject',
        string='Failed Subjects',
        help='Subjects to repeat when Repeating Some Subjects.',
    )

    repetition_invoice_id = fields.Many2one('account.move', string='Repetition Invoice', readonly=True)

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
        ],
        string='Record State',
        default='draft',
        tracking=True,
    )

    current_gpa = fields.Float(string='Current Level GPA', digits=(12, 2))
    cumulative_gpa = fields.Float(string='Cumulative GPA', digits=(12, 2))

    def action_compute_results(self):
        """
        Automated logic for academic outcome based on exam scores.
        """
        for rec in self:
            scores = self.env['university.student.subject.score'].search([
                ('student_id', '=', rec.student_id.id),
                ('academic_year_name', '=', rec.academic_year_name),
                ('level', '=', rec.level),
            ])

            if not scores:
                raise ValidationError(_("No exam scores found for this student in the selected year and level."))

            # 1. Get unique subjects and find the best result for each
            subject_outcomes = {} # subject_id -> {is_pass: bool, round: str, score: float, credit_hours: float}
            for s in scores:
                sid = s.subject_id.id
                if sid not in subject_outcomes:
                    subject_outcomes[sid] = {'is_pass': False, 'round': 'main', 'score': 0.0, 'credit_hours': s.subject_id.credit_hours}
                
                # Round hierarchy: makeup > supplementary > second > main (simplified)
                # If they pass in any round, they pass. If they fail makeup, it's a final fail.
                round_rank = {'main': 1, 'second': 2, 'supplementary': 3, 'makeup': 4}
                if s.is_pass:
                    subject_outcomes[sid]['is_pass'] = True
                    subject_outcomes[sid]['score'] = s.score
                    subject_outcomes[sid]['round'] = s.exam_round
                elif round_rank[s.exam_round] >= round_rank[subject_outcomes[sid]['round']]:
                    # Keep the latest fail if they haven't passed
                    subject_outcomes[sid]['is_pass'] = False
                    subject_outcomes[sid]['score'] = s.score
                    subject_outcomes[sid]['round'] = s.exam_round

            # 2. Calculate GPA & Failures
            total_weighted_score = 0.0
            total_credits = 0.0
            failed_subjects = self.env['university.subject']
            
            non_exempt_failed_second = False
            failed_makeup = False
            
            exempt_names = ['Arabic Language', 'Islamic Studies', 'Computer Sciences', 'Sudanese Studies']
            
            for sid, outcome in subject_outcomes.items():
                subject = self.env['university.subject'].browse(sid)
                total_weighted_score += (outcome['score'] / 100.0) * outcome['credit_hours'] * 4.0 # Scale 4.0
                total_credits += outcome['credit_hours']
                
                if not outcome['is_pass']:
                    failed_subjects |= subject
                    if outcome['round'] == 'second' and not any(ex in (subject.name_ar or subject.name or '') for ex in exempt_names):
                        non_exempt_failed_second = True
                    if outcome['round'] == 'makeup':
                        failed_makeup = True

            gpa = total_weighted_score / total_credits if total_credits > 0 else 0.0
            rec.current_gpa = gpa
            # For simplicity, cumulative gpa is same as current for now, 
            # ideally it should factor in previous years.
            rec.cumulative_gpa = gpa 

            # 3. Apply Rules
            status = 'promoted'
            failed_ids = []

            # Scenario A: Repeat All
            if len(failed_subjects) == len(subject_outcomes) or failed_makeup or (1.5 <= gpa < 2.5):
                status = 'repeating_all'
            # Expulsion check (will be checked more strictly in action_confirm)
            elif gpa < 1.5:
                status = 'expelled'
            # Scenario B: Repeat Some
            elif len(failed_subjects) > 0 or non_exempt_failed_second:
                status = 'repeating_some'
                failed_ids = failed_subjects.ids
            
            rec.write({
                'status_result': status,
                'failed_subject_ids': [(6, 0, failed_ids)]
            })

    def action_confirm(self):
        for rec in self:
            student = rec.student_id
            
            if rec.status_result == 'expelled':
                student.action_expel()
                
            elif rec.status_result in ('repeating_all', 'repeating_some'):
                # Rule: Max 1 repetition per level
                existing_repeat = self.env['university.student.repeat.history'].search([
                    ('student_id', '=', student.id),
                    ('level_repeated', '=', rec.level),
                    ('status', 'not in', ['discarded'])
                ])
                if existing_repeat:
                    # They failed a level they were already repeating -> Expulsion
                    student.action_expel()
                    rec.message_post(body=_("Student failed a repeated level. Automatic expulsion triggered."))
                    rec.write({'status_result': 'expelled', 'state': 'confirmed'})
                    continue

                # Batch Update: Find next batch
                next_batch = self.env['university.batch'].search([
                    ('program_id', '=', student.program_id.id),
                    ('current_level', '=', rec.level),
                    ('state', '=', 'active')
                ], limit=1)
                
                if not next_batch:
                    raise ValidationError(_("Could not find an active batch for this program at the required level to reassign the student."))

                # Update history
                open_history = self.env['university.student.repeat.history'].search([
                    ('student_id', '=', student.id),
                    ('status', '=', 'ongoing')
                ])
                open_history.write({'status': 'failed_again'})
                
                self.env['university.student.repeat.history'].create({
                    'student_id': student.id,
                    'current_academic_year_name': rec.academic_year_name,
                    'level_repeated': rec.level,
                    'status': 'ongoing',
                    'notes': _("Repeating all subjects") if rec.status_result == 'repeating_all' else _("Repeating %s subject(s)") % len(rec.failed_subject_ids)
                })

                # Update Student
                student.write({
                    'is_repeater': True,
                    'batch_id': next_batch.id, # Reassign to next batch
                })

                # Trigger Re-registration
                student.action_trigger_re_registration(
                    is_repetition=True, 
                    failed_subject_ids=rec.failed_subject_ids if rec.status_result == 'repeating_some' else rec.failed_subject_ids # if repeating all, failed subjects don't restrict invoicing
                )
                
                student.message_post(body=_("Student set to repeat. Reassigned to Batch %s. Added to repetition history.") % next_batch.name)
                
            elif rec.status_result == 'promoted':
                student.action_promote()
                
                open_history = self.env['university.student.repeat.history'].search([
                    ('student_id', '=', student.id),
                    ('status', '=', 'ongoing')
                ])
                for oh in open_history:
                    if "External Exam Attempt" in (oh.notes or ""):
                        oh.status = 'passed_as_external'
                    else:
                        oh.status = 'passed'
                
                student.is_repeater = False
                # registration_status is updated via re-registration link

            rec.write({'state': 'confirmed'})
