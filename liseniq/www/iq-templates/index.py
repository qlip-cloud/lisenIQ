import frappe
import json
from frappe import _
from liseniq.utils.login_util import global_website_context, get_current_active_company


def get_context(context):

    if frappe.session.user == "Guest":
        frappe.throw(_("Cliente aún no ha sido registrado. Por favor comunique al Administrador."), frappe.PermissionError)

    context = global_website_context(context)

    # Configuración base de la página
    context.page_title = _("Plantillas")
    context.no_breadcrumbs = True
    context.is_navbar_custom = True
    context.no_cache = 1

    user_company = get_current_active_company()
    if not user_company:
        frappe.throw("El usuario actual no tiene una compañía activa asignada. Por favor, contacte al administrador o seleccione una empresa.")

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
                "qp_IQ_TemplateCategory",
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
            "qp_IQ_TemplateCategory",
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
        
        t_data = frappe.db.get_value("qp_IQ_QuestionType", q_doc.qn_type, ["qnt_type_name", "qnt_mnemonico"], as_dict=True) if q_doc.qn_type else None
        type_name = t_data.qnt_type_name if t_data else "No definido"
        mnemonic = t_data.qnt_mnemonico if t_data else None

        demographic_name = frappe.db.get_value("qp_IQ_DemographicType", q_doc.qn_demographic, "dt_title") if q_doc.qn_demographic else None
        culture_name = frappe.db.get_value("qp_IQ_DemographicType", q_doc.qp_topic, "dt_title") if q_doc.qp_topic else None

        question_data = {
            "id": q_doc.name,
            "text": q_doc.qn_statement,
            "text_others": q_doc.qn_statement_others,
            "type": q_doc.qn_type,
            "typeName": type_name,
            "demographic": demographic_name,
            "culture": culture_name,
            "negative_statement": q_doc.qn_negative_statement,
            "positive_statement": q_doc.qn_positive_statement,
            "nps_min": q_doc.qn_nps_min,
            "nps_max": q_doc.qn_nps_max,
            "qp_others": q_doc.get("qp_others", 0),
            "qp_none_above": q_doc.get("qp_none_above", 0),
            "options": []
        }

        if q_doc.qn_response_options:
            if mnemonic == "scale_likert" or type_name == "Likert":
                options = [
                    {
                        "text": opt.qo_option_text,
                        "value": opt.qo_option_value,
                        "url": getattr(opt, "qo_url", None)
                    }
                    for opt in q_doc.qn_response_options
                ]
            elif mnemonic == "scale_emoji" or type_name == "Likert Visual":
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
def get_demographic_suggestions_for_questions(search_term, object_type="Pregunta"):
    if not search_term:
        return []

    return frappe.get_all(
        "qp_IQ_DemographicType",
        filters={
            'dt_title': ['like', f'%{search_term}%'],
            'dt_object_type': object_type
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
        user_company = get_current_active_company()

        if not user_contact or not user_company:
            frappe.throw("No se pudo encontrar el contacto o la compañía para el usuario actual.")

        question_doc = frappe.new_doc("qp_IQ_Question")
        
        question_doc.qn_statement = data.get("qn_statement")
        
        # Guardar el enunciado para evaluadores
        if data.get("qn_statement_others"):
            question_doc.qn_statement_others = data.get("qn_statement_others")

        question_doc.qn_type = data.get("qn_type")
        question_doc.qn_category = data.get("qn_category")
        question_doc.qn_status = data.get("qn_status", "Activa")
        question_doc.qn_negative_statement = data.get("qn_negative_statement")
        question_doc.qn_positive_statement = data.get("qn_positive_statement")
        question_doc.qn_creator = user_contact
        question_doc.qn_owner = user_company
        question_doc.qp_others = data.get("qp_others", 0)
        question_doc.qp_none_above = data.get("qp_none_above", 0)
        
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
                culture_doc.dt_creator_company = user_company
                culture_doc.insert(ignore_permissions=True)
                culture_name = culture_doc.name
            
            question_doc.qp_topic = culture_name

        nps_min = data.get("qn_nps_min")
        if nps_min is not None and nps_min != '':
            question_doc.qn_nps_min = int(nps_min)

        nps_max = data.get("qn_nps_max")
        if nps_max is not None and nps_max != '':
            question_doc.qn_nps_max = int(nps_max)
        
        if data.get("qn_response_options"):
            for option in data.get("qn_response_options"):
                if isinstance(option, dict):
                    # Extracción segura de valores, previniendo diccionarios anidados que rompen el SQL
                    opt_text = option.get("qo_option_text") or option.get("text")
                    opt_val = option.get("qo_option_value") or option.get("value")
                    opt_url = option.get("qo_url") or option.get("url")

                    if isinstance(opt_text, dict):
                        if not opt_url:
                            opt_url = opt_text.get("url") or opt_text.get("qo_url")
                        if opt_val is None:
                            opt_val = opt_text.get("value") or opt_text.get("qo_option_value")
                        opt_text = opt_text.get("text") or opt_text.get("qo_option_text") or str(opt_text)

                    if isinstance(opt_val, dict):
                        opt_val = opt_val.get("value") or opt_val.get("qo_option_value") or str(opt_val)

                    if isinstance(opt_url, dict):
                        opt_url = opt_url.get("url") or opt_url.get("qo_url") or ""

                    text = str(opt_text) if opt_text is not None else ""
                    value = str(opt_val) if opt_val is not None else text
                    url = str(opt_url) if opt_url else None
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
def get_bank_data(keyword=None, demographic=None, template_category=None):
    # Tipos que usan opciones basados en sus nombres clásicos (por si acaso como fallback)
    OPTIONS_BASED_TYPES = [
        'Selección Múltiple', 
        'Casilla de verificación',
        'Selección Única', 
        'Likert', 
        'Escala de frecuencia', 
        'Ranking (Calificación o Prioridad)',
        'Likert Visual'
    ]

    OPTIONS_BASED_MNEMONICS = ['radio_group', 'check_group', 'scale_likert', 'scale_emoji']

    user_company = get_current_active_company()
    if not user_company:
        frappe.throw("El usuario actual no tiene una compañía asignada. Por favor, contacte al administrador.")

    question_filters = {
        'qn_status': 'Activa'
    }
    if keyword:
        question_filters['qn_statement'] = ['like', f'%{keyword}%']
    if demographic:
        question_filters['qn_demographic'] = demographic

    # Obtener el ID de la categoría "Liderazgo" si existe
    leadership_cat_name = frappe.db.get_value("qp_IQ_TemplateCategory", {"qnc_category": "Liderazgo"}, "name")

    if leadership_cat_name:
        # Si se seleccionó la categoría "Liderazgo", filtrar solo por esa categoría. De lo contrario, excluir esa categoría.
        if template_category == "Liderazgo":
            question_filters['qn_category'] = leadership_cat_name
        else:
            question_filters['qn_category'] = ['!=', leadership_cat_name]

    questions = frappe.get_list(
        "qp_IQ_Question",
        filters=question_filters,
        or_filters=[
            ['qn_owner', '=', user_company],
            ['qp_is_public', '=', 1]
        ],
        fields=[
            "name", 
            "qn_statement as text", 
            "qn_statement_others as text_others",
            "qn_category", "qn_type", "qn_nps_min",
            "qn_nps_max", "qn_positive_statement", "qn_negative_statement", "qn_demographic",
            "qp_topic",
            "qp_others", "qp_none_above"
        ],
        ignore_permissions=True
    )

    for q in questions:
        if q.get("qn_category"):
            q["category_name"] = frappe.db.get_value("qp_IQ_TemplateCategory", q["qn_category"], "qnc_category")
        else:
            q["category_name"] = "General"

        if q.get("qn_type"):
            t_data = frappe.db.get_value("qp_IQ_QuestionType", q["qn_type"], ["qnt_type_name", "qnt_mnemonico"], as_dict=True)
            if t_data:
                q["type_name"] = t_data.qnt_type_name
                mnemonic = t_data.qnt_mnemonico
            else:
                q["type_name"] = "No definido"
                mnemonic = None
        else:
            q["type_name"] = "No definido"
            mnemonic = None
        
        if q.get("qn_demographic"):
            q["demographic_name"] = frappe.db.get_value("qp_IQ_DemographicType", q["qn_demographic"], "dt_title")
        else:
            q["demographic_name"] = None

        if q.get("qp_topic"):
            q["culture_name"] = frappe.db.get_value("qp_IQ_DemographicType", q["qp_topic"], "dt_title")
        else:
            q["culture_name"] = None

        if mnemonic in OPTIONS_BASED_MNEMONICS or q.get("type_name") in OPTIONS_BASED_TYPES:
            if mnemonic in ("scale_emoji", "scale_likert") or q.get("type_name") in ("Likert Visual", "Likert"):
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

# Metodo para marcar preguntas de una plantilla como públicas
@frappe.whitelist()
def mark_template_questions_public(template_name: str):
    if not template_name:
        frappe.throw("Nombre de plantilla inválido.")

    try:
        # Obtener preguntas desde la tabla hija sin cargar el Doc completo
        rows = frappe.get_all(
            "qp_IQ_TemplateQuestion",
            filters={"parent": template_name, "parenttype": "qp_IQ_Template"},
            fields=["tq_question"],
            ignore_permissions=True
        )
        question_names = [r.tq_question for r in rows if r.tq_question]

        for qname in question_names:
            frappe.db.set_value("qp_IQ_Question", qname, "qp_is_public", 1, update_modified=True)

        return {"updated": len(question_names)}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Error al marcar preguntas como públicas")
        frappe.throw("No fue posible marcar las preguntas como públicas. Intenta nuevamente.")