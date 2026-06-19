frappe.ui.form.on("Address", {
	setup(frm) {
		frm.set_query("city", () => {
			return {
				filters: {
					enabled: 1,
				},
			};
		});
	},

	refresh(frm) {
		hide_hashtag_address_fields(frm);
	},

	city(frm) {
		apply_hashtag_sector(frm);
	},

	validate(frm) {
		if ((frm.doc.country || "") === "Egypt" && !frm.doc.hashtag_sector_id) {
			frappe.throw(__("Select City/Town from the Hashtag Sector dropdown."));
		}
	},
});

const hashtag_address_fields = [
	"hashtag_section",
	"hashtag_gov_id",
	"hashtag_gov_name",
	"hashtag_sector_id",
	"hashtag_sector_name",
	"hashtag_keyword",
];

function hide_hashtag_address_fields(frm) {
	hashtag_address_fields.forEach((fieldname) => {
		if (frm.fields_dict[fieldname]) {
			frm.toggle_display(fieldname, false);
		}
	});
}

function apply_hashtag_sector(frm) {
	if (!frm.doc.city) {
		clear_hashtag_sector(frm);
		return;
	}

	frappe.db.get_doc("Hashtag Sector", frm.doc.city).then((sector) => {
		frm.set_value("hashtag_gov_id", sector.gov_id || "");
		frm.set_value("hashtag_gov_name", sector.gov_name || "");
		frm.set_value("hashtag_sector_id", sector.sector_id || sector.name);
		frm.set_value("hashtag_sector_name", sector.sector_name || "");
		frm.set_value("hashtag_keyword", sector.keyword || "");
		frm.set_value("state", sector.gov_name || "");
		frm.set_value("country", "Egypt");
	});
}

function clear_hashtag_sector(frm) {
	frm.set_value("hashtag_gov_id", "");
	frm.set_value("hashtag_gov_name", "");
	frm.set_value("hashtag_sector_id", "");
	frm.set_value("hashtag_sector_name", "");
	frm.set_value("hashtag_keyword", "");
}
