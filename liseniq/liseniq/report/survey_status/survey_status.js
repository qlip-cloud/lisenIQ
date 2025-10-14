// Copyright (c) 2016, Mentum Group and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Survey Status"] = {
	"filters": [
		{
			"fieldname": su_owner,
			"label": "Compañía",
			"fieldtype": "Link",
			"options": "qp_IQ_Company",
			"reqd": 0,
		},
		{
			"fieldname": "survey",
			"label": "Medición",
			"fieldtype": "Link",
			"options": "qp_IQ_Survey",
			"reqd": 0,
		}
	]
};
