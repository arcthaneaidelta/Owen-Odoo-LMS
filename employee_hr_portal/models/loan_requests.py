from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta

class LoanRequests(models.Model):
    _name = "loan.requests"
    _description = "Loan Requests"
    _rec_name = 'employee_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, copy=False, tracking=True)
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user, tracking=True, copy=False)
    name = fields.Char(string='Name', copy=False, tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', tracking=True, copy=False)
    reason = fields.Text(string='Reason')
    amount = fields.Float(string='Loan Amount', tracking=True, copy=False)
    requested_date = fields.Datetime(string='Requested Date', tracking=True, copy=False, default=fields.Datetime.now)
    month = fields.Date(string='For Month', tracking=True, copy=False)
    currency_id = fields.Many2one('res.currency', related="company_id.currency_id")
    state = fields.Selection([
        ('new', 'New'),
        ('approve', 'Approved'),
        ('inv_created', 'Invoiced'),
        ('refuse', 'Refused'),
        ('cancel', 'Cancelled')
    ], default='new', tracking=True)
    installment_count = fields.Integer(string='Number of Monthly Installments', tracking=True, copy=False)
    first_due_date = fields.Date(string='Due Date of Invoices', tracking=True, copy=False)
    invoice_ids = fields.One2many('account.move', 'loan_request_id', string='Invoices', copy=False)
    invoice_count = fields.Integer(compute='_compute_invoice_count', string='Number of Invoices')

    # New Fields for Disbursement Bill
    disbursement_invoice_id = fields.Many2one(
        'account.move',
        string='Disbursement Bill',
        copy=False
    )
    disbursement_payment_state = fields.Selection(
        related='disbursement_invoice_id.payment_state',
        string='Disbursement Payment Status',
        store=True
    )

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    def action_reset(self):
        for rec in self:
            rec.state = 'new'

    def action_approve(self):
        for rec in self:
            rec.state = 'approve'

    def action_refuse(self):
        for rec in self:
            rec.state = 'refuse'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
        }

    def create_invoices(self):
        for rec in self:
            if rec.state != 'approve':
                raise ValidationError(_("Loan must be approved to create invoices."))
            if not rec.employee_id:
                raise ValidationError(_("Employee is not set for this loan request."))
            if not rec.employee_id.address_home_id:
                raise ValidationError(
                    _("Employee '%(employee_name)s' does not have a linked Private Contact (Partner). "
                      "Please set the 'Private Address' on the employee record.", employee_name=rec.employee_id.name)
                )
            if not rec.amount or rec.amount <= 0:
                raise ValidationError(_("Sorry, amount for the loan request should be greater than zero."))
            if rec.installment_count <= 0:
                raise ValidationError(_("Installment count must be greater than zero for the loan request."))
            if not rec.month:
                raise ValidationError(_("Start date must be set. Please set the 'For Month' field."))
            if not rec.first_due_date:
                raise ValidationError(_("Due date must be set. Please set the 'Due Date of Invoices' field."))
            if rec.first_due_date < rec.month:
                raise ValidationError(_("Due date cannot be earlier than the loan start date (For Month)."))
            if rec.invoice_ids:
                raise ValidationError(_("Invoices have already been created for this loan."))

            # 🔍 Check for the required journal
            journal = self.env['account.journal'].search([
                ('name', '=', 'Employee Loans'),
                ('company_id', '=', rec.company_id.id),
                ('type', '=', 'sale'),  # Must be a customer journal (sale)
            ], limit=1)

            if not journal:
                raise ValidationError(_(
                    "Journal 'Employee Loans' not found for company %(company)s. "
                    "Please create the 'Employee Loans' journal inside the Accounting > Configuration > Journals.",
                    company=rec.company_id.name
                ))

            amount_per_installment = rec.amount / rec.installment_count
            invoices = []

            for i in range(rec.installment_count):
                due_date_installment = rec.first_due_date + relativedelta(months=i)
                invoice_line_name = _(f"Loan Repayment for {rec.employee_id.name} - Installment {i + 1}")

                invoice_vals = {
                    'move_type': 'out_invoice',
                    'partner_id': rec.employee_id.address_home_id.id,
                    'invoice_date': fields.Date.today(),
                    'invoice_date_due': due_date_installment,
                    'company_id': rec.company_id.id,
                    'ref': rec.name or 'Loan Request',
                    'loan_request_id': rec.id,
                    'journal_id': journal.id,
                    'is_loan_invoice': True,
                    'invoice_line_ids': [(0, 0, {
                        'name': invoice_line_name,
                        'quantity': 1,
                        'price_unit': amount_per_installment,
                        'tax_ids': [(6, 0, [])],
                    })]
                }

                try:
                    invoice = self.env['account.move'].with_context(default_move_type='out_invoice').create(invoice_vals)
                    invoice.action_post()
                    invoices.append(invoice.id)
                except Exception as e:
                    raise UserError(
                        _("Failed to create or post the invoice for loan request '%(loan_name)s'. "
                          "Error: %(error)s. "
                          "Please check accounting configurations or contact your administrator.",
                          loan_name=rec.name, error=str(e))
                    )

            rec.write({
                'state': 'inv_created',
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', invoices)],
            'name': _('Loan Installment Invoices'),
        }

    def create_disbursement_bill(self):
        for rec in self:
            if rec.disbursement_invoice_id:
                raise ValidationError(_("A disbursement bill already exists for this loan."))

            if not rec.employee_id:
                raise ValidationError(_("Employee must be selected to create a disbursement bill."))

            if not rec.employee_id.address_home_id:
                raise ValidationError(_("Employee %s has no private address.", rec.employee_id.name))

            if not rec.employee_id.address_home_id.supplier_rank:
                raise ValidationError(_("The private address of employee %s is not marked as a supplier. Please update the partner's vendor status.", rec.employee_id.name))

            if not rec.amount or rec.amount <= 0:
                raise ValidationError(_("Loan amount must be greater than zero."))

            # Search for the correct journal
            journal = self.env['account.journal'].search([
                ('name', '=', 'Employee Loans'),
                ('type', '=', 'purchase'),
                ('company_id', '=', rec.company_id.id)
            ], limit=1)

            if not journal:
                raise ValidationError(_("Journal 'Employee Loans' (Purchase) not found for company %s. Please create it.", rec.company_id.name))

            # Prepare invoice values
            invoice_vals = {
                'move_type': 'in_invoice',
                'partner_id': rec.employee_id.address_home_id.id,
                'invoice_date': fields.Date.context_today(self),
                'company_id': rec.company_id.id,
                'ref': rec.name or _('Loan Disbursement'),
                'loan_request_id': rec.id,
                'is_loan_invoice': True,
                'journal_id': journal.id,
                'invoice_line_ids': [(0, 0, {
                    'name': _('Loan Disbursement to %s', rec.employee_id.name),
                    'quantity': 1,
                    'price_unit': rec.amount,
                    'tax_ids': False,
                })]
            }

            # Create and post the invoice
            try:
                invoice = self.env['account.move'].with_context(default_move_type='in_invoice').create(invoice_vals)
                invoice.action_post()
                rec.disbursement_invoice_id = invoice.id
            except Exception as e:
                raise UserError(_("Failed to create or post the disbursement bill: %s", str(e)))

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': invoice.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_view_disbursement_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Disbursement Bill'),
            'res_model': 'account.move',
            'res_id': self.disbursement_invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class AccountMove(models.Model):
	_inherit = 'account.move'

	loan_request_id = fields.Many2one('loan.requests', string='Loan Request')
	is_loan_invoice = fields.Boolean(string='Loan', default=False, copy=False)