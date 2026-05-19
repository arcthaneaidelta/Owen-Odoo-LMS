# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import io


class UniversityMinistryBatch(models.Model):
    """
    Top-level container: one record per Ministry Excel batch
    e.g. "Batch 2016/2017".  Records live here until matched
    to an admission application via the Ministry Approved button.
    """
    _name = 'university.ministry.batch'
    _description = 'Ministry Import Batch'
    _order = 'entry_year desc, name'

    name = fields.Char(
        string='Batch Label',
        required=True,
        help='e.g. Batch 2021/2022',
    )
    entry_year = fields.Char(
        string='Entry Year',
        required=True,
        help='The single admission year extracted from the YEAR range (e.g. 2021)',
    )
    import_date = fields.Date(
        string='Import Date',
        default=fields.Date.today,
        readonly=True,
    )
    record_count = fields.Integer(
        string='Records',
        compute='_compute_record_count',
    )
    notes = fields.Text(string='Notes')

    # ── kanban color ──────────────────────────────────────────────────────────
    color = fields.Integer(string='Color')

    def _compute_record_count(self):
        for rec in self:
            rec.record_count = self.env['university.ministry.bank'].search_count(
                [('batch_id', '=', rec.id)]
            )

    def action_view_records(self):
        """Open the list of bank records for this batch."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ministry Records – %s') % self.name,
            'res_model': 'university.ministry.bank',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
            'context': {'default_batch_id': self.id},
        }

    def action_import_excel(self):
        """Wizard to import Excel into this batch."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Ministry Excel'),
            'res_model': 'university.ministry.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_batch_id': self.id},
        }


class UniversityMinistryBank(models.Model):
    """
    Raw Ministry Excel row — one record per student row imported.
    Unique key = ministry_form_number (FRMNO) + entry_year.
    """
    _name = 'university.ministry.bank'
    _description = 'Ministry Bank Record'
    _order = 'entry_year desc, ministry_form_number'
    _rec_name = 'display_name_ar'

    batch_id = fields.Many2one(
        'university.ministry.batch',
        string='Import Batch',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # ── Excel columns (exact mapping) ────────────────────────────────────────
    ministry_form_number = fields.Char(string='FRMNO', index=True)
    ministry_fac_code = fields.Char(string='FAC')
    ministry_university_id_code = fields.Integer(string='UNIV_ID')

    name_part1_ar = fields.Char(string='N1 (First Name)')
    name_part2_ar = fields.Char(string='N2 (Father)')
    name_part3_ar = fields.Char(string='N3 (Grandfather)')
    name_part4_ar = fields.Char(string='N4 (Family)')

    display_name_ar = fields.Char(
        string='Full Arabic Name',
        compute='_compute_display_name_ar',
        store=True,
    )

    school_name = fields.Char(string='SCNAME')
    gob_number = fields.Integer(string='GOBNO')
    faculty_name_ar = fields.Char(string='FACNAME')
    program_code = fields.Char(string='Program')
    admission_type_text = fields.Char(string='GOBOLS')
    internal_admission_type = fields.Char(string='Internal Admission Type')
    citizenship = fields.Char(string='Citizenship')
    starting_level = fields.Selection(
        [
            ('1', 'Level 1'),
            ('2', 'Level 2'),
            ('3', 'Level 3'),
            ('4', 'Level 4'),
            ('5', 'Level 5'),
            ('6', 'Level 6'),
        ],
        string='Starting Level',
    )
    fin_position = fields.Char(string='Fin-Position')
    academic_year_str = fields.Char(string='YEAR')
    entry_year = fields.Char(string='Entry Year')
    batch_number = fields.Char(string='Batch')
    national_id = fields.Char(string='NATIONAL_ID', index=True)
    gender_code = fields.Integer(string='SEX')
    university_name_ar = fields.Char(string='UNIVERSITY')

    # ── match status ─────────────────────────────────────────────────────────
    is_matched = fields.Boolean(
        string='Matched to Application',
        default=False,
        index=True,
    )
    matched_admission_id = fields.Many2one(
        'university.admission',
        string='Matched Admission',
        readonly=True,
    )

    # ── SQL unique constraint: FRMNO + entry_year ─────────────────────────────
    _sql_constraints = [
        (
            'frmno_year_uniq',
            'unique(ministry_form_number, entry_year)',
            'A record with this FRMNO and Entry Year already exists in the bank.',
        ),
    ]

    @api.depends('name_part1_ar', 'name_part2_ar', 'name_part3_ar', 'name_part4_ar')
    def _compute_display_name_ar(self):
        for rec in self:
            parts = [
                rec.name_part1_ar or '',
                rec.name_part2_ar or '',
                rec.name_part3_ar or '',
                rec.name_part4_ar or '',
            ]
            rec.display_name_ar = ' '.join(p for p in parts if p.strip())
