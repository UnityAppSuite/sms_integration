import frappe
import requests
from frappe.utils import cint

@frappe.whitelist()
def send_sms(phone_number, sms_template, context={}, sender_id=None, doc=None):
    """
    Send SMS using the selected provider

    Args:
        phone_number (str): Phone number to send SMS
        sms_template (str): SMS Template ID to use (DocType: SMS Template)
        sender_id (str, optional): Sender ID. Defaults to None.
        context (dict, optional): Context to render the SMS Template. Defaults to {}.
        doc (Document, optional): SMS Provider Settings Document. Defaults to None.
    """
    try:
        if not doc:
            doc = frappe.get_doc("SMS Provider", {"default_sending": 1})
        sms_template_doc = frappe.get_doc("SMS Template", sms_template)
        message = frappe.render_template(sms_template_doc.message, context)
        if doc.sms_provider == "Business Lead":
            return business_lead_send_sms(
                doc,
                phone_number,
                message,
                sms_template_doc.template_id,
                sender_id,
            )
        # TODO: Add other providers here
        else:
            frappe.log_error(title=f"Failed to send SMS to {phone_number}", message="SMS Provider not found")
    except Exception as e:
        frappe.log_error(title=f"Failed to send SMS to {phone_number}", message=frappe.get_traceback())
        return False


def business_lead_send_sms(doc, phone_number, message, template_id, sender_id=None):
    """
    Send SMS using Business Lead

    Args:
        doc (Document): SMS Provider Settings Document
        phone_number (str): Phone number to send SMS
        message (str): Message to send
        template_id (str): Template ID to use
        sender_id (str, optional): Sender ID. Defaults to None.
    """
    if not phone_number:
        frappe.throw("Phone Number is required to send SMS.")
    if not message:
        frappe.throw("Message is required to send SMS.")

    url = "http://login.businesslead.co.in/api/mt/SendSMS"
    params = {
        "senderid": sender_id or doc.sender_id,
        "channel": doc.channel,
        "dcs": cint(doc.dcs),
        "flashsms": cint(doc.flash_sms),
        "number": phone_number,
        "text": message,
        "route": cint(doc.route),
        "dlttemplateid": template_id,
        "peid": doc.platform_entity_id,
    }
    if doc.auth_type == "USER_PASS":
        params["user"] = doc.username
        params["password"] = doc.get_password(fieldname="password", raise_exception=False)
    else:
        params["apikey"] = doc.get_password(fieldname="api_key", raise_exception=False)

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        res = response.json()
        if res.get("ErrorCode") == "000":
            return True
        else:
            frappe.logger("sms_integration").exception(
                f"Failed to send SMS: {phone_number} \n{response.status_code}, {response.text}"
            )
            return False
    except requests.RequestException as e:
        frappe.logger("sms_integration").exception(
            f"Failed to send SMS: {phone_number} {e}"
        )
        return False
