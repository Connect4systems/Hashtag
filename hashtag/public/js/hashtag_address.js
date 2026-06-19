frappe.ui.form.on("Address", {
	setup(frm) {
		frm.set_df_property("city", "fieldtype", "Autocomplete");
		frm.set_df_property("city", "description", __("Search and select a Hashtag delivery area."));
	},

	refresh(frm) {
		setup_hashtag_city_search(frm);
	},

	city(frm) {
		apply_selected_hashtag_city(frm);
	},

	validate(frm) {
		if ((frm.doc.country || "") === "Egypt" && !frm.doc.hashtag_sector_id) {
			frappe.throw(__("Select City/Town from the Hashtag delivery area list."));
		}
	},
});

function setup_hashtag_city_search(frm) {
	const city_field = frm.fields_dict.city;
	if (!city_field) {
		return;
	}

	city_field.get_query = (txt) => {
		return frappe.call({
			method: "hashtag.integrations.hashtag_shipment.search_hashtag_sectors",
			args: { txt: txt || "" },
		}).then((response) => {
			frm.hashtag_sector_options = get_response_rows(response.message);
			return frm.hashtag_sector_options.map(format_sector_option);
		});
	};

	if (city_field.$input) {
		city_field.$input.off(".hashtag");
		city_field.$input.on("focus.hashtag", () => refresh_city_options(frm, city_field.$input.val() || ""));
		city_field.$input.on("input.hashtag", frappe.utils.debounce(() => {
			refresh_city_options(frm, city_field.$input.val() || "");
		}, 250));
	}
}

function refresh_city_options(frm, txt) {
	frappe.call({
		method: "hashtag.integrations.hashtag_shipment.search_hashtag_sectors",
		args: { txt: txt || "" },
		callback(response) {
			frm.hashtag_sector_options = get_response_rows(response.message);
			if (frm.fields_dict.city && frm.fields_dict.city.set_data) {
				frm.fields_dict.city.set_data(frm.hashtag_sector_options.map(format_sector_option));
			}
		},
	});
}

function apply_selected_hashtag_city(frm) {
	const value = frm.doc.city || "";
	const sector = find_selected_sector(frm, value);
	if (!sector) {
		if (frm.doc.hashtag_sector_id && value !== frm.doc.hashtag_sector_name) {
			frm.set_value("hashtag_gov_id", "");
			frm.set_value("hashtag_gov_name", "");
			frm.set_value("hashtag_sector_id", "");
			frm.set_value("hashtag_sector_name", "");
			frm.set_value("hashtag_keyword", "");
		}
		return;
	}

	frm.set_value("hashtag_gov_id", sector.gov_id || "");
	frm.set_value("hashtag_gov_name", sector.gov_name || "");
	frm.set_value("hashtag_sector_id", sector.id || "");
	frm.set_value("hashtag_sector_name", sector.name || "");
	frm.set_value("hashtag_keyword", sector.key_words || "");
	frm.set_value("state", sector.gov_name || "");
	frm.set_value("country", "Egypt");

	if (value !== sector.name) {
		frm.set_value("city", sector.name);
	}
}

function find_selected_sector(frm, value) {
	const id = String(value).split(" - ")[0];
	return (frm.hashtag_sector_options || []).find((row) => {
		return String(row.id) === id || row.name === value || format_sector_option(row) === value;
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

function format_sector_option(row) {
	const alias = row.alias ? ` - ${row.alias}` : "";
	return `${row.id} - ${row.name}${alias}${row.gov_name ? ` (${row.gov_name})` : ""}`;
}
