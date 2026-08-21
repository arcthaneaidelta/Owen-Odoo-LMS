# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityAcademicYear(models.Model):
    _name = 'university.academic_year'
    _description = 'Academic Year'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'
    
    name = fields.Char(
        string='Academic Year/Level',
        required=True,
        tracking=True,
        help='e.g. Year 1, Year 2, 2023/2024',
    )
    batch_id = fields.Many2one(
        'university.batch',
        string='Batch',
        required=True,
        ondelete='cascade',
    )
    date_start = fields.Date(string='Start Date', required=True, tracking=True)
    date_end = fields.Date(string='End Date', required=True, tracking=True)
    registration_start = fields.Date(string='Registration Start Date', tracking=True)
    registration_deadline = fields.Date(string='Registration Deadline', tracking=True, help='Date by which students must be registered or frozen. Otherwise they face late fees or expulsion.')
    late_registration_deadline = fields.Date(string='Late Registration Deadline', tracking=True, help='Final date for late registration with fine.')
    late_registration_fee = fields.Float(string='Late Registration Fee', default=0.0, tracking=True)

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

    roadmap_event_count = fields.Integer(compute='_compute_roadmap_event_count')

    def _compute_roadmap_event_count(self):
        for record in self:
            record.roadmap_event_count = self.env['university.batch.roadmap'].search_count([('academic_year_id', '=', record.id)])

    def action_open_roadmap(self):
        self.ensure_one()
        return {
            'name': f'Roadmap: {self.name}',
            'view_mode': 'calendar,list,form',
            'res_model': 'university.batch.roadmap',
            'domain': [('academic_year_id', '=', self.id)],
            'context': {
                'default_batch_id': self.batch_id.id,
                'default_academic_year_id': self.id,
            },
            'type': 'ir.actions.act_window',
        }

    _sql_constraints = [
        ('name_batch_uniq', 'unique(name, batch_id)', 'Academic year name must be unique per batch.'),
    ]

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_start >= rec.date_end:
                raise ValidationError(_('End date must be after start date.'))



    def action_activate(self):
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed'})
