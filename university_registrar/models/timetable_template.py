# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class UniversityTimetableTemplate(models.Model):
    _name = 'university.timetable.template'
    _description = 'Timetable Template'
    _inherit = ['mail.thread']

    name = fields.Char(string='Template Name', required=True, tracking=True)
    program_id = fields.Many2one('university.program', string='Program', required=True)
    level = fields.Selection(
        [
            ('1', 'Level 1'),
            ('2', 'Level 2'),
            ('3', 'Level 3'),
            ('4', 'Level 4'),
            ('5', 'Level 5'),
            ('6', 'Level 6'),
        ],
        string='Level',
        required=True,
    )
    semester = fields.Integer(string='Semester', default=1)
    
    line_ids = fields.One2many(
        'university.timetable.template.line',
        'template_id',
        string='Schedule Lines',
    )
    
    def action_apply_to_batch(self):
        """Action to launch a wizard to apply this template to a specific batch and academic year."""
        self.ensure_one()
        return {
            'name': _('Generate Timetable'),
            'type': 'ir.actions.act_window',
            'res_model': 'university.timetable.apply.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
            }
        }


class UniversityTimetableTemplateLine(models.Model):
    _name = 'university.timetable.template.line'
    _description = 'Timetable Template Line'

    template_id = fields.Many2one('university.timetable.template', string='Template', required=True, ondelete='cascade')
    subject_id = fields.Many2one('university.subject', string='Subject', required=True)
    
    day_of_week = fields.Selection(
        [
            ('0', 'Saturday'),
            ('1', 'Sunday'),
            ('2', 'Monday'),
            ('3', 'Tuesday'),
            ('4', 'Wednesday'),
            ('5', 'Thursday'),
            ('6', 'Friday'),
        ],
        string='Day of Week',
        required=True,
    )
    start_time = fields.Float(string='Start Time', required=True)
    end_time = fields.Float(string='End Time', required=True)
    session_type = fields.Selection(
        [
            ('lecture', 'Lecture'),
            ('practical', 'Practical/Lab'),
            ('tutorial', 'Tutorial'),
            ('clinical', 'Clinical'),
        ],
        string='Session Type',
        default='lecture',
    )

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for rec in self:
            if rec.start_time >= rec.end_time:
                raise ValidationError(_('End time must be after start time.'))
            if not (0 <= rec.start_time < 24) or not (0 < rec.end_time <= 24):
                raise ValidationError(_('Times must be valid 24h values.'))
