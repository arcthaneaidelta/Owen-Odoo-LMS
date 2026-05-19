# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class UniversityCollege(models.Model):
    _name = 'university.college'
    _description = 'College'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'university_id, name'

    name = fields.Char(
        string='College Name',
        required=True,
        translate=True,
        tracking=True,
    )
    name_ar = fields.Char(string='Arabic Name', tracking=True)
    name_en = fields.Char(string='English Name', tracking=True)
    code = fields.Char(string='College Code', tracking=True)

    university_id = fields.Many2one(
        'university.university',
        string='University',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    dean_name = fields.Char(string='Dean Name', translate=True, tracking=True)
    dean_employee_id = fields.Many2one(
        'hr.employee',
        string='Dean (Employee)',
    )

    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    address = fields.Text(string='Address', translate=True)

    program_ids = fields.One2many(
        'university.program',
        'college_id',
        string='Programs',
    )
    department_ids = fields.One2many(
        'university.department',
        'college_id',
        string='Departments',
    )
    program_count = fields.Integer(
        string='Program Count',
        compute='_compute_program_count',
    )
    department_count = fields.Integer(
        string='Department Count',
        compute='_compute_department_count',
    )

    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes', translate=True)

    _sql_constraints = [
        (
            'code_university_uniq',
            'unique(code, university_id)',
            'College code must be unique per university.',
        ),
    ]

    @api.depends('program_ids')
    def _compute_program_count(self):
        for rec in self:
            rec.program_count = len(rec.program_ids)

    @api.depends('department_ids')
    def _compute_department_count(self):
        for rec in self:
            rec.department_count = len(rec.department_ids)

    def name_get(self):
        result = []
        for rec in self:
            name = rec.name_ar or rec.name or rec.name_en or ''
            if rec.university_id:
                uni = rec.university_id.name_ar or rec.university_id.name or ''
                name = f'{name} ({uni})'
            result.append((rec.id, name))
        return result
