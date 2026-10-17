import frappe
import re
import unicodedata
from frappe import _
from liseniq.utils.login_util import global_website_context, get_current_active_company


def _normalize_demographic_title(text):
    """
    Normaliza el título de un Tema o Dimensión para comparaciones insensibles a:
    - Mayúsculas y minúsculas
    - Acentos, tildes y diéresis (NFKD)
    - Caracteres especiales, signos de puntuación y espacios múltiples
    """
    if not text:
        return ""
    text_str = str(text).strip()
    no_accents = "".join(
        c for c in unicodedata.normalize("NFKD", text_str)
        if unicodedata.category(c) != "Mn"
    )
    cleaned = re.sub(r"[^a-z0-9]+", " ", no_accents.lower()).strip()
    return cleaned or text_str.lower()


def _get_or_create_demographic_type(raw_value, object_type, user_company=None):
    """
    Valida si ya existe un Tema o Dimensión en qp_IQ_DemographicType (dt_title)
    indiferentemente de la compañía creadora (dt_creator_company), ignorando
    acentos, mayúsculas/minúsculas y caracteres especiales.
    Si existe, retorna su 'name'; si no existe, lo crea sin compañía asociada
    (compartido entre empresas) y retorna el nuevo 'name'.
    """
    if not raw_value or not str(raw_value).strip():
        return None

    clean_raw = str(raw_value).strip()
    norm_obj_type = _normalize_demographic_title(object_type)
    allowed_norm_types = ("dimension", "pregunta") if norm_obj_type == "dimension" else (norm_obj_type,)

    # Si el valor recibido es un ID (name) existente de qp_IQ_DemographicType, resolver su dt_title
    by_id = frappe.db.sql(
        """
        SELECT name, dt_title, dt_object_type
        FROM `tabqp_IQ_DemographicType`
        WHERE name = %s
        LIMIT 1
        """,
        (clean_raw,),
        as_dict=True
    )
    if by_id and _normalize_demographic_title(by_id[0].get("dt_object_type")) in allowed_norm_types:
        if by_id[0].get("dt_title"):
            clean_raw = by_id[0].get("dt_title").strip()
        else:
            return by_id[0].name

    normalized_target = _normalize_demographic_title(clean_raw)
    if not normalized_target:
        return None

    # Consultar todos los registros sin filtrar por compañía ni depender de colación en dt_object_type
    candidates = frappe.db.sql(
        """
        SELECT name, dt_title, dt_object_type
        FROM `tabqp_IQ_DemographicType`
        WHERE dt_title IS NOT NULL
          AND dt_title != ''
        ORDER BY creation ASC
        """,
        as_dict=True
    )

    # Priorizar coincidencia exacta de tipo ('dimension' o 'tema') sobre 'pregunta'
    candidates.sort(
        key=lambda r: 0 if _normalize_demographic_title(r.get("dt_object_type")) == norm_obj_type else 1
    )

    for rec in candidates:
        rec_type_norm = _normalize_demographic_title(rec.get("dt_object_type"))
        if rec_type_norm in allowed_norm_types:
            if _normalize_demographic_title(rec.get("dt_title")) == normalized_target:
                return rec.name

    # Si no existe coincidencia normalizada, crear el nuevo registro compartido (sin dt_creator_company para Dimension/Tema)
    new_doc = frappe.new_doc("qp_IQ_DemographicType")
    new_doc.dt_title = clean_raw
    new_doc.dt_object_type = object_type
    if norm_obj_type not in ("dimension", "tema") and user_company:
        new_doc.dt_creator_company = user_company
    new_doc.insert(ignore_permissions=True)
    return new_doc.name

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
def get_user_contact_id():
    contact_name = frappe.db.get_value("Contact", {"user": frappe.session.user}, "name")
    
    if not contact_name:
        frappe.throw(_("No se encontró un perfil de Contacto asociado a tu usuario. Por favor, contacta al administrador del sistema."))
        
    return contact_name

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
    user_company = get_current_active_company()
    
    # Actualizar campos directos
    if "qn_statement" in data:
        doc.qn_statement = data.get("qn_statement")
    if "qn_type" in data:
        doc.qn_type = data.get("qn_type")
    if "qn_statement_others" in data:
        doc.qn_statement_others = data.get("qn_statement_others")
    if "qp_others" in data:
        doc.qp_others = data.get("qp_others")
    if "qp_none_above" in data:
        doc.qp_none_above = data.get("qp_none_above")
    if "qn_nps_min" in data:
        doc.qn_nps_min = data.get("qn_nps_min")
    if "qn_nps_max" in data:
        doc.qn_nps_max = data.get("qn_nps_max")
    if "qn_optional" in data:
        doc.qn_optional = data.get("qn_optional")

    # Actualizar opciones de respuesta si vienen
    if "qn_response_options" in data:
        doc.set("qn_response_options", [])
        options = data.get("qn_response_options", [])
        for opt in options:
            doc.append("qn_response_options", {
                "qo_option_text": opt.get("qo_option_text"),
                "qo_option_value": opt.get("qo_option_value"),
                "qo_url": opt.get("qo_url")
            })
        
    # Validar o crear el demográfico (Dimensión) dinámicamente sin duplicar entre empresas
    if "qn_demographic" in data:
        demographic_title = data.get("qn_demographic")
        doc.qn_demographic = (
            _get_or_create_demographic_type(demographic_title, "Dimension", user_company)
            if demographic_title else None
        )

    # Validar o crear Cultura (Tema) dinámicamente sin duplicar entre empresas
    if "qp_topic" in data or "culture" in data:
        culture_title = data.get("qp_topic") or data.get("culture")
        doc.qp_topic = (
            _get_or_create_demographic_type(culture_title, "Tema", user_company)
            if culture_title else None
        )
        
    doc.save(ignore_permissions=True)
    return {"status": "success"}