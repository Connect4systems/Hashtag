from __future__ import annotations

from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def install():
	"""Install Hashtag Shipment integration into an existing Hashtag app/site.

	This installer is intentionally callable with:
		bench --site <site> execute hashtag.integrations.install.install

	It avoids requiring a merge into an existing hooks.py/patches.txt, which makes it safer
	for existing Hashtag repositories that already have their own app metadata files.
	"""
	create_address_fields()
	hide_address_integration_fields()
	create_shipment_fields()
	create_shipment_client_script()
	create_address_client_script()
	frappe.db.commit()


def configure_settings(api_password: str, default_sector_id: str | None = None, default_keyword: str | None = None):
	"""Apply the documented Hashtag Express API defaults to Hashtag Settings."""
	doc = frappe.get_single("Hashtag Settings")
	doc.enabled = 1
	doc.base_url = "https://hashtag-express.com/api"
	doc.create_shipment_path = "/shipment.php?action=addShipment"
	doc.tracking_path = "/shipment.php?action=statusHistory"
	doc.auth_scheme = "Form Credentials"
	doc.api_name = "hashtag"
	doc.api_password = api_password
	if default_sector_id is not None:
		doc.default_sector_id = default_sector_id
	if default_keyword is not None:
		doc.default_keyword = default_keyword
	doc.save(ignore_permissions=True)
	frappe.db.commit()


def create_shipment_fields():
	if not frappe.db.exists("DocType", "Shipment"):
		return

	create_custom_fields(
		{
			"Shipment": [
				{
					"fieldname": "hashtag_section",
					"fieldtype": "Section Break",
					"insert_after": "tracking_status_info",
					"label": "Hashtag Integration",
				},
				{
					"fieldname": "hashtag_shipment_created",
					"fieldtype": "Check",
					"insert_after": "hashtag_section",
					"label": "Hashtag Shipment Created",
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_sector_id",
					"fieldtype": "Data",
					"insert_after": "hashtag_shipment_created",
					"label": "Hashtag Sector ID",
				},
				{
					"fieldname": "hashtag_keyword",
					"fieldtype": "Data",
					"insert_after": "hashtag_sector_id",
					"label": "Hashtag Keyword",
				},
				{
					"fieldname": "hashtag_shipment_id",
					"fieldtype": "Data",
					"insert_after": "hashtag_keyword",
					"label": "Hashtag Shipment ID",
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_tracking_number",
					"fieldtype": "Data",
					"insert_after": "hashtag_shipment_id",
					"label": "Hashtag Tracking Number",
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_status",
					"fieldtype": "Data",
					"insert_after": "hashtag_tracking_number",
					"label": "Hashtag Status",
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_column_break",
					"fieldtype": "Column Break",
					"insert_after": "hashtag_status",
				},
				{
					"fieldname": "hashtag_label_url",
					"fieldtype": "Small Text",
					"insert_after": "hashtag_column_break",
					"label": "Hashtag Label URL",
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_last_sync",
					"fieldtype": "Datetime",
					"insert_after": "hashtag_label_url",
					"label": "Hashtag Last Sync",
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_api_response",
					"fieldtype": "Code",
					"insert_after": "hashtag_last_sync",
					"label": "Hashtag API Response",
					"options": "JSON",
					"read_only": 1,
				},
			],
		},
		ignore_validate=True,
	)


def create_address_fields():
	if not frappe.db.exists("DocType", "Address"):
		return

	create_custom_fields(
		{
			"Address": [
				{
					"fieldname": "hashtag_section",
					"fieldtype": "Section Break",
					"insert_after": "city",
					"label": "Hashtag Delivery Area",
					"hidden": 1,
				},
				{
					"fieldname": "hashtag_gov_id",
					"fieldtype": "Data",
					"insert_after": "hashtag_section",
					"label": "Hashtag Government ID",
					"hidden": 1,
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_gov_name",
					"fieldtype": "Data",
					"insert_after": "hashtag_gov_id",
					"label": "Hashtag Government",
					"hidden": 1,
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_sector_id",
					"fieldtype": "Data",
					"insert_after": "hashtag_gov_name",
					"label": "Hashtag Sector ID",
					"hidden": 1,
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_sector_name",
					"fieldtype": "Data",
					"insert_after": "hashtag_sector_id",
					"label": "Hashtag Sector",
					"hidden": 1,
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_keyword",
					"fieldtype": "Data",
					"insert_after": "hashtag_sector_name",
					"label": "Hashtag Keyword",
					"hidden": 1,
					"read_only": 1,
				},
			],
		},
		ignore_validate=True,
	)


def hide_address_integration_fields():
	for fieldname in (
		"hashtag_section",
		"hashtag_gov_id",
		"hashtag_gov_name",
		"hashtag_sector_id",
		"hashtag_sector_name",
		"hashtag_keyword",
	):
		custom_field = f"Address-{fieldname}"
		if frappe.db.exists("Custom Field", custom_field):
			frappe.db.set_value("Custom Field", custom_field, "hidden", 1)
			if fieldname != "hashtag_section":
				frappe.db.set_value("Custom Field", custom_field, "read_only", 1)


def create_shipment_client_script():
	if not frappe.db.exists("DocType", "Client Script"):
		return

	_create_client_script("Hashtag Shipment Buttons", "Shipment", "hashtag_shipment.js")


def create_address_client_script():
	if not frappe.db.exists("DocType", "Client Script"):
		return

	_create_client_script("Hashtag Address Area Picker", "Address", "hashtag_address.js")


def _create_client_script(script_name: str, dt: str, filename: str):
	js_path = Path(frappe.get_app_path("hashtag")) / "public" / "js" / filename
	script = js_path.read_text(encoding="utf-8")

	if frappe.db.exists("Client Script", script_name):
		doc = frappe.get_doc("Client Script", script_name)
	else:
		doc = frappe.new_doc("Client Script")
		doc.name = script_name

	doc.dt = dt
	doc.enabled = 1
	doc.script = script
	doc.save(ignore_permissions=True)
