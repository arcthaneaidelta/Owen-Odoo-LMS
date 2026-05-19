# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityUniversity(models.Model):
    _name = 'university.university'
    _description = 'University'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # ─── Basic Info ───────────────────────────────────────────────────────────
    name = fields.Char(
        string='University Name',
        required=True,
        translate=True,
        tracking=True,
    )
    name_ar = fields.Char(
        string='Arabic Name',
        tracking=True,
    )
    name_en = fields.Char(
        string='English Name',
        tracking=True,
    )
    code = fields.Char(
        string='University Code',
        required=True,
        copy=False,
        tracking=True,
    )
    ministry_registration_number = fields.Char(
        string='Ministry Registration Number',
        required=True,
        copy=False,
        tracking=True,
    )
    logo = fields.Binary(
        string='University Logo',
        attachment=True,
    )
    logo_filename = fields.Char(string='Logo Filename')

    # ─── Contact ──────────────────────────────────────────────────────────────
    address = fields.Text(
        string='Address',
        translate=True,
    )
    city = fields.Char(string='City', translate=True)
    state_id = fields.Many2one(
        'res.country.state',
        string='State',
    )
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        default=lambda self: self.env.ref('base.sd', raise_if_not_found=False),
    )
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    website = fields.Char(string='Website')

    # ─── Relational ───────────────────────────────────────────────────────────
    college_ids = fields.One2many(
        'university.college',
        'university_id',
        string='Colleges',
    )
    college_count = fields.Integer(
        string='College Count',
        compute='_compute_college_count',
    )

    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes', translate=True)

    # ─── SQL Constraints ──────────────────────────────────────────────────────
    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'University code must be unique.'),
        (
            'ministry_reg_uniq',
            'unique(ministry_registration_number)',
            'Ministry registration number must be unique.',
        ),
    ]

    # ─── Computes ─────────────────────────────────────────────────────────────
    @api.depends('college_ids')
    def _compute_college_count(self):
        for rec in self:
            rec.college_count = len(rec.college_ids)

    # ─── Display ──────────────────────────────────────────────────────────────
    def name_get(self):
        result = []
        for rec in self:
            name = rec.name_ar or rec.name or rec.name_en or ''
            result.append((rec.id, name))
        return result
