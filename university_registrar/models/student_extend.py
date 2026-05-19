# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class UniversityStudent(models.Model):
    _inherit = 'university.student'

    freeze_request_ids = fields.One2many(
        'university.student.freeze.request',
        'student_id',
        string='Freeze Requests',
    )


    resignation_ids = fields.One2many(
        'university.student.resignation',
        'student_id',
        string='Resignation Requests',
    )

    total_freeze_years = fields.Integer(
        string='Total Freeze Years',
        compute='_compute_total_freeze_years',
        store=True,
        help='Total number of years the student has frozen.'
    )

    net_study_duration = fields.Integer(
        string='Net Study Duration (Years)',
        compute='_compute_net_study_duration',
        store=True,
        help='Chronological years since admission minus total frozen years.'
    )

    @api.depends('freeze_request_ids', 'freeze_request_ids.state')
    def _compute_total_freeze_years(self):
        for rec in self:
            rec.total_freeze_years = len(rec.freeze_request_ids.filtered(lambda f: f.state == 'completed' or f.state == 'active'))

    @api.depends('total_freeze_years', 'admission_date')
    def _compute_net_study_duration(self):
        today = fields.Date.today()
        for rec in self:
            if rec.admission_date:
                years_since_admission = relativedelta(today, rec.admission_date).years
                rec.net_study_duration = max(0, years_since_admission - rec.total_freeze_years)
            else:
                rec.net_study_duration = 0

    # ═══════════════════════════════════════════════════════════════════════════
    # OVERRIDE action_promote() — triggers re-registration after each promotion
    # ═══════════════════════════════════════════════════════════════════════════

    def action_promote(self):
        """
        Extend the base action_promote to:
        1. Call super() to do the actual level increment / graduation.
        2. For students whose level genuinely increased (not initial setup, not graduated):
           Trigger the re-registration flow.
        """
        for rec in self:
            # ── 0. Registration Lock ──────────────────────────────────────────
            # Prevent promotion if the student is not registered for their CURRENT level
            # (unless it's the very first time they are being initialized with a level)
            if rec.current_level and rec.registration_status != 'registered':
                raise ValidationError(_(
                    "Student %s cannot be promoted because they are not yet registered "
                    "for their current level (%s). Complete re-registration first."
                ) % (rec.display_name, rec.current_level))

            old_level = rec.current_level
            old_standing = rec.academic_standing

            super(UniversityStudent, rec).action_promote()

            was_actually_promoted = (
                old_level
                and rec.current_level != old_level
                and rec.academic_standing != 'graduated'
            )
            if was_actually_promoted:
                # Set Academic Year to the system's current active academic year
                active_year = self.env['university.academic_year'].search([('is_current', '=', True)], limit=1)
                if active_year:
                    rec.write({'academic_year_id': active_year.id})
                
                rec.action_trigger_re_registration(is_repetition=False)

    def action_trigger_re_registration(self, is_repetition=False, failed_subject_ids=None):
        """
        Generates registration and tuition invoices directly on the student record
        and sends a portal link for them to update their medical/personal info.
        """
        import secrets
        
        for rec in self:
            # a. Determine academic year and deadlines
            target_year = rec.academic_year_id or rec.batch_id.academic_year_id
            if not target_year:
                target_year = self.env['university.academic_year'].search(
                    [('is_current', '=', True)], limit=1
                )
            
            token_expiry = (
                target_year.late_registration_deadline
                or target_year.registration_deadline
                if target_year else False
            )

            # b. Determine currency
            if rec.financial_type == 'foreigner':
                currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
            else:
                currency = self.env['res.currency'].search([('name', '=', 'SDG')], limit=1)
            if not currency:
                currency = self.env.company.currency_id

            # c. Identify Required Subjects (Failed + Newly Introduced)
            # 1. Subjects the student previously passed
            passed_subject_ids = self.env['university.student.subject.score'].search([
                ('student_id', '=', rec.id),
                ('is_pass', '=', True)
            ]).mapped('subject_id')

            # 2. Subjects in the NEW batch's curriculum for this level
            new_batch_curriculum = rec.batch_id.curriculum_id
            required_subjects = self.env['university.subject']
            if new_batch_curriculum:
                # Filter lines in curriculum for the student's current level
                new_curriculum_lines = new_batch_curriculum.line_ids.filtered(
                    lambda l: l.year_level == int(rec.current_level or 0)
                )
                new_curriculum_subjects = new_curriculum_lines.mapped('subject_id')
                
                # Identify subjects in the new curriculum that the student has NOT passed
                required_subjects = new_curriculum_subjects.filtered(
                    lambda s: s.id not in passed_subject_ids.ids
                )

            # d. Determine Fees
            reg_fee = rec.program_id.registration_fee if rec.program_id else 0.0
            
            if is_repetition:
                # Repeating students pay per subject for failed and new subjects
                subject_count = len(required_subjects)
                if subject_count > 0:
                    tuition_fee = (rec.program_id.repetition_fee_per_subject or 0.0) * subject_count
                else:
                    tuition_fee = rec.program_id.repetition_fee_per_subject or 0.0
            else:
                tuition_fee = rec.program_id.tuition_fee if rec.program_id else 0.0

            # e. Create Invoices
            level_label = f'Level {rec.current_level}' if rec.current_level else ''
            reg_desc = f'Registration Fee – {level_label}'
            tui_desc = f'Tuition Fee – {level_label}'
            
            if is_repetition:
                reg_desc = f'Registration Fee (Repetition) – {level_label}'
                if required_subjects:
                    subjects_str = ", ".join(required_subjects.mapped('name_ar') or required_subjects.mapped('name'))
                    tui_desc = f'Tuition Fee (Repetition & New Subjects: {subjects_str}) – {level_label}'
                else:
                    tui_desc = f'Tuition Fee (Full Repetition) – {level_label}'

            reg_inv = rec._create_fee_invoice(reg_fee, reg_desc, 'Registration Fee', currency)
            tui_inv = rec._create_fee_invoice(tuition_fee, tui_desc, 'Tuition Fee', currency)
            
            if reg_inv:
                reg_inv.action_post()
            if tui_inv:
                tui_inv.action_post()

            # e. Update Student Record
            vals = {
                'registration_invoice_id': reg_inv.id if reg_inv else False,
                'tuition_invoice_id': tui_inv.id if tui_inv else False,
                're_registration_token': secrets.token_urlsafe(32),
                're_registration_token_expiry': token_expiry,
                're_registration_draft_data': False,  # Reset any old draft data
                'academic_year_id': target_year.id if target_year else False,
            }

            # If it's a repetition, they join the batch that is now at their level
            if is_repetition:
                new_batch = self.env['university.batch'].search([
                    ('program_id', '=', rec.program_id.id),
                    ('current_level', '=', rec.current_level),
                    ('state', '=', 'active')
                ], limit=1)
                
                if new_batch:
                    vals['batch_id'] = new_batch.id

            rec.write(vals)
            
            msg = _('Student promoted to Level %s. ' if not is_repetition else 'Student is Repeating Level %s. ') % rec.current_level
            msg += _('Registration and Tuition invoices generated.')
            rec.message_post(body=msg)

            # f. Send the re-registration email
            if rec.email:
                template = self.env.ref(
                    'university_registrar.email_template_re_registration',
                    raise_if_not_found=False,
                )
                if template:
                    template.sudo().send_mail(rec.id, force_send=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # FEE INVOICE HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _get_or_create_fee_product(self, product_name):
        Product = self.env['product.product']
        product = Product.search([('name', '=', product_name)], limit=1)
        if not product:
            income_account = self.env['account.account'].search([
                ('account_type', 'in', ['income', 'income_other']),
                ('deprecated', '=', False),
            ], limit=1)
            product_vals = {
                'name': product_name,
                'type': 'service',
                'invoice_policy': 'order',
                'sale_ok': True,
                'purchase_ok': False,
                'taxes_id': [],
                'supplier_taxes_id': [],
            }
            if income_account:
                product_vals['property_account_income_id'] = income_account.id
            product = Product.sudo().create(product_vals)
        return product

    def _create_fee_invoice(self, amount, fee_desc, product_name, currency):
        self.ensure_one()
        if not amount or amount <= 0:
            return self.env['account.move']

        invoice_currency = currency or self.env.company.currency_id

        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('currency_id', '=', invoice_currency.id),
        ], limit=1)
        if not journal:
            journal = self.env['account.journal'].search([
                ('type', '=', 'sale'),
                ('currency_id', '=', False),
            ], limit=1)
        if not journal:
            journal = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)

        product = self._get_or_create_fee_product(product_name)
        partner = self._get_or_create_partner()

        line_desc = _('{fee} – {name} ({prog})').format(
            fee=fee_desc,
            name=self.display_name_ar or self.name_en or '',
            prog=self.program_id.name or '',
        )

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_date_due': fields.Date.today(),
            'ref': f"{self.student_id or self.name_en} - {fee_desc}",
            'currency_id': invoice_currency.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'name': line_desc,
                'quantity': 1,
                'price_unit': amount,
                'currency_id': invoice_currency.id,
            })],
        }
        if journal:
            invoice_vals['journal_id'] = journal.id
        return self.env['account.move'].create(invoice_vals)

    def _get_or_create_partner(self):
        self.ensure_one()
        if self.partner_id:
            return self.partner_id
        partner = self.env['res.partner'].sudo().search(
            [('email', '=', self.email)], limit=1
        )
        if not partner:
            partner = self.env['res.partner'].sudo().create({
                'name': self.display_name_ar or self.name_en or '',
                'phone': self.phone,
                'email': self.email,
                'customer_rank': 1,
            })
            self.partner_id = partner.id
        return partner

    # ═══════════════════════════════════════════════════════════════════════════
    # CRON JOBS
    # ═══════════════════════════════════════════════════════════════════════════

    @api.model
    def _cron_check_max_duration_expulsion(self):
        """
        Checks if students have exceeded the maximum allowed study duration (excluding frozen years).
        If net_study_duration > max_duration_years, expel the student.
        """
        today = fields.Date.today()
        students = self.search([('academic_standing', 'not in', ['graduated', 'expelled', 'withdrawn'])])
        for student in students:
            max_duration = student.program_id.max_duration_years or 10

            # Trigger recalculation just in case
            student._compute_net_study_duration()

            if student.net_study_duration > max_duration:
                student.academic_standing = 'expelled'
                student.active = False
                student.message_post(body=_(
                    "System automatically expelled the student for exceeding "
                    "the maximum study duration of %s years."
                ) % max_duration)
                # Block RFIDs
                active_cards = self.env['university.rfid_card'].search([
                    ('student_id', '=', student.id),
                    ('status', '=', 'active')
                ])
                if active_cards:
                    active_cards.write({
                        'status': 'blocked',
                        'block_reason': 'System: Student expelled due to max duration.'
                    })

    @api.model
    def _cron_check_unregistered_expulsion(self):
        """
        Checks for students who have not registered (or frozen) by the registration deadline
        of the current academic year, and expels them automatically.
        Also handles previously frozen students who failed to return.
        """
        current_year = self.env['university.academic_year'].search([('is_current', '=', True)], limit=1)
        if not current_year:
            return

        today = fields.Date.today()

        # 1. Unregistered students who missed regular and late deadlines
        if current_year.late_registration_deadline and today > current_year.late_registration_deadline:
            deadline_to_check = current_year.late_registration_deadline
        elif current_year.registration_deadline and today > current_year.registration_deadline and not current_year.late_registration_deadline:
            deadline_to_check = current_year.registration_deadline
        else:
            deadline_to_check = False

        if deadline_to_check and today > deadline_to_check:
            students_to_check = self.search([
                ('academic_standing', 'in', ['good_standing', 'warning', 'probation']),
                ('registration_status', '=', 'unregistered'),
            ])

            for student in students_to_check:
                active_freeze = self.env['university.student.freeze.request'].search([
                    ('student_id', '=', student.id),
                    ('academic_year_id', '=', current_year.id),
                    ('state', 'in', ['active', 'approved'])
                ], limit=1)

                if not active_freeze:
                    student.action_expel()
                    student.message_post(body=_(
                        "Auto-expelled: Student failed to register or freeze by the "
                        "final registration deadline (%s)."
                    ) % deadline_to_check)

        # 2. Frozen students who failed to properly return
        if current_year.registration_deadline and today > current_year.registration_deadline:
            frozen_students = self.search([
                ('academic_standing', '=', 'frozen')
            ])

            for f_student in frozen_students:
                active_freeze = self.env['university.student.freeze.request'].search([
                    ('student_id', '=', f_student.id),
                    ('state', '=', 'active')
                ], limit=1)

                if active_freeze and active_freeze.academic_year_id.id != current_year.id:
                    pending_unfreeze = self.env['university.student.unfreeze.request'].search([
                        ('student_id', '=', f_student.id),
                        ('state', 'not in', ['completed', 'rejected', 'draft'])
                    ], limit=1)

                    if not pending_unfreeze:
                        f_student.action_expel()
                        f_student.message_post(body=_(
                            "Auto-expelled: Student failed to apply for unfreezing "
                            "and re-registration after their freeze period ended."
                        ))

