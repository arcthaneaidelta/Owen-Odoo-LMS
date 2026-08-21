from odoo import models, fields, api, _
from datetime import date, datetime
import calendar
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError


class AdvanceRequests(models.Model):
    _name = "advance.requests"
    _description = "Advance Requests"
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, copy=False,
                                 tracking=True)
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user, tracking=True,
                              copy=False)
    name = fields.Char(string='Name', copy=False, tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', tracking=True, copy=False)
    requested_date = fields.Datetime(string='Requested Date', tracking=True, copy=False, default=fields.Datetime.now)
    month = fields.Date(string='Month', tracking=True, copy=False)
    amount = fields.Float(string='Amount', tracking=True, copy=False)
    currency_id = fields.Many2one('res.currency', related="company_id.currency_id")
    reason = fields.Text(string='Reason/Description')
    state = fields.Selection([
        ('new', 'New'),
        ('approve', 'Approved'),
        ('inv_created', 'Billed'),
        ('refuse', 'Refused'),
        ('cancel', 'Cancelled')
    ], default='new', tracking=True)

    return_state = fields.Selection([
        ('no', 'Not Returned'),
        ('yes', 'Returned'),
    ], default='no', tracking=True)

    contract_id = fields.Many2one('hr.contract', string='Employee Contract', tracking=True, copy=False)
    advance_limit = fields.Monetary(string='Advance Limit', tracking=True, copy=False,
                                    related="contract_id.advance_limit")
    availed_advance_amount = fields.Monetary(
        string='Availed Advance Amount (Monthly)',
        store=True,
        tracking=True,
        related="contract_id.availed_advance_amount")

    seq_number = fields.Char(string='Seq#', default='New', copy=False, required=True, readonly=True)
    created_invoice = fields.Many2one('account.move', string='Related Invoice', copy=False)
    created_invoices_count = fields.Integer(string='Invoice Count', compute='_compute_created_inv_count')

    @api.onchange('employee_id')
    def get_contract(self):
        if self.contract_id:
            self.contract_id = False

    def _compute_created_inv_count(self):
        for record in self:
            record.created_invoices_count = 1 if record.created_invoice else 0

    def show_created_invs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_in_invoice_type')
        action['domain'] = [('advance_id', '=', self.id)]
        action['context'] = {'create': 0, 'duplicate': 0, 'edit': False}
        return action

    def action_reset(self):
        for rec in self:
            previous_state_was_counted = rec.state in ('approve', 'inv_created')
            rec.state = 'new'
            if previous_state_was_counted:
                rec.set_the_contract_availed_amount_back()

    def action_approve(self):
        for rec in self:
            rec.state = 'approve'
            rec.set_the_contract_availed_amount()

    def action_refuse(self):
        for rec in self:
            previous_state_was_counted = rec.state in ('approve', 'inv_created')
            rec.state = 'refuse'
            if previous_state_was_counted:
                rec.set_the_contract_availed_amount_back()

    def action_cancel(self):
        for rec in self:
            previous_state_was_counted = rec.state in ('approve', 'inv_created')
            rec.state = 'cancel'
            if previous_state_was_counted:
                rec.set_the_contract_availed_amount_back()

    def _get_month_boundaries_for_calc(self, for_date=None):
        calc_date = for_date if for_date else date.today()
        if isinstance(calc_date, str):
            calc_date = fields.Date.from_string(calc_date)
        first_day = calc_date.replace(day=1)
        last_day = calc_date.replace(day=calendar.monthrange(calc_date.year, calc_date.month)[1])
        return first_day, last_day

    def set_the_contract_availed_amount_back(self):
        contracts_to_update = self.mapped('contract_id')
        for contract in contracts_to_update:
            if not contract: continue
            first_day, last_day = self._get_month_boundaries_for_calc()

            advance_requests_ids = self.env['advance.requests'].sudo().search([
                ('contract_id', '=', contract.id),
                ('month', '>=', first_day),
                ('month', '<=', last_day),
                ('state', 'in', ['approve', 'inv_created'])
            ])
            contract.availed_advance_amount = sum(advance_requests_ids.mapped('amount'))

    def set_the_contract_availed_amount(self):
        for rec in self:
            if not rec.month:
                raise ValidationError(_("The 'Month' field must be set on the advance request."))

            first_day, last_day = self._get_month_boundaries_for_calc()

            if rec.employee_id.contract_id and rec.employee_id.contract_id.state == 'open':
                if rec.employee_id.contract_id.id == rec.contract_id.id:
                    if rec.contract_id.advance_limit is not None:
                        other_advance_requests = self.env['advance.requests'].sudo().search([
                            ('contract_id', '=', rec.contract_id.id),
                            ('employee_id', '=', rec.employee_id.id),
                            ('month', '>=', first_day),
                            ('month', '<=', last_day),
                            ('state', 'in', ['approve', 'inv_created']),
                            ('id', '!=',
                             rec._origin.id if rec._origin and rec._origin.id else (rec.id if rec.id else -1))
                        ])
                        already_availed_this_month = sum(other_advance_requests.mapped('amount'))
                        remaining_limit = rec.contract_id.advance_limit - already_availed_this_month

                        if rec.amount <= remaining_limit and rec.amount > 0:
                            rec.contract_id.availed_advance_amount = already_availed_this_month + rec.amount
                        else:
                            raise ValidationError(
                                _("Sorry, the employee's advance limit of %(limit).2f for the current month would be exceeded, "
                                  "or the requested amount %(amount).2f is invalid. "
                                  "Currently availed: %(availed).2f. Remaining: %(remaining).2f.",
                                  limit=rec.contract_id.advance_limit,
                                  amount=rec.amount,
                                  availed=already_availed_this_month,
                                  remaining=remaining_limit)
                            )
                    else:
                        raise ValidationError(
                            _('Sorry, the employee (%(employee_name)s) does not have an advance limit set on their contract (%(contract_name)s).',
                              employee_name=rec.employee_id.name, contract_name=rec.contract_id.name))
                else:
                    raise ValidationError(
                        _('Sorry, the employee (%(employee_name)s) current contract (%(emp_contract_name)s) '
                          'and the advance request contract (%(req_contract_name)s) are mismatched!',
                          employee_name=rec.employee_id.name,
                          emp_contract_name=rec.employee_id.contract_id.name,
                          req_contract_name=rec.contract_id.name))
            else:
                raise ValidationError(_('Sorry, the employee (%(employee_name)s) has no current active contract.',
                                        employee_name=rec.employee_id.name))

    @api.model
    def create(self, vals):
        if 'company_id' in vals:
            vals['seq_number'] = self.env['ir.sequence'].with_company(vals['company_id']).next_by_code(
                'advance.employee.request') or _('New')
        else:
            vals['seq_number'] = self.env['ir.sequence'].next_by_code('advance.employee.request') or _('New')

        record = super(AdvanceRequests, self).create(vals)

        if 'amount' in vals and record.state == 'approve':
            record.set_the_contract_availed_amount()
        return record

    def write(self, vals):
        res = super(AdvanceRequests, self).write(vals)
        if 'amount' in vals or 'state' in vals:
            for rec in self:
                if rec.state in ('approve', 'inv_created'):
                    rec.set_the_contract_availed_amount()
                elif vals.get('state') and vals['state'] not in ('approve', 'inv_created') and rec._origin.state in (
                        'approve', 'inv_created'):
                    rec.set_the_contract_availed_amount_back()
        return res

    def unlink(self):
        for advance in self:
            if advance.state not in ("new", "cancel"):
                raise UserError(
                    _("You can only delete an advance request if it's in 'New' or 'Cancelled' state. This one is '%s'.",
                      advance.state)
                )
        return super(AdvanceRequests, self).unlink()

    def create_bill(self):
        for x in self:
            if not x.employee_id:
                raise ValidationError(_("Employee is not set for this advance request."))

            # Get the partner from work_contact_id (the company contact) or from user
            employee_partner = False
            
            # Option 1: Use work_contact_id (this is the company contact/partner)
            if x.employee_id.work_contact_id:
                employee_partner = x.employee_id.work_contact_id
            # Option 2: Use user's partner if work_contact_id doesn't exist
            elif x.employee_id.user_id and x.employee_id.user_id.partner_id:
                employee_partner = x.employee_id.user_id.partner_id
            
            if not employee_partner:
                raise ValidationError(
                    _("Employee '%(employee_name)s' does not have a linked Contact/Partner. "
                      "Please ensure the employee has a Work Contact or a linked User account.",
                      employee_name=x.employee_id.name)
                )

            # If you need to show the formatted private address for reference:
            private_address = self._format_employee_private_address(x.employee_id)
            
            if not x.amount or x.amount <= 0:
                raise ValidationError(_('Sorry, Amount for the advance request should be greater than zero.'))

            account_move_obj = self.env['account.move']
            today_date = fields.Date.today()
            invoice_line_name = _('Advance for %s - Request: %s', x.employee_id.name, x.name or x.seq_number)

            invoice_vals = {
                'move_type': 'in_invoice',
                'partner_id': employee_partner.id,
                'invoice_date': today_date,
                'date': today_date,
                'invoice_date_due': today_date,
                'company_id': x.company_id.id,
                'ref': x.seq_number,
                'advance_id': x.id,
                'invoice_line_ids': [(0, 0, {
                    'name': invoice_line_name,
                    'quantity': 1,
                    'price_unit': x.amount,
                    'tax_ids': [(6, 0, [])],
                })]
            }

            try:
                bill = account_move_obj.with_context(default_move_type='in_invoice').create(invoice_vals)
                bill.action_post()

                x.write({
                    'state': 'inv_created',
                    'created_invoice': bill.id
                })
            except UserError as e:
                raise e
            except ValidationError as e:
                raise e
            except Exception as e:
                raise UserError(
                    _("Failed to create or post the vendor bill for advance request %(adv_req_name)s. "
                      "Error: %(error)s. Please check accounting configurations.",
                      adv_req_name=x.name, error=str(e))
                )
        return True

    def _format_employee_private_address(self, employee):
        """Helper method to format employee's private address for display"""
        address_parts = []
        if employee.private_street:
            address_parts.append(employee.private_street)
        if employee.private_street2:
            address_parts.append(employee.private_street2)
        
        city_state_zip = []
        if employee.private_city:
            city_state_zip.append(employee.private_city)
        if employee.private_state_id:
            city_state_zip.append(employee.private_state_id.name)
        if employee.private_zip:
            city_state_zip.append(employee.private_zip)
        
        if city_state_zip:
            address_parts.append(" ".join(city_state_zip))
        
        if employee.private_country_id:
            address_parts.append(employee.private_country_id.name)
        
        return "\n".join(address_parts)