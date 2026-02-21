import frappe
from frappe import _
from liseniq.utils.login_util import global_website_context


def get_context(context):

    if frappe.session.user == "Guest":
        frappe.throw(_("Cliente aún no ha sido registrado. Por favor comunique al Administrador."), frappe.PermissionError)

    context = global_website_context(context)

    # Configuración base de la página
    context.page_title = _("Crear Plantilla")
    context.no_breadcrumbs = True
    context.is_navbar_custom = True
    context.no_cache = 1

    try:
        # contact_info = frappe.db.get_value("Contact", {"user": frappe.session.user}, "custom_company")
        contact_info = frappe.db.get_value("Contact", {"user": frappe.session.user, "custom_is_liseniq_contact": 0}, "custom_company")
        if not contact_info:
            frappe.throw("El usuario actual no tiene una compañía asignada. Por favor, contacte al administrador.")
        context.user_company = contact_info
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error obteniendo la compañía del usuario")
        frappe.throw(str(e))

    try:
        question_categories = frappe.get_all(
            "qp_IQ_QuestionCategory",
            fields=["name", "qnc_category"],
            order_by="qnc_category",
            ignore_permissions=True
        )
        context.question_categories = question_categories
    except frappe.DoesNotExistError:
        context.question_categories = []

    try:
        # Filtramos estrictamente por los mnemónicos
        question_types = frappe.get_all(
            "qp_IQ_QuestionType",
            filters={
                "qnt_mnemonico": ["in", ["text_area", "text_short", "check_group", "scale_likert", "scale_emoji", "score_nps", "radio_group"]]
            },
            fields=["name", "qnt_type_name", "qnt_mnemonico"],
            order_by="qnt_type_name",
            ignore_permissions=True
        )
        context.question_types = question_types
    except frappe.DoesNotExistError:
        context.question_types = []

    return context

@frappe.whitelist()
def check_template_name(name):
    exists = frappe.db.exists("qp_IQ_Template", {"tp_name": name})
    return {"exists": bool(exists)}