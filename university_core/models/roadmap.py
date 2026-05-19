# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class UniversityBatchRoadmap(models.Model):
    _name = 'university.batch.roadmap'
    _description = 'Batch Academic Roadmap'
    _order = 'date_start, id'

    name = fields.Char(
        string='Activity/Event Name',
        required=True,
        tracking=True,
    )
    batch_id = fields.Many2one(
        'university.batch',
        string='Batch',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    event_type = fields.Selection(
        [
            ('registration', 'Registration'),
            ('class_start', 'Class Commencement'),
            ('examination', 'Examination Dates'),
            ('holiday', 'Holiday / Break'),
            ('event', 'Academic Event / Activity'),
            ('other', 'Other'),
        ],
        string='Activity Type',
        required=True,
        default='other',
        tracking=True,
    )
    date_start = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
    )
    date_stop = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
    )
    description = fields.Text(
        string='Details / Notes',
    )
    color = fields.Integer(
        string='Color Index',
        compute='_compute_color',
        store=True,
    )

    @api.depends('event_type')
    def _compute_color(self):
        # Map each event type to a specific color index (1 to 11)
        color_map = {
            'registration': 1,   # Red
            'class_start': 2,    # Orange
            'examination': 3,    # Yellow
            'holiday': 4,        # Light blue
            'event': 5,          # Dark purple
            'other': 6,          # Pink
        }
        for record in self:
            record.color = color_map.get(record.event_type, 9)

    @api.constrains('date_start', 'date_stop')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_stop and record.date_stop < record.date_start:
                raise ValidationError(_("The End Date cannot be earlier than the Start Date."))

    @api.depends('name', 'batch_id.name', 'batch_id.batch_number')
    def _compute_display_name(self):
        for record in self:
            batch_name = record.batch_id.name or record.batch_id.batch_number
            if batch_name:
                record.display_name = f"[{batch_name}] {record.name}"
            else:
                record.display_name = record.name

