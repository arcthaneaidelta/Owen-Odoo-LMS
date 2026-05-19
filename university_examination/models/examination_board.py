from odoo import models, fields, api

class ExaminationBoardSession(models.Model):
    _name = 'examination.board.session'
    _description = 'Result Moderation Board Session'

    name = fields.Char(string='Session Name', required=True)
    board_type = fields.Selection([
        ('program', 'Program Board'),
        ('college', 'College Board'),
        ('scientific', 'Scientific Board'),
    ], string='Board Type', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('closed', 'Closed'),
    ], string='Status', default='draft')
    
    adjustment_ids = fields.One2many('examination.board.adjustment', 'session_id', string='Adjustments')

    def action_open(self):
        self.state = 'open'

    def action_close(self):
        # Process adjustments
        for adjustment in self.adjustment_ids:
            if adjustment.adjustment_type == 'row' and adjustment.student_id:
                print('111112123456781234567234567')
                # Find the specific student's grade line for the subject
                lines = self.env['examination.grade.entry.line'].search([
                    ('entry_id.student_id', '=', adjustment.student_id.id),
                    ('subject_id', '=', adjustment.subject_id.id)
                ])
                print(lines)
                for line in lines:
                    line.exam_score += adjustment.marks_added
            elif adjustment.adjustment_type == 'column':
                # Apply to all students for this subject in the current cycle
                # (Assuming we might want to restrict by cycle or batch if defined, but globally for now)
                lines = self.env['examination.grade.entry.line'].search([
                    ('subject_id', '=', adjustment.subject_id.id)
                ])
                for line in lines:
                    line.exam_score += adjustment.marks_added

        # Trigger OTP and lock results (placeholder for future extension)
        self.state = 'closed'

class ExaminationBoardAdjustment(models.Model):
    _name = 'examination.board.adjustment'
    _description = 'Grade Adjustment'

    session_id = fields.Many2one('examination.board.session', required=True)
    adjustment_type = fields.Selection([
        ('row', 'Row-Based (Student Level)'),
        ('column', 'Column-Based (Subject Level)'),
    ], required=True)
    student_id = fields.Many2one('university.student', string='Student')
    subject_id = fields.Many2one('university.subject', string='Subject', required=True)
    marks_added = fields.Float('Marks Added', required=True)
    justification = fields.Text('Justification', required=True)
