# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityStudentFreezeRequest(models.Model):
    _name = 'university.student.freeze.request'
    _description = 'Student Freeze Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')

    otp_code = fields.Char(string='OTP Code', copy=False, readonly=True)
    otp_verified = fields.Boolean(string='OTP Verified', default=False, copy=False, tracking=True)

    student_id = fields.Many2one(
        'university.student', 
        string='Student', 
        required=True, 
        tracking=True,
    )
    program_id = fields.Many2one(
        'university.program',
        string='Program',
        related='student_id.program_id',
        store=True,
    )
    academic_year_name = fields.Char(
        string='Academic Year',
        required=True,
        tracking=True,
    )
    level_to_freeze = fields.Selection(
        [
            ('1', 'Level 1'),
            ('2', 'Level 2'),
            ('3', 'Level 3'),
            ('4', 'Level 4'),
            ('5', 'Level 5'),
            ('6', 'Level 6'),
        ],
        string='Level to Freeze',
        required=True,
        tracking=True,
    )
    
    reason = fields.Selection(
        [
            ('late_arrival', 'Late Arrival'),
            ('travel', 'Travel'),
            ('accident', 'Accident'),
            ('other', 'Other'),
        ],
        string='Reason',
        required=True,
        tracking=True,
    )
    reason_details = fields.Text(string='Reason Details')
    
    invoice_id = fields.Many2one('account.move', string='Freeze Fee Invoice', readonly=True)
    activation_date = fields.Date(string='Activation Date', readonly=True, copy=False)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('otp_sent', 'OTP Sent'),
            ('submitted', 'Submitted'),
            ('registrar_approved', 'Registrar Approved'),
            ('approved', 'Academic Affairs Approved'),
            ('dean_approved', 'Dean Approved'),
            ('invoiced', 'Invoiced'),
            ('active', 'Active (Frozen)'),
            ('rejected', 'Rejected'),
            ('completed', 'Completed (Unfrozen)'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            student_id = vals.get('student_id')
            if student_id:
                student = self.env['university.student'].browse(student_id)
                
                # 1. Must be registered
                if student.registration_status != 'registered':
                    raise ValidationError(_("Student must be in 'Registered' status to apply for freezing. Current: %s") % student.registration_status)
                
                # 2. Registration fee must be fully paid
                if not student.registration_invoice_id or student.registration_invoice_id.payment_state not in ['paid', 'in_payment']:
                    raise ValidationError(_("The registration fee for the current academic year must be fully paid before applying for a freeze."))
                
                # 3. Half tuition check (Amount paid >= 50% of total)
                if student.tuition_invoice_id:
                    tuition_inv = student.tuition_invoice_id
                    if tuition_inv.amount_total > 0:
                        paid_amt = tuition_inv.amount_total - tuition_inv.amount_residual
                        # Use a small epsilon for float comparison safety if needed, but standard >= is usually fine here
                        if paid_amt < (tuition_inv.amount_total / 2.0):
                            raise ValidationError(_("At least 50%% of the tuition fees must be paid to apply for a freeze. Paid: %s, Total: %s") % (paid_amt, tuition_inv.amount_total))
                else:
                    # If tuition invoice is missing, we might assume they haven't started payment process for tuition yet.
                    # Usually, students should have a tuition invoice to be registered in some systems, 
                    # but if it is allowed to be missing, we should decide policy. 
                    # The plan says "The tuition invoice ... must have at least 50% paid", implying one exists.
                    raise ValidationError(_("Tuition invoice not found. Student must have an issued and partially paid tuition invoice to freeze."))

            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('university.freeze.request') or 'New'
        return super().create(vals_list)

    @api.constrains('student_id', 'level_to_freeze')
    def _check_freeze_limits(self):
        for rec in self:
            if rec.state in ['rejected']:
                continue
            # 1. A student may perform freezing up to two times during the total program.
            all_freezes = self.search([
                ('student_id', '=', rec.student_id.id),
                ('state', 'not in', ['draft', 'rejected']),
                ('id', '!=', rec.id)
            ])
            if len(all_freezes) >= 2:
                raise ValidationError(_("A student may perform freezing up to a maximum of two times during the total program."))
            
            current_lvl = int(rec.level_to_freeze)
            for freeze in all_freezes:
                prev_lvl = int(freeze.level_to_freeze)
                # 2. Freezing is allowed only once for a specific level.
                if prev_lvl == current_lvl:
                    raise ValidationError(_("Freezing is allowed only once for a specific level. You cannot freeze Level %s again.") % rec.level_to_freeze)
                
                # 3. Cannot freeze for two consecutive levels.
                if abs(prev_lvl - current_lvl) == 1:
                    raise ValidationError(_("A student cannot freeze for two consecutive levels (e.g. Level %s and Level %s).") % (prev_lvl, current_lvl))

    def action_send_otp(self):
        for rec in self:
            if not rec.student_id.email:
                raise ValidationError(_("Student must have an email address to receive OTP."))
            import random
            rec.otp_code = str(random.randint(100000, 999999))
            rec.write({'state': 'otp_sent'})
            
            # Simple mail sending
            mail_values = {
                'subject': 'OTP for Freeze Request %s' % rec.name,
                'body_html': '<p>Your OTP code for freezing your academic status is: <strong>%s</strong></p>' % rec.otp_code,
                'email_to': rec.student_id.email,
            }
            mail = self.env['mail.mail'].sudo().create(mail_values)
            mail.send()
            rec.message_post(body=_("OTP sent to student email for Freeze confirmation."))

    def action_verify_otp(self, entered_code):
        self.ensure_one()
        if self.state != 'otp_sent':
            raise ValidationError(_("OTP not sent or already verified."))
        if self.otp_code != entered_code:
            raise ValidationError(_("Invalid OTP Code."))
        
        self.otp_verified = True
        self.message_post(body=_("Student successfully verified OTP."))
        self.action_submit()

    def action_submit(self):
        for rec in self:
            if not rec.otp_verified:
                raise ValidationError(_("OTP must be verified before submitting."))
            rec.write({'state': 'submitted'})

    def action_dean_approve(self):
        for rec in self:
            if rec.level_to_freeze != '1':
                raise ValidationError(_("Dean Approval is only required for Level 1."))
            if rec.state != 'approved':
                raise ValidationError(_("Level 1 freezing requests must be approved by Academic Affairs first."))
            rec.write({'state': 'dean_approved'})

    def action_registrar_approve(self):
        for rec in self:
            rec.write({'state': 'registrar_approved'})

    def action_head_approve(self):
        # Generate Invoice if required, else move to active
        # Assuming fixed freeze fee of 0.0 means no invoice
        for rec in self:
            rec.write({'state': 'approved'})

    def action_activate_freeze(self):
        for rec in self:
            if rec.level_to_freeze == '1' and rec.state != 'dean_approved':
                raise ValidationError(_("Level 1 requests must be approved by the Dean before activation."))
            if rec.level_to_freeze != '1' and rec.state != 'approved':
                raise ValidationError(_("Requests must be approved by Academic Affairs before activation."))
                
            rec.write({
                'state': 'active',
                'activation_date': fields.Date.today(),
            })
            rec.student_id.write({
                'academic_standing': 'frozen',
                'registration_status': 'unregistered',
                'batch_id': False,  # Remove from current batch
            })
            rec.student_id.message_post(body=_("Academic year frozen due to approved Freeze Request %s. Student unregistered.") % rec.name)

    def action_unfreeze(self):
        for rec in self:
            rec.write({'state': 'completed'})
            rec.student_id.write({'academic_standing': 'good_standing'})
            rec.student_id.message_post(body=_("Student has unfrozen from Request %s and is continuing the level.") % rec.name)

    def action_reject(self):
        self.write({'state': 'rejected'})
