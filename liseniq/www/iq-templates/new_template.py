import frappe
from frappe import _
from liseniq.utils.login_util import global_website_context, get_current_active_company


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
        user_company = get_current_active_company()
        if not user_company:
            frappe.throw("El usuario actual no tiene una compañía activa asignada. Por favor, contacte al administrador.")
        context.user_company = user_company
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error obteniendo la compañía del usuario")
        frappe.throw(str(e))

    try:
        question_categories = frappe.get_all(
            "qp_IQ_TemplateCategory",
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

@frappe.whitelist()
def get_template_details(template_name):
    if not template_name:
        return None
    doc = frappe.get_doc("qp_IQ_Template", template_name)
    return {
        "tp_name": doc.tp_name,
        "tp_category": doc.tp_category,
        "tp_description": doc.tp_description,
        "tp_is_private": doc.tp_is_private,
        "tp_is_public": doc.tp_is_public
    }

@frappe.whitelist()
def update_template_questions(template_name, new_questions):
    questions = frappe.parse_json(new_questions)
    doc = frappe.get_doc("qp_IQ_Template", template_name)
    
    # Limpiar tabla hija
    doc.set("tp_questions", [])
    
    # Insertar nuevas preguntas preservando el orden
    for q_name in questions:
        doc.append("tp_questions", {"tq_question": q_name})
        
    doc.save(ignore_permissions=True)
    return {"status": "success"}

@frappe.whitelist()
def update_template_question(question_name, question_data):
    data = frappe.parse_json(question_data)
    doc = frappe.get_doc("qp_IQ_Question", question_name)
    
    # Actualizar campos directos
    if "qn_statement" in data:
        doc.qn_statement = data.get("qn_statement")
    if "qn_type" in data:
        doc.qn_type = data.get("qn_type")
    if "qn_statement_others" in data:
        doc.qn_statement_others = data.get("qn_statement_others")
        
    # Validar o crear el demográfico dinámicamente
    demographic_title = data.get("qn_demographic")
    if demographic_title:
        demographic_name = frappe.db.exists(
            "qp_IQ_DemographicType",
            {"dt_title": demographic_title, "dt_object_type": "Pregunta"}
        )
        if not demographic_name:
            demographic_doc = frappe.new_doc("qp_IQ_DemographicType")
            demographic_doc.dt_title = demographic_title
            demographic_doc.dt_object_type = "Pregunta"
            demographic_doc.insert(ignore_permissions=True)
            demographic_name = demographic_doc.name
        
        doc.qn_demographic = demographic_name

    # Validar o crear Cultura dinámicamente
    culture_title = data.get("qp_topic")
    if culture_title:
        culture_name = frappe.db.exists(
            "qp_IQ_DemographicType",
            {"dt_title": culture_title, "dt_object_type": "Tema"}
        )
        if not culture_name:
            culture_doc = frappe.new_doc("qp_IQ_DemographicType")
            culture_doc.dt_title = culture_title
            culture_doc.dt_object_type = "Tema"
            user_company = get_current_active_company()
            if user_company:
                culture_doc.dt_creator_company = user_company
            culture_doc.insert(ignore_permissions=True)
            culture_name = culture_doc.name
        
        doc.qp_topic = culture_name
        
    doc.save(ignore_permissions=True)
    return {"status": "success"}