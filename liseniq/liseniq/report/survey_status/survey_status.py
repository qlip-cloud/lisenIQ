# Copyright (c) 2013, Mentum Group and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data


def get_columns(filters):
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
    ]
    if filters and filters.get("demographic1"):
        dem = frappe.get_value(
            "qp_IQ_DemographicType", filters.get("demographic1"), "dt_title"
        )
        columns.append(
            {
                "fieldname": "demographic1",
                "label": dem or "Demográfico 1",
                "fieldtype": "Data",
                "width": 150,
            }
        )
    if filters and filters.get("demographic2"):
        dem = frappe.get_value(
            "qp_IQ_DemographicType", filters.get("demographic2"), "dt_title"
        )
        columns.append(
            {
                "fieldname": "demographic2",
                "label": dem or "Demográfico 2",
                "fieldtype": "Data",
                "width": 150,
            }
        )

    columns += [
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
        },
    ]
    return columns


def get_data(filters):
    rs_responded = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Responded"}, "name") or "Responded"
    demographic1 = filters.get("demographic1")
    demographic2 = filters.get("demographic2")

    joins = ""
    select_extra = ""
    group_extra = ""

    if demographic1:
        joins += f"""
            LEFT JOIN `tabqp_IQ_ContactAdditionalDetail` cad1 
                ON cad1.parent = c.name 
                AND cad1.cad_demographic_type = '{demographic1}'
        """
        select_extra += ", cad1.cad_value AS demographic1"
        group_extra += ", cad1.cad_value"

    if demographic2:
        joins += f"""
            LEFT JOIN `tabqp_IQ_ContactAdditionalDetail` cad2 
                ON cad2.parent = c.name 
                AND cad2.cad_demographic_type = '{demographic2}'
        """
        select_extra += ", cad2.cad_value AS demographic2"
        group_extra += ", cad2.cad_value"

    conditions = []
    if filters.get("company"):
        conditions.append("s.su_owner = %(company)s")
    if filters.get("survey"):
        conditions.append("s.name = %(survey)s")

    where_clause = "WHERE 1=1" + (
        " AND " + " AND ".join(conditions) if conditions else ""
    )

    query = f"""
        SELECT
            s.su_name AS name,
            co.co_name AS company
            {select_extra},
            COUNT(DISTINCT srp.name) AS expected_responses,
            COUNT(DISTINCT 
                CASE WHEN srp.sr_status = '{rs_responded}' THEN srp.name END
            ) AS received_responses,
            (
                COUNT(DISTINCT srp.name) -
                COUNT(DISTINCT CASE WHEN srp.sr_status = '{rs_responded}' THEN srp.name END)
            ) AS pending_responses
        FROM `tabqp_IQ_Survey` s
        LEFT JOIN `tabqp_IQ_Company` co ON co.name = s.su_owner
        LEFT JOIN `tabqp_IQ_SurveyRecipient` srp 
            ON srp.sr_survey = s.name
        LEFT JOIN `tabContact` c 
            ON c.name = srp.sr_contact
        {joins}
        {where_clause}
        GROUP BY s.su_name, s.su_owner {group_extra}
        ORDER BY co.co_name, s.su_name {group_extra}
    """

    return frappe.db.sql(query, filters or {}, as_dict=True)
