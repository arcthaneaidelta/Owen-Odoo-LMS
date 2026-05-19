# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import io


class UniversityMinistryImportWizard(models.TransientModel):
    _name = 'university.ministry.import.wizard'
    _description = 'Import Ministry Excel Wizard'

    batch_id = fields.Many2one(
        'university.ministry.batch',
        string='Target Batch',
        required=True,
    )
    excel_file = fields.Binary(string='Ministry Excel File', required=True)
    file_name = fields.Char(string='File Name')
    result_message = fields.Text(string='Import Result', readonly=True)
    state = fields.Selection(
        [('draft', 'Upload'), ('done', 'Done')],
        default='draft',
    )

    def action_import(self):
        self.ensure_one()
        try:
            import openpyxl
        except ImportError:
            raise UserError(_('openpyxl is required. Install it via: pip install openpyxl'))

        file_data = base64.b64decode(self.excel_file)
        wb = openpyxl.load_workbook(io.BytesIO(file_data))
        ws = wb.active

        headers = [str(cell.value).strip() if cell.value else '' for cell in ws[1]]

        # Column index map (0-based)
        col = {h: i for i, h in enumerate(headers)}

        def get(row, name, default=None):
            idx = col.get(name)
            if idx is None:
                return default
            val = row[idx]
            return val if val is not None else default

        def to_str(val):
            if val is None:
                return ''
            if isinstance(val, float) and val.is_integer():
                return str(int(val))
            return str(val).strip()

        Bank = self.env['university.ministry.bank']
        created = skipped = updated = 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue

            frmno = to_str(get(row, 'FRMNO'))
            # Entry Year: use the 'Entry Year' column directly
            raw_year = get(row, 'Entry Year')
            try:
                entry_year = int(raw_year) if raw_year else 0
            except (ValueError, TypeError):
                entry_year = 0

            if not frmno or not entry_year:
                skipped += 1
                continue

            # De-duplication: find existing by FRMNO + entry_year
            existing = Bank.search([
                ('ministry_form_number', '=', frmno),
                ('entry_year', '=', entry_year),
            ], limit=1)

            # Normalize starting_level value
            raw_level = to_str(get(row, 'starting level') or get(row, 'starting level '))
            level_map = {
                'Level One': '1', 'Level 1': '1', '1': '1',
                'Level Two': '2', 'Level 2': '2', '2': '2',
                'Level Three': '3', 'Level 3': '3', '3': '3',
                'Level Four': '4', 'Level 14': '4', '4': '4',
                'Level Five': '5', 'Level 5': '5', '5': '5',
                'Level Six': '6', 'Level 6': '6', '6': '6',
            }
            starting_level = level_map.get(raw_level, '')

            # Normalize citizenship
            raw_citizenship = to_str(get(row, 'Citizenship')).lower().strip()
            # Most common values: citizen or foreigner (in Arabic or English)
            citizenship_map = {
                'citizen': 'citizen', 'مواطن': 'citizen', 'سوداني': 'citizen',
                'foreigner': 'foreigner', 'أجنبي': 'foreigner', 'اجنبي': 'foreigner', 'وافد': 'foreigner',
            }
            citizenship = citizenship_map.get(raw_citizenship, 'citizen')

            # Normalize internal admission type
            raw_admission = to_str(get(row, 'Internal addmission type') or get(row, 'Internal admission type')).lower().strip()
            admission_map = {
                'regular': 'regular', 'عام': 'regular', 'قبول عام': 'regular',
                'bridging': 'bridging', 'تجسير': 'bridging',
                'mature': 'mature', 'ناضجين': 'mature',
                'transfer': 'transfer', 'تحويل': 'transfer',
            }
            internal_admission_type = admission_map.get(raw_admission, 'regular')

            vals = {
                'batch_id': self.batch_id.id,
                'ministry_form_number': frmno,
                'ministry_fac_code': to_str(get(row, 'FAC')),
                'ministry_university_id_code': int(get(row, 'UNIV_ID') or 0),
                'name_part1_ar': to_str(get(row, 'N1')),
                'name_part2_ar': to_str(get(row, 'N2')),
                'name_part3_ar': to_str(get(row, 'N3')),
                'name_part4_ar': to_str(get(row, 'N4')),
                'school_name': to_str(get(row, 'SCNAME')),
                'gob_number': int(get(row, 'GOBNO') or 0),
                'faculty_name_ar': to_str(get(row, 'FACNAME')),
                'program_code': to_str(get(row, 'Program')),
                'admission_type_text': to_str(get(row, 'GOBOLS')),
                'internal_admission_type': internal_admission_type,
                'citizenship': citizenship,
                'starting_level': starting_level,
                'fin_position': to_str(get(row, 'Fin-Position')),
                'academic_year_str': to_str(get(row, 'YEAR')),
                'entry_year': entry_year,
                'batch_number': to_str(get(row, 'Batch')),
                'national_id': to_str(get(row, 'NATIONAL_ID')),
                'gender_code': int(get(row, 'SEX') or 0),
                'university_name_ar': to_str(get(row, 'UNIVERSITY')),
            }

            if existing:
                existing.write(vals)
                updated += 1
            else:
                Bank.create(vals)
                created += 1

        self.result_message = _(
            'Import complete.\n'
            'Created: %d\n'
            'Updated (duplicates): %d\n'
            'Skipped (missing FRMNO/Year): %d'
        ) % (created, updated, skipped)
        self.state = 'done'

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
