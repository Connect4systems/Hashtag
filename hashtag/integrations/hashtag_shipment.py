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


def build_shipment_payload(shipment) -> dict:
	_require(shipment, "pickup_date", _("Pickup Date"))
	_require(shipment, "pickup_from", _("Pickup from"))
	_require(shipment, "pickup_to", _("Pickup to"))
	_require(shipment, "delivery_address_name", _("Delivery Address"))
	_require(shipment, "description_of_content", _("Description of Content"))

	return {
		"reference": shipment.name,
		"shipment_type": shipment.shipment_type or "Goods",
		"pickup_type": shipment.pickup_type or "Pickup",
		"pickup": {
			"date": str(shipment.pickup_date),
			"from_time": str(shipment.pickup_from),
			"to_time": str(shipment.pickup_to),
			"type": shipment.pickup_from_type,
			"company": shipment.pickup_company,
			"customer": shipment.pickup_customer,
			"supplier": shipment.pickup_supplier,
			"address_name": shipment.pickup_address_name,
			"address": shipment.pickup_address,
			"contact_name": _first(shipment.pickup_contact_name, shipment.pickup_contact_person),
			"contact_email": shipment.pickup_contact_email,
			"contact": shipment.pickup_contact,
		},
		"delivery": {
			"type": shipment.delivery_to_type,
			"company": shipment.delivery_company,
			"customer": shipment.delivery_customer,
			"supplier": shipment.delivery_supplier,
			"delivery_to": shipment.delivery_to,
			"address_name": shipment.delivery_address_name,
			"address": shipment.delivery_address,
			"contact_name": shipment.delivery_contact_name,
			"contact_email": shipment.delivery_contact_email,
			"contact": shipment.delivery_contact,
		},
		"content": {
			"description": shipment.description_of_content,
			"value_of_goods": float(shipment.value_of_goods or 0),
			"total_weight": float(shipment.total_weight or 0),
			"pallets": shipment.pallets,
			"incoterm": shipment.incoterm,
		},
		"parcels": [parcel.as_dict(no_nulls=True) for parcel in shipment.get("shipment_parcel", [])],
		"delivery_notes": [row.as_dict(no_nulls=True) for row in shipment.get("shipment_delivery_note", [])],
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


def _apply_hashtag_response(shipment, response: dict):
	tracking_number = _get_response_value(response, "tracking_number", "awb_number", "awb", "data.tracking_number", "data.awb_number", "data.awb")
	shipment_id = _get_response_value(response, "shipment_id", "id", "data.shipment_id", "data.id")
	status = _get_response_value(response, "status", "shipment_status", "data.status", "data.shipment_status") or "Created"
	label_url = _get_response_value(response, "label_url", "tracking_url", "data.label_url", "data.tracking_url")

	shipment.hashtag_shipment_created = 1
	shipment.hashtag_shipment_id = shipment_id
	shipment.hashtag_tracking_number = tracking_number
	shipment.hashtag_status = status
	shipment.hashtag_label_url = label_url
	shipment.hashtag_last_sync = frappe.utils.now_datetime()
	shipment.hashtag_api_response = json.dumps(response, ensure_ascii=False, indent=2, default=str)

	if shipment_id and not shipment.shipment_id:
		shipment.shipment_id = shipment_id
	if tracking_number and not shipment.awb_number:
		shipment.awb_number = tracking_number
	if label_url and not shipment.tracking_url:
		shipment.tracking_url = label_url
	if status and frappe.get_meta("Shipment").get_field("tracking_status"):
		tracking_status_field = frappe.get_meta("Shipment").get_field("tracking_status")
		options = [option.strip() for option in (tracking_status_field.options or "").split("\n") if option.strip()]
		if not options or status in options:
			shipment.tracking_status = status


@frappe.whitelist()
def sync_hashtag_status(shipment_name: str):
	shipment = frappe.get_doc("Shipment", shipment_name)
	client = HashtagClient()
	path = client.settings.tracking_path
	if not path:
		frappe.throw(_("Tracking Path is not configured in Hashtag Settings."))
	path = path.format(
		shipment_id=shipment.get("hashtag_shipment_id") or shipment.get("shipment_id") or "",
		tracking_number=shipment.get("hashtag_tracking_number") or shipment.get("awb_number") or "",
	)
	response = client.get(path)
	_apply_hashtag_response(shipment, response)
	shipment.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": shipment.get("hashtag_status"), "response": response}
