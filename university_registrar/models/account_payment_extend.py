# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    bank_reference = fields.Char(string='Bank Reference')

    def _create_payment_vals_from_wizard(self, batch_result):
        # OVERRIDE
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        payment_vals['bank_reference'] = self.bank_reference
        return payment_vals

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    bank_reference = fields.Char(string='Bank Reference', tracking=True)
