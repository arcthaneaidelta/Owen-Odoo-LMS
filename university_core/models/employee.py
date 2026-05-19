# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_teacher = fields.Boolean(
        string='Is a Teacher?',
        default=False,
        help='Check this box if this employee is an academic teacher or instructor.'
    )
    
    academic_qualification = fields.Selection(
        [
            ('diploma', 'Diploma'),
            ('bachelors', 'Bachelors'),
            ('masters', 'Masters'),
            ('phd', 'PhD'),
            ('other', 'Other')
        ],
        string='Highest Academic Qualification',
        tracking=True
    )
    
    university_department_id = fields.Many2one(
        'university.department',
        string='Academic Department',
        tracking=True
    )
    
    university_program_id = fields.Many2one(
        'university.program',
        string='Academic Program',
        domain="[('department_id', '=', university_department_id)]",
        tracking=True
    )

    @api.onchange('university_department_id')
    def _onchange_university_department_id(self):
        """Clear program and subjects when department changes."""
        self.university_program_id = False
        if hasattr(self, 'university_subject_ids'):
            self.university_subject_ids = [(5, 0, 0)]

    @api.onchange('university_program_id')
    def _onchange_university_program_id(self):
        """Clear subjects when program changes."""
        if hasattr(self, 'university_subject_ids'):
            self.university_subject_ids = [(5, 0, 0)]

    # @api.onchange('is_teacher')
    # def _onchange_is_teacher(self):
    #     for record in self:
    #         if record.is_teacher:
    #             record.job_title = 'Teacher'
    #         else:
    #             record.job_title = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'is_teacher' in vals:
                if vals['is_teacher']:
                    # Only overwrite if they didn't manually type a different title like 'Professor'
                    if not vals.get('job_title'):
                        vals['job_title'] = 'Teacher'
                else:
                    if vals.get('job_title') == 'Teacher':
                        vals['job_title'] = False
        return super().create(vals_list)

    def write(self, vals):
        if 'is_teacher' in vals:
            if vals['is_teacher']:
                if not vals.get('job_title'):
                    vals['job_title'] = 'Teacher'
            else:
                # If they uncheck it, empty the title if it was 'Teacher'
                if not vals.get('job_title'):
                    vals['job_title'] = False
        return super().write(vals)
