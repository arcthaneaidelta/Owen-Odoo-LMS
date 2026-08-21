# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import random
import string
from datetime import datetime

class UniversityStudentResignation(models.Model):
    _name = 'university.student.resignation'
    _description = 'Student Resignation Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='New')
    student_id = fields.Many2one('university.student', string='Student', required=True, tracking=True)
    academic_year_name = fields.Char(string='Academic Year', tracking=True)
    level = fields.Selection([
        ('1', 'Level 1'),
        ('2', 'Level 2'),
        ('3', 'Level 3'),
        ('4', 'Level 4'),
        ('5', 'Level 5'),
        ('6', 'Level 6'),
    ], string='Level', tracking=True)
    
    reason = fields.Text(string='Reason for Resignation', required=True, tracking=True)
    resignation_date = fields.Date(string='Resignation Date', default=fields.Date.today, tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('otp_sent', 'OTP Sent'),
        ('otp_verified', 'OTP Verified'),
        ('clearance', 'Clearance in Progress'),
        ('registrar_approval', 'Registrar Approval'),
        ('academic_affairs', 'Academic Affairs Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # OTP Logic
    otp_code = fields.Char(string='OTP Code', copy=False, readonly=True)
    otp_verified = fields.Boolean(string='OTP Verified', default=False, readonly=True)

    # Departmental Clearance
    library_clearance = fields.Selection([('pending', 'Pending'), ('cleared', 'Cleared')], string='Library Clearance', default='pending', tracking=True)
    lab_clearance = fields.Selection([('pending', 'Pending'), ('cleared', 'Cleared')], string='Laboratory Clearance', default='pending', tracking=True)
    finance_clearance = fields.Selection([('pending', 'Pending'), ('cleared', 'Cleared')], string='Financial Clearance', default='pending', tracking=True)
    admission_clearance = fields.Selection([('pending', 'Pending'), ('cleared', 'Cleared')], string='Admission Clearance', default='pending', tracking=True)
    
    library_cleared_by = fields.Many2one('res.users', string='Library Cleared By', readonly=True)
    lab_cleared_by = fields.Many2one('res.users', string='Lab Cleared By', readonly=True)
    finance_cleared_by = fields.Many2one('res.users', string='Finance Cleared By', readonly=True)
    admission_cleared_by = fields.Many2one('res.users', string='Admission Cleared By', readonly=True)

    # Financials
    is_refund_eligible = fields.Boolean(string='Eligible for Tuition Refund', compute='_compute_finance_eligibility', store=True)
    tuition_refund_amount = fields.Monetary(string='Tuition Refund Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', related='student_id.program_id.currency_id')

    # Approval Info
    registrar_approver_id = fields.Many2one('res.users', string='Registrar Approver', readonly=True)
    academic_approver_id = fields.Many2one('res.users', string='Academic Affairs Approver', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('university.student.resignation') or 'New'
            
            # Auto-populate level and year from student
            if vals.get('student_id'):
                student = self.env['university.student'].browse(vals['student_id'])
                print(student)
                print("1111321234567890`12345678912345678923456")
                vals['level'] = student.current_level
                if not vals.get('academic_year_name'):
                    vals['academic_year_name'] = student.current_academic_year_name
                
                # Eligibility Rule: Level 1 must be registered
                if student.current_level == '1' and student.registration_status != 'registered':
                    raise ValidationError(_("Level 1 students can only resign after completing initial registration procedures."))

        return super().create(vals_list)

    @api.depends('resignation_date', 'student_id.batch_id.academic_year_ids.state', 'student_id.batch_id.academic_year_ids.registration_deadline')
    def _compute_finance_eligibility(self):
        for rec in self:
            if rec.student_id and rec.student_id.batch_id and rec.resignation_date:
                active_years = rec.student_id.batch_id.academic_year_ids.filtered(lambda y: y.state == 'active')
                deadline = active_years[0].registration_deadline if active_years else False
                rec.is_refund_eligible = rec.resignation_date <= deadline if deadline else False
            else:
                rec.is_refund_eligible = False

    def action_send_otp(self):
        """Generates a 6-digit OTP and sends it to the student's email."""
        self.ensure_one()
        if not self.student_id.email:
            raise UserError(_("Student does not have a registered email address."))
        
        self.otp_code = ''.join(random.choices(string.digits, k=6))
        self.state = 'otp_sent'
        
        # Send Email
        template = self.env.ref('university_registrar.email_template_resignation_otp', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
        
        self.message_post(body=_("Resignation OTP sent to student email."))

    def action_verify_otp(self, code):
        """Verifies the OTP code provided by the student."""
        self.ensure_one()
        if code == self.otp_code:
            self.otp_verified = True
            self.state = 'clearance'
            self.message_post(body=_("OTP Verified. Clearance process initiated."))
        else:
            raise UserError(_("Invalid OTP code. Please try again."))

    # ─── Clearance Actions ───────────────────────────────────────────────────
    def action_clear_library(self):
        self.write({'library_clearance': 'cleared', 'library_cleared_by': self.env.user.id})
        self._check_all_cleared()

    def action_clear_lab(self):
        self.write({'lab_clearance': 'cleared', 'lab_cleared_by': self.env.user.id})
        self._check_all_cleared()

    def action_clear_finance(self):
        self.write({'finance_clearance': 'cleared', 'finance_cleared_by': self.env.user.id})
        self._check_all_cleared()

    def action_clear_admission(self):
        self.write({'admission_clearance': 'cleared', 'admission_cleared_by': self.env.user.id})
        self._check_all_cleared()

    def _check_all_cleared(self):
        if all(x == 'cleared' for x in [self.library_clearance, self.lab_clearance, self.finance_clearance, self.admission_clearance]):
            self.state = 'registrar_approval'

    # ─── Final Approvals ──────────────────────────────────────────────────────
    def action_registrar_approve(self):
        self.write({'registrar_approver_id': self.env.user.id, 'state': 'academic_affairs'})

    def action_academic_approve(self):
        """Final approval step: archive student and deactivate user."""
        self.ensure_one()
        student = self.student_id
        
        # 1. Update Standing and Archive Student
        student.write({
            'academic_standing': 'withdrawn',
            'active': False,
        })
        
        # 2. Deactivate Portal User
        if student.partner_id and student.partner_id.user_ids:
            student.partner_id.user_ids.write({'active': False})

        self.write({
            'academic_approver_id': self.env.user.id,
            'state': 'approved'
        })
        self.message_post(body=_("Resignation approved. Student and user deactivated."))

    def action_reject(self):
        if not self.rejection_reason:
            raise UserError(_("Please provide a rejection reason."))
        self.state = 'rejected'
