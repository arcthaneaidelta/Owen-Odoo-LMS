# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import ValidationError

class UniversityFreezeOtpWizard(models.TransientModel):
    _name = 'university.freeze.otp.wizard'
    _description = 'Verify OTP Wizard'

    freeze_request_id = fields.Many2one('university.student.freeze.request', string="Freeze Request")
    unfreeze_request_id = fields.Many2one('university.student.unfreeze.request', string="Unfreeze Request")
    
    otp_code = fields.Char(string='Enter OTP from Student', required=True)

    def action_verify(self):
        if self.freeze_request_id:
            if self.freeze_request_id.state != 'otp_sent':
                raise ValidationError(_("Freeze Request is not in 'OTP Sent' state."))
            if self.freeze_request_id.otp_code != self.otp_code:
                raise ValidationError(_("Invalid OTP Code."))
            self.freeze_request_id.otp_verified = True
            self.freeze_request_id.message_post(body=_("OTP successfully verified by Administrator."))
            self.freeze_request_id.action_submit()
            
        elif self.unfreeze_request_id:
            if self.unfreeze_request_id.state != 'otp_sent':
                raise ValidationError(_("Unfreeze Request is not in 'OTP Sent' state."))
            if self.unfreeze_request_id.otp_code != self.otp_code:
                raise ValidationError(_("Invalid OTP Code."))
            self.unfreeze_request_id.otp_verified = True
            self.unfreeze_request_id.message_post(body=_("OTP successfully verified by Administrator."))
            self.unfreeze_request_id.action_submit()
