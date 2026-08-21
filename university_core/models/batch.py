# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityBatch(models.Model):
    _name = 'university.batch'
    _description = 'Student Batch'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'program_id, batch_year desc'

    name = fields.Char(
        string='Batch Name',
        compute='_compute_name',
        store=True,
    )
    batch_year = fields.Char(
        string='Batch Year',
        required=True,
        tracking=True,
    )
    batch_number = fields.Char(
        string='Batch Number',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
    )
    code = fields.Char(
        string='Batch Code',
        compute='_compute_code',
        store=True,
    )

    program_id = fields.Many2one(
        'university.program',
        string='Program',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    college_id = fields.Many2one(
        'university.college',
        string='College',
        related='program_id.college_id',
        store=True,
        readonly=True,
    )
    university_id = fields.Many2one(
        'university.university',
        string='University',
        related='program_id.university_id',
        store=True,
        readonly=True,
    )
    current_academic_year_name = fields.Char(
        string='Academic Year',
        compute='_compute_current_academic_year_name',
        store=True,
    )

    @api.depends('academic_year_ids', 'academic_year_ids.state', 'academic_year_ids.name')
    def _compute_current_academic_year_name(self):
        for rec in self:
            active_year = rec.academic_year_ids.filtered(lambda y: y.state == 'active')
            if active_year:
                rec.current_academic_year_name = active_year[0].name
            else:
                rec.current_academic_year_name = False
    academic_year_ids = fields.One2many(
        'university.academic_year',
        'batch_id',
        string='Academic Years',
    )



    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('archived', 'Archived'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )



    capacity = fields.Integer(string='Maximum Capacity', default=0)
    notes = fields.Text(string='Notes', translate=True)

    _sql_constraints = [
        (
            'program_year_uniq',
            'unique(program_id, batch_year)',
            'A batch for this program and year already exists.',
        ),
        (
            'year_positive',
            'CHECK(batch_year > 2000)',
            'Batch year must be a valid year after 2000.',
        ),
    ]

    # ─── Computes ─────────────────────────────────────────────────────────────
    @api.depends('program_id', 'batch_year')
    def _compute_name(self):
        for rec in self:
            prog = rec.program_id.name_ar or rec.program_id.name or ''
            rec.name = f'{prog} - {rec.batch_year}' if prog and rec.batch_year else ''

    @api.depends('program_id', 'batch_year')
    def _compute_code(self):
        for rec in self:
            prog_code = rec.program_id.code or ''
            rec.code = f'{prog_code}-{rec.batch_year}' if prog_code else str(rec.batch_year)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('batch_number', _('New')) == _('New'):
                program_id = vals.get('program_id')
                if program_id:
                    # Count how many batches this program already has
                    batch_count = self.search_count([('program_id', '=', program_id)])
                    next_number = batch_count + 1
                    vals['batch_number'] = f'B{next_number:04d}'
                else:
                    # Fallback to global if no program (shouldn't happen due to required=True)
                    vals['batch_number'] = self.env['ir.sequence'].next_by_code('university.batch') or _('New')
        return super().create(vals_list)



    # ─── State Transitions ────────────────────────────────────────────────────
    def action_activate(self):
        for rec in self:
            rec.write({'state': 'active'})
            rec.message_post(
                body=_('Batch activated.')
            )

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_archive_batch(self):
        self.write({'state': 'archived', 'active': False})

    def action_open_roadmap(self):
        self.ensure_one()
        return {
            'name': _('Academic Years - %s') % (self.name or self.batch_number),
            'type': 'ir.actions.act_window',
            'res_model': 'university.academic_year',
            'view_mode': 'kanban,list,form',
            'domain': [('batch_id', '=', self.id)],
            'context': {
                'default_batch_id': self.id,
                'search_default_batch_id': self.id,
            },
            'target': 'current',
        }

    # ─── Curriculum Lock Enforcement ──────────────────────────────────────────

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, rec.name or rec.batch_number))
        return result

    # ─── Roadmap Automation ───────────────────────────────────────────────────
    @api.model
    def _cron_process_roadmaps(self):
        today = fields.Date.today()
        # Find all unprocessed roadmap events for today or past days
        events = self.env['university.batch.roadmap'].search([
            ('date_start', '<=', today),
            ('is_processed', '=', False),
            ('event_type', 'in', ['level_promotion', 'registration']),
            ('batch_id.state', '=', 'active')
        ])

        for event in events:
            batch = event.batch_id
            action_taken = ""

            if event.event_type == 'level_promotion':
                if hasattr(batch, 'action_promote'):
                    batch.action_promote()
                    action_taken = f"Batch automatically promoted to Level {batch.current_level}."

            elif event.event_type == 'registration':
                # Propagate the deadline to the Academic Year so the penalty cron job can enforce it.
                if event.academic_year_id:
                    event.academic_year_id.write({
                        'registration_deadline': event.registration_end or event.date_stop,
                    })

                # Skip re-registration for Level 1 if it's their first year, as Admission handled their invoices.
                if batch.current_level == 1 and len(batch.academic_year_ids) <= 1:
                    action_taken = "Registration window opened. Skipped automated invoicing as this is the batch's first year."
                else:
                    students = self.env['university.student'].search([
                        ('batch_id', '=', batch.id),
                        ('registration_status', 'in', ['registered', 'frozen', 'unregistered'])
                    ])
                    # Update their status to unregistered
                    students.write({'registration_status': 'unregistered'})
                    
                    if hasattr(self.env['university.student'], 'action_trigger_re_registration'):
                        students.action_trigger_re_registration()
                        action_taken = f"Triggered Re-Registration flow for {len(students)} students."
                    else:
                        action_taken = f"Registration window opened for {len(students)} students."

            if action_taken:
                event.write({'is_processed': True})
                batch.message_post(body=f"Roadmap Automation Triggered: {action_taken}")
                
                # Send email notification to administrators
                group_admin = self.env.ref('university_core.group_university_manager', raise_if_not_found=False)
                if group_admin:
                    users = self.env['res.users'].search([('groups_id', '=', group_admin.id)])
                    emails = [u.email for u in users if u.email]
                    if emails:
                        mail_values = {
                            'subject': f"Roadmap Automation: {batch.name}",
                            'body_html': f"<p>The roadmap event <strong>{event.name}</strong> for batch <strong>{batch.name}</strong> was triggered today.</p><p>Result: {action_taken}</p>",
                            'email_to': ",".join(emails),
                        }
                        mail = self.env['mail.mail'].sudo().create(mail_values)
                        mail.send()

