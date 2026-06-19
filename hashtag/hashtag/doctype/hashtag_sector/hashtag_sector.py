from frappe.model.document import Document


class HashtagSector(Document):
	def before_save(self):
		self.sector_label = self.build_sector_label()

	def build_sector_label(self):
		parts = [self.sector_name]
		if self.alias:
			parts.append(self.alias)
		if self.gov_name:
			parts.append(f"({self.gov_name})")
		return " - ".join(part for part in parts if part)
