from __future__ import annotations

from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from hashtag.integrations.hashtag_client import HashtagClient
from hashtag.integrations.hashtag_shipment import SECTOR_ALIASES, _response_rows


def install():
	"""Install Hashtag Shipment integration into an existing Hashtag app/site.

	This installer is intentionally callable with:
		bench --site <site> execute hashtag.integrations.install.install

	It avoids requiring a merge into an existing hooks.py/patches.txt, which makes it safer
	for existing Hashtag repositories that already have their own app metadata files.
	"""
	configure_address_city_link()
	create_address_fields()
	hide_address_integration_fields()
	create_shipment_fields()
	configure_shipment_integration_fields()
	create_shipment_client_script()
	create_address_client_script()
	frappe.db.commit()


@frappe.whitelist()
def sync_hashtag_sectors():
	"""Sync Hashtag sectors into the local Hashtag Sector master."""
	client = HashtagClient()
	response = client.post("/shipment.php?action=getAllSectors", {"gov_id": ""})
	count = 0
	for row in _response_rows(response):
		sector_id = str(row.get("id") or "").strip()
		if not sector_id:
			continue

		doc = frappe.get_doc("Hashtag Sector", sector_id) if frappe.db.exists("Hashtag Sector", sector_id) else frappe.new_doc("Hashtag Sector")
		doc.sector_id = sector_id
		doc.sector_name = row.get("name") or sector_id
		doc.gov_id = row.get("gov_id") or ""
		doc.gov_name = row.get("gov_name") or ""
		doc.keyword = row.get("key_words") or ""
		doc.alias = SECTOR_ALIASES.get(sector_id, "")
		doc.enabled = 1
		doc.save(ignore_permissions=True)
		count += 1

	frappe.db.commit()
	return count


def configure_address_city_link():
	if not frappe.db.exists("DocType", "Address") or not frappe.db.exists("DocType", "Hashtag Sector"):
		return

	make_property_setter("Address", "city", "options", "Hashtag Sector", "Text", for_doctype=False)
	make_property_setter("Address", "city", "fieldtype", "Link", "Select", for_doctype=False)
	make_property_setter("Address", "city", "description", "Search and select a Hashtag delivery area.", "Small Text", for_doctype=False)


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
					"allow_on_submit": 1,
					"insert_after": "hashtag_section",
					"label": "Hashtag Shipment Created",
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_sector_id",
					"fieldtype": "Data",
					"allow_on_submit": 1,
					"insert_after": "hashtag_shipment_created",
					"label": "Hashtag Sector ID",
				},
				{
					"fieldname": "hashtag_keyword",
					"fieldtype": "Data",
					"allow_on_submit": 1,
					"insert_after": "hashtag_sector_id",
					"label": "Hashtag Keyword",
				},
				{
					"fieldname": "hashtag_shipment_id",
					"fieldtype": "Data",
					"allow_on_submit": 1,
					"insert_after": "hashtag_keyword",
					"label": "Hashtag Shipment ID",
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_tracking_number",
					"fieldtype": "Data",
					"allow_on_submit": 1,
					"insert_after": "hashtag_shipment_id",
					"label": "Hashtag Tracking Number",
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_status",
					"fieldtype": "Data",
					"allow_on_submit": 1,
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
					"allow_on_submit": 1,
					"insert_after": "hashtag_column_break",
					"label": "Hashtag Label URL",
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_last_sync",
					"fieldtype": "Datetime",
					"allow_on_submit": 1,
					"insert_after": "hashtag_label_url",
					"label": "Hashtag Last Sync",
					"read_only": 1,
				},
				{
					"fieldname": "hashtag_api_response",
					"fieldtype": "Code",
					"allow_on_submit": 1,
					"insert_after": "hashtag_last_sync",
					"label": "Hashtag API Response",
					"options": "JSON",
					"read_only": 1,
				},
			],
		},
		ignore_validate=True,
	)


def configure_shipment_integration_fields():
	for fieldname in (
		"hashtag_shipment_created",
		"hashtag_sector_id",
		"hashtag_keyword",
		"hashtag_shipment_id",
		"hashtag_tracking_number",
		"hashtag_status",
		"hashtag_label_url",
		"hashtag_last_sync",
		"hashtag_api_response",
	):
		custom_field = f"Shipment-{fieldname}"
		if frappe.db.exists("Custom Field", custom_field):
			doc = frappe.get_doc("Custom Field", custom_field)
			doc.allow_on_submit = 1
			doc.save(ignore_permissions=True)


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
			doc = frappe.get_doc("Custom Field", custom_field)
			doc.hidden = 1
			if fieldname != "hashtag_section":
				doc.read_only = 1
			doc.save(ignore_permissions=True)


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
