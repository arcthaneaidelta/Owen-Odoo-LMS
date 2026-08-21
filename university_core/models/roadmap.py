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
            # ('academic_year_duration', 'Academic Year Duration'),
            ('registration', 'Registration Window'),
            ('main_exam_s1', 'Main Exam - Semester 1'),
            ('main_exam_s2', 'Main Exam - Semester 2'),
            ('second_exam', 'Second / Substitute Exam'),
            ('supplementary_exam', 'Supplementary Exam'),
            ('clearance_exam', 'Clearance Exam'),
            ('level_promotion', 'Promote Batch to Next Level'),
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
    academic_year_id = fields.Many2one(
        'university.academic_year',
        string='Academic Year',
        ondelete='cascade',
        required=True,
    )
    registration_start = fields.Date(string='Registration Start Date')
    registration_end = fields.Date(string='Registration End Date')
    is_processed = fields.Boolean(
        string='Automation Processed',
        default=False,
        help='Checked automatically when the cron job runs the promotion or transition.',
        readonly=True,
    )
    color = fields.Integer(
        string='Color Index',
        compute='_compute_color',
        store=True,
    )

    @api.depends('event_type')
    def _compute_color(self):
        color_map = {
            'registration': 1,           # Red
            # 'academic_year_duration': 2, # Orange
            'main_exam_s1': 3,           # Yellow
            'main_exam_s2': 3,           # Yellow
            'second_exam': 5,            # Dark purple
            'supplementary_exam': 6,     # Pink
            'clearance_exam': 8,         # Light Blue
            'level_promotion': 10,       # Green
            'holiday': 4,                # Light blue
            'event': 7,                  # Teal
            'other': 0,                  # Grey
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

