# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

from odoo.http import request
from odoo import api, fields, models, _
from psycopg2 import errorcodes
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError


class PortalEmployeeWizard(models.TransientModel):
	_name = 'employee.present.user.portal'
	_description = 'Grant Only Portal Access'


	create_employee_id = fields.Many2one('hr.employee',string="Employee")
	user_id = fields.Many2one('res.users',string="User")
	groups_id = fields.Many2many('res.groups',string="Groups/Access Rights")


	def action_apply(self):
		self.ensure_one()
		if self.user_id:
			if self.groups_id:
				self.user_id.sudo().write({'groups_id': [(6,0, self.groups_id.ids)], 'active': True})
		return {'type': 'ir.actions.act_window_close'}