# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class UniversitySpecialization(models.Model):
    _name = 'university.specialization'
    _description = 'Program Specialization'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'program_id, name'

    name = fields.Char(
        string='Specialization Name',
        required=True,
        translate=True,
        tracking=True,
    )
    name_ar = fields.Char(string='Arabic Name', tracking=True)
    name_en = fields.Char(string='English Name', tracking=True)
    code = fields.Char(string='Specialization Code', tracking=True)

    program_id = fields.Many2one(
        'university.program',
        string='Program',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    college_id = fields.Many2one(
        'university.college',
        string='College',
        related='program_id.college_id',
        store=True,
        readonly=True,
    )
    university_id = fields.Many2one(
        'university.university',
        string='University',
        related='program_id.university_id',
        store=True,
        readonly=True,
    )

    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes', translate=True)

    _sql_constraints = [
        (
            'code_program_uniq',
            'unique(code, program_id)',
            'Specialization code must be unique per program.',
        ),
    ]

    def name_get(self):
        result = []
        for rec in self:
            name = rec.name_ar or rec.name or rec.name_en or ''
            if rec.program_id:
                prog = rec.program_id.name_ar or rec.program_id.name or ''
                name = f'{name} - {prog}'
            result.append((rec.id, name))
        return result
