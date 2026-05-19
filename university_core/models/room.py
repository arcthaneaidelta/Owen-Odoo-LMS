# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class UniversityRoom(models.Model):
    _name = 'university.room'
    _description = 'University Room / Facility'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Room Name/Number', required=True, tracking=True)
    capacity = fields.Integer(string='Capacity', required=True, tracking=True)
    room_type = fields.Selection([
        ('classroom', 'Classroom'),
        ('lab', 'Laboratory'),
        ('field', 'Field / Clinical Location'),
        ('hall', 'Lecture Hall'),
        ('other', 'Other')
    ], string='Room Type', required=True, default='classroom', tracking=True)
    is_active = fields.Boolean(string='Active', default=True)

    @api.constrains('capacity')
    def _check_capacity(self):
        for room in self:
            if room.capacity <= 0:
                raise ValidationError(_('Room capacity must be strictly greater than zero.'))
