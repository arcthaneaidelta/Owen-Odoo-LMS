# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

from odoo import api, fields, models, _
import calendar

class HRContract(models.Model):
	_inherit = 'hr.contract'
	
	advance_limit = fields.Monetary(string='Advance Limit', tracking=True, copy=False)
	availed_advance_amount = fields.Monetary(
		string='Availed Advance Amount (Monthly)',
		store=True,
		tracking=True
	)