import frappe
from frappe.model.document import Document


class HashtagSettings(Document):
	def validate(self):
		if self.base_url:
			self.base_url = self.base_url.rstrip("/")
		if self.create_shipment_path and not self.create_shipment_path.startswith("/"):
			self.create_shipment_path = f"/{self.create_shipment_path}"
		if self.tracking_path and not self.tracking_path.startswith("/"):
			self.tracking_path = f"/{self.tracking_path}"
		if self.cancel_path and not self.cancel_path.startswith("/"):
			self.cancel_path = f"/{self.cancel_path}"

		if self.enabled and not self.get_password("api_password"):
			frappe.throw("API Password is required when Hashtag integration is enabled.")
