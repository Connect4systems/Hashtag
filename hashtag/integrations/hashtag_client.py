from __future__ import annotations

from urllib.parse import urljoin

import frappe
import requests
from frappe import _


class HashtagAPIError(frappe.ValidationError):
	pass


class HashtagClient:
	def __init__(self):
		self.settings = frappe.get_single("Hashtag Settings")
		if not self.settings.enabled:
			raise HashtagAPIError(_("Hashtag integration is disabled."))
		if not self.settings.base_url:
			raise HashtagAPIError(_("Hashtag Base URL is required in Hashtag Settings."))
		self.api_password = self.settings.get_password("api_password")
		if not self.settings.api_name or not self.api_password:
			raise HashtagAPIError(_("Hashtag API Name and API Password are required."))

	def _url(self, path: str) -> str:
		return urljoin(f"{self.settings.base_url.rstrip('/')}/", (path or "").lstrip("/"))

	def _headers(self) -> dict[str, str]:
		headers = {"Accept": "application/json", "Content-Type": "application/json"}
		if self.settings.auth_scheme == "Headers":
			headers.update({"X-API-Name": self.settings.api_name, "X-API-Password": self.api_password})
		return headers

	def _auth(self):
		if self.settings.auth_scheme == "Basic Auth":
			return (self.settings.api_name, self.api_password)
		return None

	def _payload(self, payload: dict) -> dict:
		if self.settings.auth_scheme == "JSON Credentials":
			payload = payload.copy()
			payload.update({"api_name": self.settings.api_name, "api_password": self.api_password})
		return payload

	def post(self, path: str, payload: dict) -> dict:
		url = self._url(path)
		try:
			response = requests.post(
				url,
				auth=self._auth(),
				headers=self._headers(),
				json=self._payload(payload),
				timeout=self.settings.request_timeout or 30,
			)
		except requests.RequestException as exc:
			frappe.log_error(frappe.get_traceback(), "Hashtag API request failed")
			raise HashtagAPIError(_("Hashtag API request failed: {0}").format(exc))

		return self._decode_response(response)

	def get(self, path: str) -> dict:
		url = self._url(path)
		try:
			response = requests.get(
				url,
				auth=self._auth(),
				headers=self._headers(),
				timeout=self.settings.request_timeout or 30,
			)
		except requests.RequestException as exc:
			frappe.log_error(frappe.get_traceback(), "Hashtag API request failed")
			raise HashtagAPIError(_("Hashtag API request failed: {0}").format(exc))

		return self._decode_response(response)

	def _decode_response(self, response) -> dict:
		try:
			data = response.json()
		except ValueError:
			data = {"message": response.text}

		if self.settings.debug_logging:
			frappe.logger("hashtag").info({"status_code": response.status_code, "response": data})

		if response.status_code >= 400:
			raise HashtagAPIError(_("Hashtag API returned HTTP {0}: {1}").format(response.status_code, data))

		if isinstance(data, dict) and str(data.get("status", "")).lower() in {"error", "failed", "failure"}:
			raise HashtagAPIError(_("Hashtag API returned an error: {0}").format(data))

		return data if isinstance(data, dict) else {"data": data}
