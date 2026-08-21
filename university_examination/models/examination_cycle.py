from odoo import models, fields, api, _

class ExaminationCycle(models.Model):
    _name = 'examination.cycle'
    _description = 'Examination Cycle'

    name = fields.Char(string='Name', required=True)
    batch_id = fields.Many2one('university.batch', string='Batch', required=True, ondelete='cascade')
    academic_year_name = fields.Char(string='Academic Year', required=True)
    semester = fields.Selection([('1', 'Semester 1'), ('2', 'Semester 2')], string='Semester', required=True)
    exam_type = fields.Selection([
        ('main', 'Main Examination'),
        ('second', 'Second (Substitute) Examination'),
        ('supplementary', 'Supplementary Examination'),
        ('clearance', 'Clearance Examination'),
    ], string='Exam Type', required=True)
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ], string='Status', default='draft')
    
    seating_ids = fields.One2many('examination.seating', 'cycle_id', string='Seating Plans')

    def auto_generate_seating_drafts(self):
        for rec in self:
            print('00000000000000000000')
            print(rec.batch_id)
            print(rec.batch_id.curriculum_id)
            if not rec.batch_id or not rec.batch_id.curriculum_id:
                continue
            
            # Find the active curriculum
            active_curriculum = False
            if rec.batch_id.curriculum_id.state == 'active':
                print("Active---------------------------------")
                active_curriculum = rec.batch_id.curriculum_id
            elif rec.batch_id.curriculum_id.parent_id:
                active_curriculum = rec.batch_id.curriculum_id.parent_id
                
            if not active_curriculum:
                continue
                
            # Assume current level from batch
            current_level = int(rec.batch_id.current_level or 1)
            print("Current Level:", current_level)
            
            # Get all subjects for this semester and level
            subject_lines = active_curriculum.line_ids.filtered(
                lambda l: l.year_level == current_level and l.semester == int(rec.semester)
            )

            # For Supplementary Exam, we might need all subjects from Semester 1 and 2 if both are held together.
            if rec.exam_type == 'supplementary':
                subject_lines = active_curriculum.line_ids.filtered(
                    lambda l: l.year_level == current_level
                )
            
            # Create a seating draft for each subject
            for line in subject_lines:
                existing = self.env['examination.seating'].search([
                    ('cycle_id', '=', rec.id),
                    ('subject_id', '=', line.subject_id.id)
                ])
                if not existing:
                    self.env['examination.seating'].create({
                        'cycle_id': rec.id,
                        'subject_id': line.subject_id.id,
                        'exam_date': rec.start_date, # Default to cycle start, admin can change
                        'start_time': 9.0, # Default to 9:00 AM
                        'end_time': 12.0,  # Default to 12:00 PM
                    })
