// Copyright (c) 2016, Mentum Group and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Survey Response Custom Report All"] = {
	"filters": [
		{
			"fieldname": "company",
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
			"get_data": function(txt) {
        return frappe.db.get_link_options("qp_IQ_Survey", txt, "survey_name");
    	}
		}
	]
};
