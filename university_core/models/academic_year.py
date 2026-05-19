# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityAcademicYear(models.Model):
    _name = 'university.academic_year'
    _description = 'Academic Year'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Academic Year',
        required=True,
        tracking=True,
        help='e.g. 2023/2024',
    )
    date_start = fields.Date(string='Start Date', required=True, tracking=True)
    date_end = fields.Date(string='End Date', required=True, tracking=True)
    registration_deadline = fields.Date(string='Registration Deadline', tracking=True, help='Date by which students must be registered or frozen. Otherwise they face late fees or expulsion.')
    late_registration_deadline = fields.Date(string='Late Registration Deadline', tracking=True, help='Final date for late registration with fine.')
    late_registration_fee = fields.Float(string='Late Registration Fee', default=0.0, tracking=True)
    is_current = fields.Boolean(
        string='Current Year',
        default=False,
        tracking=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('closed', 'Closed'),
        ],
        string='State',
        default='draft',
        tracking=True,
    )

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Academic year name must be unique.'),
    ]

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_start >= rec.date_end:
                raise ValidationError(_('End date must be after start date.'))

    @api.constrains('is_current')
    def _check_single_current(self):
        if self.filtered(lambda r: r.is_current):
            others = self.search([('is_current', '=', True), ('id', 'not in', self.ids)])
            if others:
                raise ValidationError(_('Only one academic year can be marked as current.'))

    def action_activate(self):
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed', 'is_current': False})
