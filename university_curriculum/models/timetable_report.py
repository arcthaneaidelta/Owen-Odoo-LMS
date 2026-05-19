# -*- coding: utf-8 -*-
from odoo import models, fields, api


class UniversityTimetableReport(models.AbstractModel):
    """QWeb report helper model that builds the weekly grid data."""
    _name = 'report.university_curriculum.report_timetable_grid_document'
    _description = 'Timetable Grid Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        batch_id = data.get('batch_id')
        academic_year_id = data.get('academic_year_id')

        domain = [('state', '=', 'published')]
        if batch_id:
            domain.append(('batch_id', '=', batch_id))
        if academic_year_id:
            domain.append(('academic_year_id', '=', academic_year_id))

        sessions = self.env['university.timetable'].search(domain, order='day_of_week, start_time')

        days_order = ['0', '1', '2', '3', '4', '5', '6']
        day_labels = {
            '0': 'Monday', '1': 'Tuesday', '2': 'Wednesday',
            '3': 'Thursday', '4': 'Friday', '5': 'Saturday', '6': 'Sunday',
        }
        session_type_labels = dict(self.env['university.timetable']._fields['session_type'].selection)

        # Build grid: {day: [session, ...]}
        grid = {day: [] for day in days_order}
        for s in sessions:
            grid[s.day_of_week].append(s)

        # Remove empty days
        active_days = [d for d in days_order if grid[d]]

        # Pre-compute display strings to avoid using data dict in the template
        batch_name = self.env['university.batch'].browse(batch_id).name if batch_id else ''
        year_name = self.env['university.academic_year'].browse(academic_year_id).name if academic_year_id else ''

        return {
            'grid': grid,
            'active_days': active_days,
            'day_labels': day_labels,
            'session_type_labels': session_type_labels,
            'sessions': sessions,
            'batch_name': batch_name,
            'year_name': year_name,
        }


