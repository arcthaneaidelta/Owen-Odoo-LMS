from odoo import models, fields, api

class StudentOutcome(models.Model):
    _inherit = 'university.student'

    academic_status = fields.Selection([
        ('pass', 'Pass'),
        ('repeat_specific', 'Repeat Specific Subjects'),
        ('repeat_all', 'Repeat All Subjects'),
        ('dismissed', 'Dismissed (Expelled)'),
    ], string='End of Year Status')
    
    cumulative_gpa = fields.Float('Cumulative GPA', compute='_compute_gpa', store=True)

    def _compute_gpa(self):
        for rec in self:
            rec.cumulative_gpa = 0.0 # to be calculated
