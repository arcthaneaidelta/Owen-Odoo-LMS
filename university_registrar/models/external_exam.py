# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date

class UniversityExternalExam(models.Model):
    _name = 'university.student.external.exam'
    _description = 'Student External Exam Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')

    student_id = fields.Many2one(
        'university.student', 
        string='Student', 
        required=True, 
        tracking=True,
        domain="['|', ('active', '=', False), ('active', '=', True), ('academic_standing', '=', 'expelled')]", # Only allows expelled students
        help="Only expelled students can request an external exam."
    )
    program_id = fields.Many2one(
        'university.program',
        string='Program',
        related='student_id.program_id',
        store=True,
    )
    academic_year_id = fields.Many2one(
        'university.academic_year',
        string='Academic Year for Exam',
        required=True,
        tracking=True,
    )

    subject_ids = fields.Many2many(
        'university.subject',
        string='Subjects to Retake',
        required=True,
    )

    invoice_id = fields.Many2one('account.move', string='Exam Fee Invoice', readonly=True)

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved (Rejoined)'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('university.external.exam') or 'New'
        return super().create(vals_list)

    @api.constrains('student_id')
    def _check_max_duration(self):
        for rec in self:
            student = rec.student_id
            if student.admission_date and student.program_id:
                # 10 years for a 5 year program
                max_span = (student.program_id.duration_years or 4) * 2
                years_since_admission = date.today().year - student.admission_date.year
                if years_since_admission > max_span:
                    raise ValidationError(_("This student has exceeded the maximum program duration of %s years and is not eligible for an external exam.") % max_span)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        for rec in self:
            rec.write({'state': 'approved'})
            
            # Log this as an external repeat attempt
            open_history = self.env['university.student.repeat.history'].search([
                ('student_id', '=', rec.student_id.id),
                ('status', '=', 'ongoing')
            ])
            open_history.write({'status': 'failed_again'})
            
            self.env['university.student.repeat.history'].create({
                'student_id': rec.student_id.id,
                'academic_year_id': rec.academic_year_id.id,
                'level_repeated': rec.student_id.current_level,
                'status': 'ongoing',
                'notes': _("External Exam Attempt")
            })

            # Rejoin the student
            rec.student_id.write({
                'academic_standing': 'good_standing', # They have another chance
                'active': True, # Unarchive
                'is_repeater': True,
                'registration_status': 'unregistered' # They must pay the external exam fees to register
            })
            rec.student_id.message_post(body=_("Student approved for External Exam and has rejoined the program to retake %s subject(s). Added to repetition history.") % len(rec.subject_ids))

    def action_reject(self):
        self.write({'state': 'rejected'})
