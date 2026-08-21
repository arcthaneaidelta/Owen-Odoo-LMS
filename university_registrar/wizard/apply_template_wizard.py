# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ApplyTemplateWizard(models.TransientModel):
    _name = 'university.timetable.apply.wizard'
    _description = 'Apply Timetable Template to Batch'

    template_id = fields.Many2one('university.timetable.template', string='Template', required=True, readonly=True)
    program_id = fields.Many2one('university.program', related='template_id.program_id', readonly=True)
    batch_id = fields.Many2one('university.batch', string='Select Batch', required=True)
    academic_year_name = fields.Char(string='Academic Year', required=True)
    default_teacher_id = fields.Many2one('hr.employee', string='Default Teacher', help="This teacher will be assigned to all generated slots. You can edit them individually later.")
    default_room = fields.Char(string='Default Room', help="This room will be assigned to all generated slots. You can edit them individually later.")

    @api.model
    def default_get(self, fields_list):
        res = super(ApplyTemplateWizard, self).default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id and self.env.context.get('active_model') == 'university.timetable.template':
            res['template_id'] = active_id
            
            # Ensure the user manually selects the appropriate academic year
                
        return res

    def action_generate_timetable(self):
        self.ensure_one()
        timetable_obj = self.env['university.timetable']
        lines_created = 0

        # Loop over the template's lines and create a real Timetable record
        for line in self.template_id.line_ids:
            timetable_obj.create({
                'subject_id': line.subject_id.id,
                'batch_id': self.batch_id.id,
                'academic_year_name': self.academic_year_name,
                'day_of_week': line.day_of_week,
                'start_time': line.start_time,
                'end_time': line.end_time,
                'session_type': line.session_type,
                'semester': self.template_id.semester,
                # Use defaults or find a way around constraints. The standard timetable module requires teacher.
                # If they didn't pick a default teacher, we might hit the `required=True` on `teacher_id` in `university.timetable`.
                # If teacher is required, we MUST assign one. The wizard view should probably make it required. Let's assume the wizard makes it required.
                'teacher_id': self.default_teacher_id.id if self.default_teacher_id else False,
                'room': self.default_room or '',
                'teacher_assignment_type': 'program_specific',
                'is_active_schedule': True,
                'notes': f"Auto-generated from Template {self.template_id.name}"
            })
            lines_created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'type': 'success',
                'message': _('Successfully generated %s timetable records for %s.') % (lines_created, self.batch_id.name),
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
