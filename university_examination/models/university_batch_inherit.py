from odoo import models, fields

class UniversityBatchRoadmap(models.Model):
    _inherit = 'university.batch.roadmap'

    event_type = fields.Selection(selection_add=[
        ('main_exam_s1', 'Main Exam - Semester 1'),
        ('main_exam_s2', 'Main Exam - Semester 2'),
        ('second_exam', 'Second Exam'),
        ('supplementary_exam', 'Supplementary Exam'),
    ], ondelete={
        'main_exam_s1': 'set default',
        'main_exam_s2': 'set default',
        'second_exam': 'set default',
        'supplementary_exam': 'set default',
    })

class UniversityBatch(models.Model):
    _inherit = 'university.batch'

    evaluation_method = fields.Selection([
        ('method_a', 'Method A (Standard GPA)'),
        ('method_b', 'Method B (Alternative Scale)'),
    ], string='Evaluation Method', required=True, default='method_a',
       help="Dictates GPA formulas, grading scales, and total score ranges for that batch's entire lifecycle and cannot be changed once assigned.") # removing states parameter to avoid Odoo 17/18 deprecation
       
    student_count = fields.Integer(string='Students Enrolled', compute='_compute_student_count')

    def _compute_student_count(self):
        for rec in self:
            rec.student_count = self.env['university.student'].search_count([('batch_id', '=', rec.id)])

    def _cron_process_roadmaps(self):
        # Call super first to process core events
        super()._cron_process_roadmaps()
        
        # Process exam specific events
        today = fields.Date.today()
        events = self.env['university.batch.roadmap'].search([
            ('date_start', '<=', today),
            ('is_processed', '=', False),
            ('event_type', 'in', ['main_exam_s1', 'main_exam_s2', 'second_exam', 'supplementary_exam']),
            ('batch_id.state', '=', 'active')
        ])

        print(events)

        for event in events:
            action_taken = ""
            batch = event.batch_id

            print(batch)
            
            # Auto-generate examination cycle
            exam_type_map = {
                'main_exam_s1': 'main',
                'main_exam_s2': 'main',
                'second_exam': 'second',
                'supplementary_exam': 'supplementary'
            }
            semester = '1' if 's1' in event.event_type else '2'
            
            # Find the active academic year for this batch
            active_year = batch.academic_year_ids.filtered(lambda y: y.state == 'active')
            year_name = active_year[0].name if active_year else event.new_academic_year_name or 'Current'
            
            print("Active---------------------------------Year:", year_name)
            cycle_vals = {
                'name': event.name,
                'batch_id': batch.id,
                'academic_year_name': year_name,
                'semester': semester,
                'exam_type': exam_type_map.get(event.event_type, 'main'),
                'start_date': event.date_start,
                'end_date': event.date_stop,
                'state': 'draft',
            }
            cycle = self.env['examination.cycle'].create(cycle_vals)
            print(cycle)
            # Automatically generate Draft Seating plans for each subject
            cycle.auto_generate_seating_drafts()
            
            action_taken = f"Examination Cycle '{cycle.name}' automatically created in Draft."
            
            
            if action_taken:
                event.write({'is_processed': True})
                batch.message_post(body=f"Roadmap Automation Triggered: {action_taken}")

class UniversityStudent(models.Model):
    _inherit = 'university.student'

    troll_number = fields.Char(string='Troll Number (Exam Seat Number)', readonly=True, copy=False)

