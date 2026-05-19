# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class UniversityDepartment(models.Model):
    _name = 'university.department'
    _description = 'University Department'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'college_id, name'

    name = fields.Char(
        string='Department Name',
        required=True,
        translate=True,
        tracking=True,
    )
    name_ar = fields.Char(string='Arabic Name', tracking=True)
    # name_en = fields.Char(string='English Name', tracking=True)
    code = fields.Char(string='Department Code', tracking=True)

    college_id = fields.Many2one(
        'university.college',
        string='College',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    university_id = fields.Many2one(
        'university.university',
        string='University',
        related='college_id.university_id',
        store=True,
        readonly=True,
    )

    head_name = fields.Char(
        string='Head of Department',
        translate=True,
        tracking=True,
    )
    head_employee_id = fields.Many2one(
        'hr.employee',
        string='Head (Employee)',
    )

    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')

    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes', translate=True)

    _sql_constraints = [
        (
            'code_college_uniq',
            'unique(code, college_id)',
            'Department code must be unique per college.',
        ),
    ]

    def name_get(self):
        result = []
        for rec in self:
            name = rec.name_ar or rec.name or rec.name_en or ''
            result.append((rec.id, name))
        return result
