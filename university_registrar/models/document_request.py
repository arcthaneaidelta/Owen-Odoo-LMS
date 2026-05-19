# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class UniversityDocumentRequest(models.Model):
    _name = 'university.document.request'
    _description = 'Document Extraction Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')

    student_id = fields.Many2one(
        'university.student', 
        string='Student', 
        required=True, 
        tracking=True,
    )
    document_type = fields.Selection(
        [
            ('transcript', 'Degree Transcript'),
            ('graduation_cert', 'Graduation Certificate'),
            ('enrollment_proof', 'Proof of Enrollment'),
            ('other', 'Other Certificate'),
        ],
        string='Document Type',
        required=True,
        tracking=True,
    )
    
    notes = fields.Text(string='Notes / Requirements')

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('in_progress', 'Processing'),
            ('ready', 'Ready for Pickup'),
            ('delivered', 'Delivered'),
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
                vals['name'] = self.env['ir.sequence'].next_by_code('university.document.request') or 'New'
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_process(self):
        self.write({'state': 'in_progress'})

    def action_ready(self):
        self.write({'state': 'ready'})
        # PDF generation logic stub for future
        # if self.document_type == 'transcript':
        #     pdf_content, report_name = self.env['ir.actions.report']._render_qweb_pdf('university_registrar.report_transcript', self.id)
        #     self.message_post(body=_("Document is ready."), attachments=[(f'{self.student_id.student_id}_Transcript.pdf', pdf_content)])

    def action_deliver(self):
        self.write({'state': 'delivered'})

    def action_reject(self):
        self.write({'state': 'rejected'})
