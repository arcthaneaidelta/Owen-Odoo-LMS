from odoo import models, fields, api

class MoveEXT(models.Model):
	_inherit = "account.move"

	advance_id = fields.Many2one("advance.requests", string="Advance Reference",copy=False)