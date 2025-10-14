import frappe
from frappe import _


def get_context(context):

    if frappe.session.user == "Guest":
        frappe.throw(_("Cliente aún no ha sido registrado. Por favor comunique al Administrador."), frappe.PermissionError)

    context.page_title = "Crear Plantilla"

    try:
        contact_info = frappe.db.get_value("Contact", {"user": frappe.session.user}, "custom_company")
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
        allowed_question_types = ["Likert", "Abierta", "NPS", "Selección Múltiple"]
        question_types = frappe.get_all(
            "qp_IQ_QuestionType",
            filters={"qnt_type_name": ["in", allowed_question_types]},
            fields=["name", "qnt_type_name"],
            order_by="qnt_type_name",
            ignore_permissions=True
        )
        context.question_types = question_types
    except frappe.DoesNotExistError:
        context.question_types = []

    context.update({
        "is_navbar_custom": True,
        "no_cache": 1,
    })

    return context

@frappe.whitelist()
def check_template_name(name):
    exists = frappe.db.exists("qp_IQ_Template", {"tp_name": name})
    return {"exists": bool(exists)}
