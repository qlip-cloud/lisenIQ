import frappe
from frappe import _


def get_context(context):
    context.page_title = "Medición"
    context.no_breadcrumbs = True
    context.is_navbar_custom = True
    context.no_cache = 1

    token = frappe.form_dict.get("token")
    survey_name = ""
    if token:
        survey = frappe.db.get_value("qp_IQ_Survey", {"su_public_token": token}, "su_name")
        if survey:
            survey_name = survey
    context.survey_name = survey_name or ""

    return context