import frappe
import json
from frappe import _


def get_context(context):

    if frappe.session.user == "Guest":
        frappe.throw(_("Cliente aún no ha sido registrado. Por favor comunique al Administrador."), frappe.PermissionError)

    context.page_title = "Plantillas"
    context.no_breadcrumbs = True
    context.is_navbar_custom = True
    context.no_cache = 1

    user_contact_info = frappe.db.get_value("Contact", {"user": frappe.session.user, "custom_is_liseniq_contact": 0}, "custom_company")
    if not user_contact_info:
        frappe.throw("El usuario actual no tiene una compañía asignada. Por favor, contacte al administrador.")
    user_company = user_contact_info

    # Obtener plantillas públicas (visibles para todos)
    templates_public = frappe.get_list(
        "qp_IQ_Template",
        filters=[['tp_is_public', '=', 1]],
        fields=["name", "tp_name", "tp_description", "tp_category", "tp_owner", "tp_is_private", "tp_is_public"],
        order_by="creation desc",
        ignore_permissions=True
    )

    # Obtener plantillas de la compañía del usuario (públicas y privadas del usuario)
    templates_company_scoped = frappe.get_list(
        "qp_IQ_Template",
        filters=[['custom_company', '=', user_company]],
        or_filters=[
            ['tp_is_private', '=', 0],
            ['tp_owner', '=', frappe.session.user]
        ],
        fields=["name", "tp_name", "tp_description", "tp_category", "tp_owner", "tp_is_private", "tp_is_public"],
        order_by="creation desc",
        ignore_permissions=True
    )

    # Agregar y deduplicar por nombre
    templates_from_db = []
    seen = set()
    for t in templates_public + templates_company_scoped:
        if t.name in seen:
            continue
        seen.add(t.name)
        templates_from_db.append(t)
    
    processed_templates = []
    for template_data in templates_from_db:
        try:
            doc = frappe.get_doc("qp_IQ_Template", template_data.name)
            questions_count = len(doc.get("tp_questions", []))
            
            category_name = frappe.db.get_value(
                "qp_IQ_QuestionCategory",
                template_data.tp_category,
                "qnc_category"
            ) if template_data.tp_category else "Sin categoría"

            template_data["questions_count"] = questions_count
            template_data["category_name"] = category_name

            attachment = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "qp_IQ_Template",
                    "attached_to_name": template_data.name,
                    "is_folder": 0,
                },
                fields=["file_url"],
                limit=1,
            )
            
            template_data["tp_logo_url"] = attachment[0].file_url if attachment else None
            processed_templates.append(template_data)
        
        except frappe.DoesNotExistError:
            frappe.log_error(
                f"No se pudo encontrar el documento de la plantilla: {template_data.name}",
                "Error en index.py de IQ Templates"
            )

    context.templates = processed_templates

    try:
        categories_from_db = frappe.get_all(
            "qp_IQ_QuestionCategory",
            fields=["name", "qnc_category", "qnc_is_popular"],
            order_by="qnc_category",
            ignore_permissions=True
        )
        context.categories = categories_from_db
    except frappe.DoesNotExistError:
        context.categories = []
            
    return context

@frappe.whitelist()
def get_questions_from_template(template_name):
    frappe.has_permission("qp_IQ_Template", "read", doc=template_name)
    
    template_doc = frappe.get_doc("qp_IQ_Template", template_name)
    questions = []

    if not template_doc.tp_questions:
        return []

    for tq in template_doc.tp_questions:
        q_doc = frappe.get_doc("qp_IQ_Question", tq.tq_question)
        
        type_name = frappe.db.get_value("qp_IQ_QuestionType", q_doc.qn_type, "qnt_type_name") if q_doc.qn_type else "No definido"
        demographic_name = frappe.db.get_value("qp_IQ_DemographicType", q_doc.qn_demographic, "dt_title") if q_doc.qn_demographic else None

        question_data = {
            "id": q_doc.name,
            "text": q_doc.qn_statement,
            "type": q_doc.qn_type,
            "typeName": type_name,
            "demographic": demographic_name,
            "negative_statement": q_doc.qn_negative_statement,
            "positive_statement": q_doc.qn_positive_statement,
            "nps_min": q_doc.qn_nps_min,
            "nps_max": q_doc.qn_nps_max,
            "options": []
        }

        if q_doc.qn_response_options:
            if type_name == "Likert":
                options = [
                    {
                        "text": opt.qo_option_text,
                        "value": opt.qo_option_value,
                        "url": getattr(opt, "qo_url", None)
                    }
                    for opt in q_doc.qn_response_options
                ]
            elif type_name == "Likert Visual":
                options = [
                    {"text": opt.qo_option_text, "value": opt.qo_option_value, "url": opt.qo_url}
                    for opt in q_doc.qn_response_options
                ]
            else:
                options = [opt.qo_option_text for opt in q_doc.qn_response_options]
            question_data["options"] = options
        
        questions.append(question_data)
        
    return questions


@frappe.whitelist()
def get_demographic_suggestions_for_questions(search_term):
    if not search_term:
        return []

    return frappe.get_all(
        "qp_IQ_DemographicType",
        filters={
            'dt_title': ['like', f'%{search_term}%'],
            'dt_object_type': 'Pregunta'
        },
        fields=['dt_title'],
        limit=10,
        ignore_permissions=True
    )

