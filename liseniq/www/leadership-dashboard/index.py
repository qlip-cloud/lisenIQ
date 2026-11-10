import frappe
from urllib.parse import quote

from liseniq.api.leadership_dashboard import ALLOW_GUEST, SURVEY_DOCTYPE

no_cache = 1


def get_context(context):
    survey = frappe.form_dict.get("survey")
    survey_title = frappe.form_dict.get("survey_title")
    if not survey:
        frappe.throw("Falta el parámetro 'survey' en la URL", frappe.ValidationError)

    if not ALLOW_GUEST and frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=" + quote(
            "/liderazgo-dashboard?survey=" + survey_title)
        raise frappe.Redirect

    if not frappe.db.exists(SURVEY_DOCTYPE, survey_title):
        frappe.throw("Medición no encontrada: %s" % survey_title, frappe.DoesNotExistError)

    context.survey = survey_title
    context.no_header = 1
    context.title = "Dashboard Liderazgo 360° — %s" % survey_title