class TimetableGridWizard(models.TransientModel):
    """Wizard to display and print the weekly timetable grid."""
    _name = 'university.timetable.grid.wizard'
    _description = 'Timetable Grid Wizard'

    batch_id = fields.Many2one(
        'university.batch', string='Batch',
        domain="[('state', '=', 'active')]"
    )
    academic_year_id = fields.Many2one(
        'university.academic_year', string='Academic Year',
        domain="[('state', '=', 'active')]"
    )
    state = fields.Selection([
        ('filter', 'Filter'),
        ('grid', 'Grid View'),
    ], default='filter')

    grid_html = fields.Html(string='Weekly Grid', readonly=True, sanitize=False)

    # ─── Colors for session types ────────────────────────────────────────────
    _SESSION_COLORS = {
        'theory':    ('#1a73e8', '#e8f0fe'),   # Blue
        'practical': ('#e67c00', '#fff3e0'),   # Orange
        'lab':       ('#1e8e3e', '#e6f4ea'),   # Green
        'tutorial':  ('#7b1fa2', '#f3e5f5'),   # Purple
    }

    def _fmt_time(self, t):
        h = int(t)
        m = int(round((t % 1) * 60))
        return f'{h:02d}:{m:02d}'

    def _build_grid_html(self):
        """Build a full styled HTML weekly grid table."""
        domain = []
        if self.batch_id:
            domain.append(('batch_id', '=', self.batch_id.id))
        if self.academic_year_id:
            domain.append(('academic_year_id', '=', self.academic_year_id.id))

        sessions = self.env['university.timetable'].search(domain, order='day_of_week, start_time')

        days_order = ['0', '1', '2', '3', '4', '5', '6']
        day_labels = {
            '0': 'Monday', '1': 'Tuesday', '2': 'Wednesday',
            '3': 'Thursday', '4': 'Friday', '5': 'Saturday', '6': 'Sunday',
        }
        type_labels = dict(self.env['university.timetable']._fields['session_type'].selection)

        grid = {d: [] for d in days_order}
        for s in sessions:
            grid[s.day_of_week].append(s)

        active_days = [d for d in days_order if grid[d]]

        if not active_days:
            return '<div style="text-align:center;padding:40px;color:#999;font-family:sans-serif;">No published sessions found for the selected filters.</div>'

        # ── Build header info ──────────────────────────────────────────────
        title_parts = []
        if self.batch_id:
            title_parts.append(f'<strong>Batch:</strong> {self.batch_id.name}')
        if self.academic_year_id:
            title_parts.append(f'<strong>Year:</strong> {self.academic_year_id.name}')

        html = f'''
<div style="font-family:'Segoe UI',Arial,sans-serif; max-width:100%; overflow-x:auto;">
  <div style="background:linear-gradient(135deg,#1a237e,#1565c0);color:white;padding:16px 20px;border-radius:10px 10px 0 0;display:flex;align-items:center;justify-content:space-between;">
    <div>
      <h3 style="margin:0;font-size:1.1rem;letter-spacing:.5px;">📅 Weekly Timetable Grid</h3>
      <p style="margin:4px 0 0;font-size:.85rem;opacity:.85;">{" &nbsp;|&nbsp; ".join(title_parts) or "All Batches / All Years"}</p>
    </div>
  </div>
  <table style="width:100%;border-collapse:collapse;border:1px solid #e0e0e0;">
    <thead>
      <tr>
        <th style="background:#1565c0;color:white;padding:10px 14px;text-align:left;width:90px;font-size:.8rem;border:1px solid #1976d2;">TIME</th>
'''
        for d in active_days:
            html += f'        <th style="background:#1565c0;color:white;padding:10px 14px;text-align:center;font-size:.85rem;border:1px solid #1976d2;">{day_labels[d]}</th>\n'
        html += '      </tr>\n    </thead>\n    <tbody>\n'

        # Collect all unique time slots
        all_slots = sorted(set((s.start_time, s.end_time) for s in sessions))

        row_bg = ['#ffffff', '#f8f9fa']
        for i, (start, end) in enumerate(all_slots):
            html += f'      <tr style="background:{row_bg[i % 2]}">\n'
            html += f'        <td style="padding:8px 10px;font-weight:700;color:#555;font-size:.78rem;border:1px solid #e0e0e0;white-space:nowrap;vertical-align:top;">{self._fmt_time(start)}<br/><span style="color:#999;">–</span><br/>{self._fmt_time(end)}</td>\n'

            for d in active_days:
                # Find sessions in this time slot for this day
                slot_sessions = [s for s in grid[d] if s.start_time == start and s.end_time == end]
                if slot_sessions:
                    cards = ''
                    for s in slot_sessions:
                        fg, bg = self._SESSION_COLORS.get(s.session_type, ('#555', '#f5f5f5'))
                        cards += f'''
                  <div style="background:{bg};border-left:4px solid {fg};border-radius:6px;padding:8px 10px;margin-bottom:4px;">
                    <div style="font-weight:700;color:#212121;font-size:.82rem;">{s.subject_id.name or ''}</div>
                    <div style="font-size:.75rem;color:#555;margin-top:3px;">👤 {s.teacher_id.name or ''}</div>
                    <div style="font-size:.75rem;color:#555;">📍 {s.room_id.name or ''}</div>
                    <span style="display:inline-block;margin-top:4px;padding:1px 7px;border-radius:10px;background:{fg};color:white;font-size:.7rem;">{type_labels.get(s.session_type, s.session_type)}</span>
                  </div>'''
                    html += f'        <td style="padding:6px;border:1px solid #e0e0e0;vertical-align:top;">{cards}\n        </td>\n'
                else:
                    html += '        <td style="padding:6px;border:1px solid #e0e0e0;background:#fafafa;text-align:center;color:#ccc;font-size:.75rem;vertical-align:middle;">—</td>\n'

            html += '      </tr>\n'

        # Legend
        legend = ''
        for stype, (fg, bg) in self._SESSION_COLORS.items():
            label = type_labels.get(stype, stype)
            legend += f'<span style="display:inline-flex;align-items:center;margin-right:12px;"><span style="width:12px;height:12px;background:{fg};border-radius:3px;margin-right:5px;display:inline-block;"></span><span style="font-size:.78rem;color:#555;">{label}</span></span>'

        html += f'''    </tbody>
  </table>
  <div style="padding:10px 14px;background:#f5f5f5;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 10px 10px;">
    {legend}
  </div>
</div>'''
        return html

    def action_view_grid(self):
        """Build the HTML grid and re-open the wizard in grid state."""
        self.write({
            'grid_html': self._build_grid_html(),
            'state': 'grid',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_print_grid(self):
        data = {
            'batch_id': self.batch_id.id,
            'academic_year_id': self.academic_year_id.id,
        }
        return self.env.ref('university_curriculum.action_report_timetable_grid').report_action(self, data=data)

    def action_back(self):
        """Go back to the filter state."""
        self.state = 'filter'
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
