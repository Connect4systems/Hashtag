from __future__ import annotations

import json

import frappe
from frappe import _

from hashtag.integrations.hashtag_client import HashtagClient

HASHTAG_FIELDS = {
	"hashtag_shipment_created": {"fieldtype": "Check", "label": "Hashtag Shipment Created"},
	"hashtag_shipment_id": {"fieldtype": "Data", "label": "Hashtag Shipment ID"},
	"hashtag_tracking_number": {"fieldtype": "Data", "label": "Hashtag Tracking Number"},
	"hashtag_status": {"fieldtype": "Data", "label": "Hashtag Status"},
	"hashtag_label_url": {"fieldtype": "Small Text", "label": "Hashtag Label URL"},
	"hashtag_last_sync": {"fieldtype": "Datetime", "label": "Hashtag Last Sync"},
	"hashtag_api_response": {"fieldtype": "Code", "label": "Hashtag API Response", "options": "JSON"},
}

SECTOR_ALIASES = {
	"175": "Shorouk",
	"185": "New Cairo",
	"205": "Maadi",
	"295": "Nasr City",
	"305": "Madinaty",
	"355": "Mohandessin",
	"360": "Haram",
	"365": "Faisal",
	"500": "Obour",
	"28947": "Heliopolis",
	"28955": "Giza",
	"28962": "6 October",
	"28963": "Sheikh Zayed",
	"28967": "Imbaba",
}


def _text(value) -> str:
	return str(value or "").strip()


def _require(doc, fieldname: str, label: str):
	value = doc.get(fieldname)
	if value in (None, ""):
		frappe.throw(_("{0} is required before creating Hashtag shipment.").format(label))
	return value


def _first(*values):
	for value in values:
		if _text(value):
			return value
	return ""


def _first_response_item(response: dict) -> dict:
	items = response.get("response") if isinstance(response, dict) else None
	if isinstance(items, list) and items and isinstance(items[0], dict):
		return items[0]
	return {}


def _response_rows(response: dict) -> list[dict]:
	for key in ("response", "data"):
		rows = response.get(key) if isinstance(response, dict) else None
		if isinstance(rows, list):
			return rows
	return []


def _get_response_value(response: dict, *keys):
	for key in keys:
		value = response
		for part in key.split("."):
			if not isinstance(value, dict):
				value = None
				break
			value = value.get(part)
		if value not in (None, ""):
			return value
	return ""


def _field_can_update(shipment, fieldname: str) -> bool:
	if shipment.docstatus != 1:
		return True
	field = frappe.get_meta("Shipment").get_field(fieldname)
	return bool(field and field.allow_on_submit)


def _set_if_allowed(shipment, fieldname: str, value):
	if value and not shipment.get(fieldname) and _field_can_update(shipment, fieldname):
		shipment.set(fieldname, value)


def _set_standard_status_if_allowed(shipment, status: str):
	for fieldname in ("tracking_status", "status", "shipment_status"):
		field = frappe.get_meta("Shipment").get_field(fieldname)
		if not field or not _field_can_update(shipment, fieldname):
			continue
		options = [option.strip() for option in (field.options or "").split("\n") if option.strip()]
		if not options or status in options:
			shipment.set(fieldname, status)
			return


