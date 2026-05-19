# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityStudentPhone(models.Model):
    _name = 'university.student.phone'
    _description = 'Student Phone History'
    _order = 'student_id, is_active desc, date_added desc'

    student_id = fields.Many2one(
        'university.student',
        string='Student',
        required=True,
        ondelete='cascade',
        index=True,
    )
    phone_number = fields.Char(
        string='Phone Number',
        required=True,
    )
    is_whatsapp = fields.Boolean(
        string='WhatsApp Number',
        default=False,
    )
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Active numbers are used for current communication.',
    )
    date_added = fields.Date(
        string='Date Added',
        required=True,
        default=fields.Date.today,
    )
    date_deprecated = fields.Date(
        string='Date Deprecated',
        help='Date when this number was replaced or deprecated.',
    )
    reason = fields.Char(
        string='Reason / Note',
        help='Reason for adding or deprecating this number.',
    )

    # Phone numbers are never deleted - only deprecated
    def unlink(self):
        raise ValidationError(_(
            'Phone history records cannot be deleted. '
            'Mark them as deprecated instead to preserve the audit trail.'
        ))

    def action_deprecate(self):
        self.write({
            'is_active': False,
            'date_deprecated': fields.Date.today(),
        })
        self.message_post(body=_('Phone number marked as deprecated.'))

    def _message_post(self, body):
        # Chatter on parent student
        for rec in self:
            rec.student_id.message_post(body=body)
