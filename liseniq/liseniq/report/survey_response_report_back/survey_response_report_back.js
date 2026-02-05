// Copyright (c) 2016, Mentum Group and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Survey Response Report Back"] = {
	"filters": [
		{
			"fieldname": "survey",
			"label": __("Survey"),
			"fieldtype": "Link",
			"options": "Survey",
			"reqd": 1
		}
	]
};