def build_shipment_payload(shipment) -> dict:
	settings = frappe.get_single("Hashtag Settings")
	_require(shipment, "delivery_address_name", _("Delivery Address"))

	contact = frappe.get_doc("Contact", shipment.delivery_contact) if frappe.db.exists("Contact", shipment.get("delivery_contact")) else None
	address = frappe.get_doc("Address", shipment.delivery_address_name)
	sector_id = _first(shipment.get("hashtag_sector_id"), address.get("hashtag_sector_id"), address.get("city"), settings.default_sector_id)
	sector = frappe.get_doc("Hashtag Sector", sector_id) if frappe.db.exists("Hashtag Sector", sector_id) else None
	keyword = _first(
		shipment.get("hashtag_keyword"),
		address.get("hashtag_keyword"),
		sector.get("keyword") if sector else "",
		settings.default_keyword,
	)
	if not sector_id:
		frappe.throw(_("Hashtag Sector ID is required on the delivery Address, Shipment, or Hashtag Settings. Select the Hashtag area on the Address."))
	phone_1 = _first(
		shipment.get("delivery_contact_mobile"),
		contact.get("mobile_no") if contact else "",
		contact.get("phone") if contact else "",
		shipment.get("delivery_contact"),
	)
	if not phone_1:
		frappe.throw(_("Delivery contact mobile number is required before creating Hashtag shipment."))

	return {
		"sector_id": sector_id,
		"keyword": keyword,
		"product_name": shipment.description_of_content or shipment.name,
		"product_desc": shipment.description_of_content or "",
		"phone_1": phone_1,
		"phone_2": _first(contact.get("phone") if contact else "", contact.get("mobile_no") if contact else ""),
		"price": int(float(shipment.value_of_goods or 0)),
		"weight": str(shipment.total_weight or ""),
		"address": _first(shipment.delivery_address, address.get_display()),
		"notes": shipment.description_of_content or "",
		"client_name": _first(shipment.delivery_contact_name, contact.get("full_name") if contact else "", shipment.delivery_to),
		"order_id": shipment.name,
		"email": _first(shipment.delivery_contact_email, contact.get("email_id") if contact else ""),
		"client_id": "",
		"quantity": str(len(shipment.get("shipment_parcel", [])) or 1),
	}


@frappe.whitelist()
def create_hashtag_shipment(shipment_name: str):
	shipment = frappe.get_doc("Shipment", shipment_name)
	if shipment.docstatus == 2:
		frappe.throw(_("Cannot create Hashtag shipment for a cancelled Shipment."))
	if shipment.get("hashtag_shipment_created"):
		frappe.throw(_("Hashtag shipment already exists for {0}.").format(shipment.name))

	client = HashtagClient()
	payload = build_shipment_payload(shipment)
	response = client.post(client.settings.create_shipment_path, payload)
	_apply_hashtag_response(shipment, response)
	shipment.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"tracking_number": shipment.get("hashtag_tracking_number") or shipment.get("awb_number"),
		"shipment_id": shipment.get("hashtag_shipment_id") or shipment.get("shipment_id"),
		"status": shipment.get("hashtag_status"),
	}


@frappe.whitelist()
def mark_existing_hashtag_shipment(shipment_name: str, shipment_id: str = "", tracking_number: str = "", status: str = "Created"):
	shipment = frappe.get_doc("Shipment", shipment_name)
	if shipment.docstatus == 2:
		frappe.throw(_("Cannot update a cancelled Shipment."))
	if not _text(tracking_number):
		frappe.throw(_("Tracking Number / Waybill is required."))
	response = {"response": [{"id": shipment_id, "waybill": tracking_number, "status_en": status}]}
	_apply_hashtag_response(shipment, response)
	shipment.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"tracking_number": shipment.get("hashtag_tracking_number"),
		"shipment_id": shipment.get("hashtag_shipment_id"),
		"status": shipment.get("hashtag_status"),
	}


@frappe.whitelist()
def get_hashtag_governments():
	client = HashtagClient()
	response = client.post("/shipment.php?action=getAllGov", {})
	if _response_rows(response):
		return response

	sectors_response = client.post("/shipment.php?action=getAllSectors", {"gov_id": ""})
	governments = {}
	for row in _response_rows(sectors_response):
		gov_id = row.get("gov_id")
		if gov_id and gov_id not in governments:
			governments[gov_id] = {"id": gov_id, "name": row.get("gov_name") or gov_id}
	return {"response": list(governments.values())}