@frappe.whitelist()
def create_question_from_template_wizard(question_data):
    try:
        data = frappe.parse_json(question_data)
        
        user_contact = frappe.db.get_value("Contact", {"user": frappe.session.user, "custom_is_liseniq_contact": 0}, "name")
        user_company = frappe.db.get_value("Contact", {"user": frappe.session.user, "custom_is_liseniq_contact": 0}, "custom_company")

        if not user_contact or not user_company:
            frappe.throw("No se pudo encontrar el contacto o la compañía para el usuario actual.")

        question_doc = frappe.new_doc("qp_IQ_Question")
        
        question_doc.qn_statement = data.get("qn_statement")
        question_doc.qn_type = data.get("qn_type")
        question_doc.qn_category = data.get("qn_category")
        question_doc.qn_status = data.get("qn_status", "Activa")
        question_doc.qn_negative_statement = data.get("qn_negative_statement")
        question_doc.qn_positive_statement = data.get("qn_positive_statement")
        question_doc.qn_creator = user_contact
        question_doc.qn_owner = user_company
        
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
            
            question_doc.qn_demographic = demographic_name

        nps_min = data.get("qn_nps_min")
        if nps_min is not None and nps_min != '':
            question_doc.qn_nps_min = int(nps_min)

        nps_max = data.get("qn_nps_max")
        if nps_max is not None and nps_max != '':
            question_doc.qn_nps_max = int(nps_max)
        
        if data.get("qn_response_options"):
            for option in data.get("qn_response_options"):
                if isinstance(option, dict):
                    text = option.get("qo_option_text") or option.get("text") or ""
                    value = option.get("qo_option_value")
                    if value is None:
                        value = option.get("value", text)
                    url = option.get("qo_url") or option.get("url")
                else:
                    text = str(option)
                    value = text
                    url = None

                row = {
                    "qo_option_text": text,
                    "qo_option_value": value
                }
                if url:
                    row["qo_url"] = url

                question_doc.append("qn_response_options", row)
        
        question_doc.insert(ignore_permissions=True)
        return question_doc.name

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error en create_question_from_template_wizard")
        frappe.throw(f"Ocurrió un error al crear la pregunta: {str(e)}")

@frappe.whitelist()
def get_bank_data(keyword=None, demographic=None):
    OPTIONS_BASED_TYPES = [
        'Selección Múltiple', 
        'Selección Única', 
        'Likert', 
        'Escala de frecuencia', 
        'Ranking (Calificación o Prioridad)',
        'Likert Visual'
    ]

    user_company = frappe.db.get_value("Contact", {"user": frappe.session.user}, "custom_company")
    if not user_company:
        frappe.throw("El usuario actual no tiene una compañía asignada. Por favor, contacte al administrador.")

    question_filters = {
        'qn_status': 'Activa',
        'qn_owner': user_company
    }
    if keyword:
        question_filters['qn_statement'] = ['like', f'%{keyword}%']
    if demographic:
        question_filters['qn_demographic'] = demographic

    questions = frappe.get_list(
        "qp_IQ_Question",
        filters=question_filters,
        fields=[
            "name", "qn_statement as text", "qn_category", "qn_type", "qn_nps_min",
            "qn_nps_max", "qn_positive_statement", "qn_negative_statement", "qn_demographic"
        ],
        ignore_permissions=True
    )

    for q in questions:
        if q.get("qn_category"):
            q["category_name"] = frappe.db.get_value("qp_IQ_QuestionCategory", q["qn_category"], "qnc_category")
        else:
            q["category_name"] = "General"

        if q.get("qn_type"):
            q["type_name"] = frappe.db.get_value("qp_IQ_QuestionType", q["qn_type"], "qnt_type_name")
        else:
            q["type_name"] = "No definido"
        
        if q.get("qn_demographic"):
            q["demographic_name"] = frappe.db.get_value("qp_IQ_DemographicType", q["qn_demographic"], "dt_title")
        else:
            q["demographic_name"] = None

        if q.get("type_name") in OPTIONS_BASED_TYPES:
            if q.get("type_name") in ("Likert Visual", "Likert"):
                options = frappe.get_all(
                    "qp_IQ_QuestionOption",
                    filters={'parent': q.name, 'parenttype': 'qp_IQ_Question'},
                    fields=['qo_option_text', 'qo_option_value', 'qo_url'],
                    order_by='idx',
                    ignore_permissions=True
                )
                q['options'] = [
                    {"text": opt.qo_option_text, "value": opt.qo_option_value, "url": opt.qo_url}
                    for opt in options
                ]
            else:
                options = frappe.get_all(
                    "qp_IQ_QuestionOption",
                    filters={'parent': q.name, 'parenttype': 'qp_IQ_Question'},
                    fields=['qo_option_text'],
                    order_by='idx',
                    ignore_permissions=True
                )
                q['options'] = [opt['qo_option_text'] for opt in options]

    demographics = frappe.get_all(
        "qp_IQ_DemographicType",
        filters={"dt_object_type": "Pregunta"},
        fields=["name", "dt_title"],
        order_by="dt_title",
        ignore_permissions=True
    )

    return {
        "questions": questions,
        "demographics": demographics
    }
