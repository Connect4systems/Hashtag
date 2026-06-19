frappe.ui.form.on("Address", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Select Hashtag Area"), () => {
			open_hashtag_area_dialog(frm);
		}, __("Hashtag"));
	},
});

function open_hashtag_area_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Select Hashtag Area"),
		fields: [
			{
				fieldname: "government",
				fieldtype: "Autocomplete",
				label: __("Government"),
				reqd: 1,
				options: [],
				change() {
					const government = dialog.get_value("government");
					const gov = (dialog.hashtag_governments || []).find((row) => format_area(row) === government);
					dialog.set_value("sector", "");
					dialog.fields_dict.sector.set_data([]);
					if (gov) {
						load_hashtag_sectors(dialog, gov.id);
					}
				},
			},
			{
				fieldname: "sector",
				fieldtype: "Autocomplete",
				label: __("Sector"),
				reqd: 1,
				options: [],
			},
		],
		primary_action_label: __("Apply"),
		primary_action() {
			const gov = (dialog.hashtag_governments || []).find((row) => format_area(row) === dialog.get_value("government"));
			const sector = (dialog.hashtag_sectors || []).find((row) => format_area(row) === dialog.get_value("sector"));
			if (!gov || !sector) {
				frappe.throw(__("Select a government and sector."));
			}

			frm.set_value("hashtag_gov_id", gov.id);
			frm.set_value("hashtag_gov_name", gov.name);
			frm.set_value("hashtag_sector_id", sector.id);
			frm.set_value("hashtag_sector_name", sector.name);
			frm.set_value("hashtag_keyword", sector.key_words || "");
			dialog.hide();
		},
	});

	dialog.show();
	load_hashtag_governments(dialog);
}

function load_hashtag_governments(dialog) {
	frappe.call({
		method: "hashtag.integrations.hashtag_shipment.get_hashtag_governments",
		freeze: true,
		freeze_message: __("Loading Hashtag governments..."),
		callback(response) {
			dialog.hashtag_governments = get_response_rows(response.message);
			dialog.fields_dict.government.set_data(dialog.hashtag_governments.map(format_area));
		},
	});
}

function load_hashtag_sectors(dialog, gov_id) {
	frappe.call({
		method: "hashtag.integrations.hashtag_shipment.get_hashtag_sectors",
		args: { gov_id },
		freeze: true,
		freeze_message: __("Loading Hashtag sectors..."),
		callback(response) {
			dialog.hashtag_sectors = get_response_rows(response.message);
			dialog.fields_dict.sector.set_data(dialog.hashtag_sectors.map(format_area));
		},
	});
}

function get_response_rows(message) {
	if (Array.isArray(message)) {
		return message;
	}
	if (message && Array.isArray(message.response)) {
		return message.response;
	}
	if (message && Array.isArray(message.data)) {
		return message.data;
	}
	return [];
}

function format_area(row) {
	return `${row.id} - ${row.name}${row.gov_name ? ` (${row.gov_name})` : ""}`;
}
