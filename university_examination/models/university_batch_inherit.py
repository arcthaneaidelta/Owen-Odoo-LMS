from odoo import models, fields

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
