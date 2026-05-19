# -*- coding: utf-8 -*-
from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    university_subject_ids = fields.Many2many(
        'university.subject',
        string='Subjects Taught',
        domain="[('program_id', '=', university_program_id)]",
        help="Subjects this teacher is qualified or assigned to teach."
    )
