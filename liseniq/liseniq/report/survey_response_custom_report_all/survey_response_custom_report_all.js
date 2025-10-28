// Copyright (c) 2016, Mentum Group and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Survey Response Custom Report All"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"hidden": 1,
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 0
		}
	]
};
