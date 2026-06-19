frappe.ui.form.on("Shipment", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus === 2) {
			return;
		}

		if (!frm.doc.hashtag_shipment_created) {
			frm.add_custom_button(__("Create Hashtag Shipment"), () => {
				frappe.confirm(
					__("Create this shipment in Hashtag now?"),
					() => frm.call({
						method: "hashtag.integrations.hashtag_shipment.create_hashtag_shipment",
						args: { shipment_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Creating Hashtag Shipment..."),
						callback(response) {
							frm.reload_doc();
							const data = response.message || {};
							frappe.msgprint({
								title: __("Hashtag Shipment Created"),
								indicator: "green",
								message: __("Tracking Number: {0}", [data.tracking_number || data.shipment_id || __("Created")]),
							});
						},
					}),
				);
			}, __("Hashtag"));
		} else {
			frm.add_custom_button(__("Sync Hashtag Status"), () => {
				frm.call({
					method: "hashtag.integrations.hashtag_shipment.sync_hashtag_status",
					args: { shipment_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Syncing Hashtag status..."),
					callback(response) {
						frm.reload_doc();
						const data = response.message || {};
						frappe.show_alert({ message: __("Hashtag status: {0}", [data.status || __("Updated")]), indicator: "green" });
					},
				});
			}, __("Hashtag"));
		}
	},
});
