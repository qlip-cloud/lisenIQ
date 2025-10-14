# Copyright (c) 2013, Mentum Group and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data

def get_columns():
	columns = [
		{
			"fieldname": "name",
			"label": "Nombre Medición",
			"fieldtype": "Link",
			"options": "qp_IQ_Survey",
			"width": 200,
		},
		{
			"fieldname": "company",
			"label": "Compañía",
			"fieldtype": "Link",
			"options": "qp_IQ_Company",
			"width": 200,
		},
		{
			"fieldname": "expected_responses",
			"label": "Respuestas Esperadas",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"fieldname": "received_responses",
			"label": "Respuestas Recibidas",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"fieldname": "pending_responses",
			"label": "Respuestas Pendientes",
			"fieldtype": "Int",
			"width": 100,
		}
	]
	return columns


def get_data(filters):
    query = """
        SELECT
            s.su_name AS name,
            co.co_name AS company,
            COUNT(DISTINCT c.name) AS expected_responses,
            COUNT(DISTINCT sr.name) AS received_responses,
            (COUNT(DISTINCT c.name) - COUNT(DISTINCT sr.name)) AS pending_responses
        FROM `tabqp_IQ_Survey` s
        LEFT JOIN `tabContact` c ON c.custom_company = s.su_owner
        LEFT JOIN `tabSurvey Response` sr ON sr.survey = s.su_name AND sr.user = c.name
        LEFT JOIN `tabqp_IQ_Company` co ON co.name = s.su_owner
        {conditions}
        GROUP BY s.su_name, s.su_owner
        ORDER BY s.su_owner, s.su_name
    """

    conditions = []
    if filters and filters.get("company"):
      conditions.append("s.su_owner = %(company)s")
    if filters and filters.get("survey"):
        conditions.append("s.su_name = %(survey)s")

    query = query.format(conditions=("WHERE " + " AND ".join(conditions)) if conditions else "")

    return frappe.db.sql(query, filters or {}, as_dict=True)

