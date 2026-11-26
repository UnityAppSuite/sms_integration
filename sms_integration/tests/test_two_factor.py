# Copyright (c) 2025, Hybrowlabs Technology and contributors
# For license information, please see license.txt

import unittest
from unittest.mock import Mock, patch

import frappe
import requests

import sms_integration.utils.sms as sms
from sms_integration.utils import send_sms


def _provider(entity_id="1101000000000"):
	doc = Mock()
	doc.sms_provider = "2Factor"
	doc.sender_id = "TESTHD"
	doc.platform_entity_id = entity_id
	doc.get_password.return_value = "secret-key"
	return doc


def _response(status_code, body=None, non_json=False):
	response = Mock()
	response.status_code = status_code
	response.ok = status_code < 400
	if non_json:
		response.json.side_effect = ValueError("not json")
	else:
		response.json.return_value = body
	return response


class TestTwoFactorSMS(unittest.TestCase):
	"""2Factor sending without a live account or a real SMS."""

	def _send(self, post, entity_id="1101000000000", template_id="1107000000000", sender_id=None):
		log = Mock()
		with (
			patch.object(sms.requests, "post", side_effect=post) as posted,
			patch.object(sms.frappe, "logger", return_value=log),
		):
			result = sms.two_factor_send_sms(
				_provider(entity_id),
				"919999999999",
				"Hello Asha, test message.",
				template_id,
				sender_id,
			)
		return result, posted, log

	def test_success_sends_transactional_fields(self):
		result, posted, log = self._send(
			lambda *args, **kwargs: _response(200, {"Status": "Success", "Details": "req-1"})
		)

		self.assertTrue(result)
		log.error.assert_not_called()
		posted.assert_called_once_with(
			"https://2factor.in/API/R1/",
			data={
				"module": "TRANS_SMS",
				"apikey": "secret-key",
				"to": "919999999999",
				"from": "TESTHD",
				"msg": "Hello Asha, test message.",
				"peid": "1101000000000",
				"ctid": "1107000000000",
			},
			timeout=15,
		)

	def test_explicit_sender_overrides_provider_sender(self):
		result, posted, _log = self._send(
			lambda *args, **kwargs: _response(200, {"Status": "Success", "Details": "req-1"}),
			sender_id="OTHER1",
		)

		self.assertTrue(result)
		self.assertEqual(posted.call_args.kwargs["data"]["from"], "OTHER1")

	def test_provider_error_returns_false_without_logging_secrets(self):
		result, posted, log = self._send(
			lambda *args, **kwargs: _response(200, {"Status": "Error", "Details": "Invalid Template"})
		)

		self.assertFalse(result)
		posted.assert_called_once()
		message = log.error.call_args.args[0]
		self.assertIn("HTTP 200", message)
		self.assertIn("Invalid Template", message)
		self.assertNotIn("secret-key", message)
		self.assertNotIn("919999999999", message)
		self.assertNotIn("test message", message)

	def test_http_error_returns_false(self):
		result, _posted, log = self._send(
			lambda *args, **kwargs: _response(500, {"Status": "Error", "Details": "server"})
		)

		self.assertFalse(result)
		self.assertIn("HTTP 500", log.error.call_args.args[0])

	def test_non_json_response_returns_false(self):
		result, _posted, log = self._send(lambda *args, **kwargs: _response(502, non_json=True))

		self.assertFalse(result)
		self.assertIn("non-JSON", log.error.call_args.args[0])
		self.assertNotIn("secret-key", log.error.call_args.args[0])

	def test_timeout_returns_false(self):
		def timeout(*args, **kwargs):
			raise requests.Timeout("timed out")

		result, posted, log = self._send(timeout)

		self.assertFalse(result)
		posted.assert_called_once()
		self.assertIn("timed out", log.error.call_args.args[0])
		self.assertNotIn("secret-key", log.error.call_args.args[0])

	def test_missing_dlt_ids_raise_before_request(self):
		with patch.object(sms.requests, "post") as posted:
			with self.assertRaises(frappe.ValidationError):
				sms.two_factor_send_sms(_provider(""), "919999999999", "Hello", "1107000000000")
			with self.assertRaises(frappe.ValidationError):
				sms.two_factor_send_sms(_provider(), "919999999999", "Hello", "")
		posted.assert_not_called()

	def test_send_sms_routes_provider_and_raises_validation_error(self):
		template = Mock(message="Hello {{ name }}", template_id="")
		provider = _provider()
		with (
			patch.object(sms.frappe, "get_doc", return_value=template),
			patch.object(sms.frappe, "render_template", return_value="Hello Asha"),
			patch.object(sms, "two_factor_send_sms", return_value=True) as two_factor,
			patch.object(sms, "business_lead_send_sms", return_value=True) as business_lead,
			patch.object(sms.requests, "post") as posted,
		):
			provider.sms_provider = "Business Lead"
			self.assertTrue(send_sms("919999999999", "Template", {"name": "Asha"}, None, provider))
			business_lead.assert_called_once()
			two_factor.assert_not_called()

			business_lead.reset_mock()
			provider.sms_provider = "2Factor"
			template.template_id = "1107000000000"
			self.assertTrue(send_sms("919999999999", "Template", {"name": "Asha"}, None, provider))
			two_factor.assert_called_once()
			business_lead.assert_not_called()

			template.template_id = ""
			two_factor.side_effect = frappe.ValidationError("Template ID is required")
			with self.assertRaises(frappe.ValidationError):
				send_sms("919999999999", "Template", {"name": "Asha"}, None, provider)
		posted.assert_not_called()
