from odoo.http import request
from odoo import models, fields, api,_
import uuid

class IRAttachment(models.Model):
	_inherit="ir.attachment"

	def get_access_token_attachment_portal_update(self):
		for x in self:
			x = x.sudo()
			url = self.get_portal_url_website_document()
			sql = "UPDATE ir_attachment SET access_token = '%s' WHERE id = '%s' " % (url, str(x[0]._origin.id))
			try:
				self._cr.execute(sql)
				self._cr.commit()
			except Exception as e:
				pass

	def _portal_ensure_token_website_document(self):
		return str(uuid.uuid4())

	def get_portal_url_website_document(self, suffix=None, report_type=None, download=None, query_string=None, anchor=None):
		url = '%s%s%s%s%s' % (
			self._portal_ensure_token_website_document(),
			'&report_type=%s' % report_type if report_type else '',
			'&download=true' if download else '',
			query_string if query_string else '',
			'#%s' % anchor if anchor else ''
		)
		return url