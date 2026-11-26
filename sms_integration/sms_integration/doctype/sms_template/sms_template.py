# Copyright (c) 2025, Hybrowlabs Technology and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SMSTemplate(Document):
	def validate(self):
		if not self.sms_provider:
			return
		provider_type = frappe.db.get_value("SMS Provider", self.sms_provider, "sms_provider")
		if provider_type == "2Factor" and not self.template_id:
			frappe.throw("Template ID (DLT content template ID) is required for 2Factor.")
