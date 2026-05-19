from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ExaminationPaperUpload(models.Model):
    _name = 'examination.paper.upload'
    _description = 'Examination Paper Upload'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'subject_id'

    subject_id = fields.Many2one('university.subject', string='Subject', required=True)
    teacher_id = fields.Many2one('hr.employee', string='Teacher', required=True)
    exam_type = fields.Selection([
        ('main', 'Main'),
        ('second', 'Substitute'),
        ('supplementary', 'Supplementary'),
    ], string='Exam Type', required=True)
    
    question_paper_pdf = fields.Binary('Question Paper (PDF)', required=True)
    question_paper_word = fields.Binary('Question Paper (Word)', required=True)
    answer_sheet_pdf = fields.Binary('Answer Sheet (PDF)', required=True)
    answer_sheet_word = fields.Binary('Answer Sheet (Word)', required=True)
    
    is_verified = fields.Boolean('Is Verified', default=False, tracking=True)
    generated_otp_code = fields.Char('Generated OTP')
    otp_code = fields.Char('OTP Code', help='Enter the OTP sent to your email')
    
    def action_send_otp(self):
        import random
        for rec in self:
            rec.generated_otp_code = str(random.randint(100000, 999999))
            template = self.env.ref('university_examination.email_template_exam_otp_v2', raise_if_not_found=False)
            if template:
                template.send_mail(rec.id, force_send=True)
        return True
        
    def action_verify_otp(self):
        for rec in self:
            if not rec.generated_otp_code:
                raise ValidationError('Please send the OTP first.')
            if rec.otp_code == rec.generated_otp_code:
                rec.is_verified = True
            else:
                raise ValidationError('Invalid OTP. Please try again.')
