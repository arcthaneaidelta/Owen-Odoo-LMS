from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta

class UniversityStudentUnfreezeRequest(models.Model):
    _name = 'university.student.unfreeze.request'
    _description = 'Student Unfreeze Request'
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
        string='Academic Year related to new enrollment',
        required=True,
        tracking=True,
    )
    
    freeze_request_id = fields.Many2one(
        'university.student.freeze.request',
        string='Original Freeze Request',
        required=True,
        domain="[('student_id', '=', student_id), ('state', '=', 'active')]",
        tracking=True,
    )

    reason_details = fields.Text(string='Notes')

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('otp_sent', 'OTP Sent'),
            ('submitted', 'Submitted'),
            ('registrar_approved', 'Registrar Approved'),
            ('approved', 'Academic Affairs Approved'),
            ('completed', 'Completed (Unfrozen)'),
            ('rejected', 'Rejected'),
        ],
        tracking=True,
    )

    @api.constrains('freeze_request_id')
    def _check_freeze_duration(self):
        for rec in self:
            if rec.freeze_request_id and rec.freeze_request_id.activation_date:
                one_year_later = rec.freeze_request_id.activation_date + relativedelta(years=1)
                if fields.Date.today() < one_year_later:
                    raise ValidationError(_(
                        "A freeze request must remain active for at least one year. "
                        "This request was activated on %s. You can only unfreeze after %s."
                    ) % (rec.freeze_request_id.activation_date, one_year_later))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('university.unfreeze.request') or 'New'
        return super().create(vals_list)

    def action_send_otp(self):
        for rec in self:
            if not rec.student_id.email:
                raise ValidationError(_("Student must have an email address to receive OTP."))
            import random
            rec.otp_code = str(random.randint(100000, 999999))
            rec.write({'state': 'otp_sent'})
            
            mail_values = {
                'subject': 'OTP for Unfreeze Request %s' % rec.name,
                'body_html': '<p>Your OTP code for unfreezing your academic status is: <strong>%s</strong></p>' % rec.otp_code,
                'email_to': rec.student_id.email,
            }
            mail = self.env['mail.mail'].sudo().create(mail_values)
            mail.send()
            rec.message_post(body=_("OTP sent to student email for Unfreeze confirmation."))

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

    def action_registrar_approve(self):
        for rec in self:
            rec.write({'state': 'registrar_approved'})

    def action_head_approve(self):
        for rec in self:
            rec.write({'state': 'approved'})

    def action_complete_unfreeze(self):
        for rec in self:
            rec.write({'state': 'completed'})
            rec.freeze_request_id.write({'state': 'completed'})
            
            # Find the appropriate batch for their level in the current academic year
            # Logic: If returning to Level 1 in 2021, target batch year is 2021.
            # If returning to Level 2 in 2021, target batch year is 2020.
            new_batch = self.env['university.batch'].search([
                ('program_id', '=', rec.student_id.program_id.id),
                ('current_level', '=', rec.freeze_request_id.level_to_freeze),
                ('state', '=', 'active')
            ], limit=1)

            rec.student_id.write({
                'academic_standing': 'good_standing',
                'registration_status': 'unregistered',
                'batch_id': new_batch.id if new_batch else rec.student_id.batch_id,
                'academic_year_name': new_batch.current_academic_year_name if new_batch else False
            })
            
            rec.student_id.message_post(body=_("Student has properly unfrozen via Request %s. They must now register and pay fees to join Batch %s.") % (rec.name, new_batch.name if new_batch else 'None'))

    def action_reject(self):
        self.write({'state': 'rejected'})
