# -*- coding: utf-8 -*-
from odoo import models, fields, api

class UniversityStudent(models.Model):
    _inherit = 'university.student'

    curriculum_id = fields.Many2one(
        'university.curriculum',
        string='Student Curriculum',
        tracking=True,
        help='A separate copy of the batch curriculum for this individual student.'
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.batch_id:
                rec._generate_student_curriculum()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'batch_id' in vals:
            for rec in self:
                if rec.batch_id:
                    rec._generate_student_curriculum()
        return res

    def _generate_student_curriculum(self):
        self.ensure_one()
        batch_curr = self.batch_id.curriculum_id
        if not batch_curr:
            return
            
        # Use display_name_ar or fallback to a standard string
        student_name = self.display_name_ar or self.name_en or 'Student'
        
        # 1. First time generation (Admission)
        if not self.curriculum_id:
            student_curr = batch_curr.copy({
                'name': f"{batch_curr.name} - {student_name}",
                'curriculum_type': 'student',
                'parent_id': batch_curr.id,
                'batch_id': False,
                'student_id': self.id,
                'state': 'draft',
                'is_locked': False,
            })
            # Standard write does not trigger recursion here because batch_id is not in vals
            self.write({'curriculum_id': student_curr.id})
            return
            
        # 2. Curriculum Splitting (Repeating / Changing Batches)
        if self.curriculum_id.parent_id != batch_curr:
            # Student moved to a new batch (e.g. B3 -> B4).
            # Keep passed levels from old curriculum. Replace current and future levels with new batch's curriculum.
            try:
                current_level_int = int(self.current_level or 1)
            except ValueError:
                current_level_int = 1
                
            # Remove lines for current_level and above from student's existing curriculum
            lines_to_remove = self.curriculum_id.line_ids.filtered(lambda l: l.year_level >= current_level_int)
            lines_to_remove.unlink()
            
            # Copy lines for current_level and above from the NEW batch's curriculum
            lines_to_copy = batch_curr.line_ids.filtered(lambda l: l.year_level >= current_level_int)
            for line in lines_to_copy:
                line.copy({'curriculum_id': self.curriculum_id.id})
                
            # Update parent reference and name to reflect the split
            self.curriculum_id.write({
                'parent_id': batch_curr.id,
                'name': f"Split Curriculum - {student_name} (Now on {batch_curr.name})"
            })
