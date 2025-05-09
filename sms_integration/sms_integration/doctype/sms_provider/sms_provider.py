# Copyright (c) 2025, Hybrowlabs Technology and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from sms_integration.utils import send_sms

class SMSProvider(Document):
    def validate(self):
        if not self.sender_id:
            frappe.throw("Sender ID is required to send SMS.")
        if self.auth_type == "API" and not self.api_key:
            frappe.throw("API Key is required to send SMS.")
        if self.auth_type == "USER_PASS":
            if not self.username:
                frappe.throw("Username is required to send SMS.")
            if not self.password:
                frappe.throw("Password is required to send SMS.")
        self.validate_default()

    def validate_default(self):
        providers = frappe.db.count("SMS Provider", filters={"default_sending": 1})
        if providers > 1:
            frappe.throw("Default Sending can only be set for one provider.")
        if providers == 0:
            self.default_sending = 1

    @frappe.whitelist()
    def send_sms(self, phone_number, sms_template, context={}, sender_id=None):
        """
        Send SMS using the selected provider

        Args:
            phone_number (str): Phone number to send SMS
            sms_template (str): SMS Template ID to use (DocType: SMS Template)
            sender_id (str, optional): Sender ID. Defaults to None.
            context (dict, optional): Context to render the SMS Template. Defaults to {}.
        """
        return send_sms(phone_number, sms_template, context, sender_id, self)