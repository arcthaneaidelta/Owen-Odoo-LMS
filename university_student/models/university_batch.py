# -*- coding: utf-8 -*-
from odoo import models, fields, api

class UniversityBatch(models.Model):
    _inherit = 'university.batch'

    current_level = fields.Selection(
        [
            ('1', 'Level 1'),
            ('2', 'Level 2'),
            ('3', 'Level 3'),
            ('4', 'Level 4'),
            ('5', 'Level 5'),
            ('6', 'Level 6'),
        ],
        string='Current Level',
        tracking=True,
    )

    student_ids = fields.Many2many(
        'university.student',
        'university_batch_student_rel',
        'batch_id',
        'student_id',
        string='Students',
    )
    student_count = fields.Integer(
        string='Student Count',
        compute='_compute_student_count',
    )

    @api.depends('student_ids')
    def _compute_student_count(self):
        for rec in self:
            rec.student_count = len(rec.student_ids)

    def action_promote(self):
        for batch in self:
            if not batch.current_level:
                batch.current_level = '1'
            
            current = int(batch.current_level)
            duration = batch.program_id.duration_years or 4
            
            if current < duration:
                batch.current_level = str(current + 1)
                batch.message_post(body=f"Batch promoted to Level {batch.current_level}")
                
                # Promote all students in this batch
                for student in batch.student_ids:
                    student.action_promote()
            else:
                batch.state = 'completed'
                batch.message_post(body="Batch has completed the program.")
