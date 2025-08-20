import frappe
from liseniq.hooks import login_required

@login_required
def get_context(context):
    context.page_title = "Crear Plantilla"

    try:
        user_company = frappe.db.get_value("User", frappe.session.user, "custom_company")
        if not user_company:
            frappe.throw("El usuario actual no tiene una compañía asignada. Por favor, contacte al administrador.")
        context.user_company = user_company
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error obteniendo la compañía del usuario")
        frappe.throw(str(e))

    try:
        question_categories = frappe.get_all(
            "qp_IQ_QuestionCategory",
            fields=["name", "qnc_category"],
            order_by="qnc_category"
        )
        context.question_categories = question_categories
    except frappe.DoesNotExistError:
        context.question_categories = []

    try:
        question_types = frappe.get_all(
            "qp_IQ_QuestionType",
            fields=["name", "qnt_type_name"],
            order_by="qnt_type_name"
        )
        context.question_types = question_types
    except frappe.DoesNotExistError:
        context.question_types = []

    context.update({
        "is_navbar_custom": True,
        "no_cache": 1
    })
            
    return context
