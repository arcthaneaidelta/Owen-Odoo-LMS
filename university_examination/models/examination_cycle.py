from odoo import models, fields, api, _

class ExaminationCycle(models.Model):
    _name = 'examination.cycle'
    _description = 'Examination Cycle'

    name = fields.Char(string='Name', required=True)
    academic_year_id = fields.Many2one('university.academic_year', string='Academic Year', required=True)
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
