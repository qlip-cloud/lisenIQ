// Copyright (c) 2016, Mentum Group and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Survey Status"] = {
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
		},
		{
			"fieldname": "demographic1",
			"label": "Demográfico 1",
			"fieldtype": "Link",
			"options": "qp_IQ_DemographicType",
			"get_query": () => ({ filters: { dt_object_type: "Contacto" } }),
			"reqd": 0,
		},
		{
			"fieldname": "demographic2",
			"label": "Demográfico 2",
			"fieldtype": "Link",
			"options": "qp_IQ_DemographicType",
			"get_query": () => ({ filters: { dt_object_type: "Contacto" } }),
			"reqd": 0
		}
	]
};