@frappe.whitelist()
def get_hashtag_sectors(gov_id: str):
	if not _text(gov_id):
		frappe.throw(_("Government ID is required."))
	client = HashtagClient()
	return client.post("/shipment.php?action=getAllSectors", {"gov_id": gov_id})


@frappe.whitelist()
def search_hashtag_sectors(txt: str = ""):
	client = HashtagClient()
	response = client.post("/shipment.php?action=getAllSectors", {"gov_id": ""})
	txt = _text(txt).casefold()
	rows = _response_rows(response)
	if txt:
		rows = [
			row
			for row in rows
			if txt in _text(row.get("id")).casefold()
			or txt in _text(row.get("name")).casefold()
			or txt in _text(row.get("gov_name")).casefold()
			or txt in _text(row.get("key_words")).casefold()
			or txt in _text(SECTOR_ALIASES.get(str(row.get("id")))).casefold()
		]
	for row in rows:
		row["alias"] = SECTOR_ALIASES.get(str(row.get("id")), "")
	return {"response": rows[:50]}


def _apply_hashtag_response(shipment, response: dict):
	item = _first_response_item(response)
	tracking_number = _first(
		_get_response_value(item, "waybill"),
		_get_response_value(response, "tracking_number", "awb_number", "awb", "data.tracking_number", "data.awb_number", "data.awb"),
	)
	shipment_id = _first(_get_response_value(item, "id"), _get_response_value(response, "shipment_id", "id", "data.shipment_id", "data.id"))
	status = _first(
		_get_response_value(item, "status_en", "name_en", "status_ar", "name_ar"),
		_get_response_value(response, "status", "shipment_status", "data.status", "data.shipment_status"),
		"Created",
	)
	label_url = _get_response_value(response, "label_url", "tracking_url", "data.label_url", "data.tracking_url")

	shipment.hashtag_shipment_created = 1
	shipment.hashtag_shipment_id = shipment_id
	shipment.hashtag_tracking_number = tracking_number
	shipment.hashtag_status = status
	shipment.hashtag_label_url = label_url
	shipment.hashtag_last_sync = frappe.utils.now_datetime()
	shipment.hashtag_api_response = json.dumps(response, ensure_ascii=False, indent=2, default=str)

	_set_if_allowed(shipment, "shipment_id", shipment_id)
	_set_if_allowed(shipment, "awb_number", tracking_number)
	_set_if_allowed(shipment, "tracking_url", label_url)
	if status:
		_set_standard_status_if_allowed(shipment, status)


@frappe.whitelist()
def sync_hashtag_status(shipment_name: str):
	shipment = frappe.get_doc("Shipment", shipment_name)
	if shipment.docstatus == 2:
		frappe.throw(_("Cannot sync a cancelled Shipment."))
	client = HashtagClient()
	path = client.settings.tracking_path
	if not path:
		frappe.throw(_("Tracking Path is not configured in Hashtag Settings."))
	waybill = shipment.get("hashtag_tracking_number") or shipment.get("awb_number")
	if not waybill:
		frappe.throw(_("Hashtag Waybill is required before syncing status."))
	response = client.post(path, {"waybill": waybill})
	_apply_hashtag_response(shipment, response)
	shipment.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": shipment.get("hashtag_status"), "response": response}


@frappe.whitelist()
def sync_open_hashtag_statuses(limit: int = 50):
	shipments = frappe.get_all(
		"Shipment",
		filters={
			"docstatus": ["!=", 2],
			"hashtag_shipment_created": 1,
			"hashtag_tracking_number": ["is", "set"],
		},
		fields=["name"],
		limit_page_length=limit,
		order_by="modified asc",
	)

	results = {"synced": 0, "failed": []}
	for row in shipments:
		try:
			sync_hashtag_status(row.name)
			results["synced"] += 1
		except Exception as exc:
			frappe.log_error(frappe.get_traceback(), f"Hashtag status sync failed for {row.name}")
			results["failed"].append({"shipment": row.name, "error": str(exc)})

	return results
