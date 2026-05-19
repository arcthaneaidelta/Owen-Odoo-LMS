from odoo import models, fields

class UniversityGuardianAdmission(models.Model):
    _inherit = 'university.guardian'

    admission_id = fields.Many2one(
        'university.admission',
        string='Admission',
        ondelete='cascade',
    )