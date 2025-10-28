// Copyright (c) 2016, Mentum Group and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Survey Response Custom Report"] = {
	"filters": [
		{
			"fieldname": "survey",
			"label": __("Survey"),
			"fieldtype": "Link",
			"options": "Survey",
			"reqd": 1
		},
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
