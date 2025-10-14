import frappe
import json
from frappe import _
from liseniq.utils.constants import WEB_FORM_CLIENT_SCRIPT, WEB_FORM_CUSTOM_CSS
from liseniq.utils.api_survey import generate_public_link_for_survey

def get_context(context):

    if frappe.session.user == "Guest":
        frappe.throw(_("Cliente aún no ha sido registrado. Por favor comunique al Administrador."), frappe.PermissionError)

    context.no_cache = 1
    context.page_title = "Crear Medición"
    context.no_breadcrumbs = True
    context.is_navbar_custom = True

    measurement_name = frappe.request.args.get('name')
    context.is_edit_mode = bool(measurement_name)
    context.page_title = "Editar Medición" if context.is_edit_mode else "Crear Medición"
    context.measurement_data_json = "null"

    # Modo edición: cargar datos existentes
    if context.is_edit_mode:
        try:
            doc = frappe.get_doc("qp_IQ_Survey", measurement_name)
            # Construir preguntas
            questions = []
            for q_link in (doc.su_questions or []):
                q_doc = frappe.get_doc("qp_IQ_Question", q_link.sq_question)
                type_name = frappe.db.get_value("qp_IQ_QuestionType", q_doc.qn_type, "qnt_type_name")
                demo_title = frappe.db.get_value("qp_IQ_DemographicType", q_doc.qn_demographic, "dt_title") if q_doc.qn_demographic else None
                options = [opt.qo_option_text for opt in (q_doc.qn_response_options or [])]
                questions.append({
                    "id": q_doc.name,
                    "text": q_doc.qn_statement,
                    "type": q_doc.qn_type,
                    "typeName": type_name,
                    "demographic": demo_title,
                    "options": options,
                    "nps_min": q_doc.qn_nps_min,
                    "nps_max": q_doc.qn_nps_max
                })

            # Datos de participantes
            recipients_count = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": doc.name})
            survey_type = "selected" if recipients_count > 0 else "all"
            response_type = "anonymous" if doc.su_is_anonymous else "identified"

            # Construir lista de contactos para el modal en edición
            contacts_headers = ["Nombre"]
            contacts_list = []
            if recipients_count > 0:
                recipient_rows = frappe.get_all("qp_IQ_SurveyRecipient", filters={"sr_survey": doc.name}, fields=["sr_contact"])
                contact_names = [r.sr_contact for r in recipient_rows if r.sr_contact]
                if contact_names:
                    contact_docs = frappe.get_all("Contact", filters={"name": ["in", contact_names]}, fields=["name", "first_name", "last_name"])
                    for c in contact_docs:
                        contacts_list.append({
                            "name": c.name,
                            "Nombre": f"{(c.first_name or '').strip()} {(c.last_name or '').strip()}".strip()
                        })

            measurement_data = {
                "name": doc.su_name,
                "startDate": doc.su_start_date,
                "endDate": doc.su_end_date,
                "timezone": doc.su_timezone,
                "reminders": {
                    "send": True if doc.su_send_reminders else False,
                    "frequency": doc.su_reminder_frequency,
                    "max": doc.su_reminder_max
                },
                "questions": questions,
                "contacts": {
                    "surveyType": survey_type,
                    "responseType": response_type,
                    "contactCount": recipients_count,
                    "headers": contacts_headers,
                    "list": contacts_list
                }
            }
            context.measurement_data_json = frappe.as_json(measurement_data)
        except Exception as e:
            frappe.log_error(f"Error cargando medición para editar: {e}", "new_measurement.get_context")
            frappe.throw(_("Medición no encontrada."), frappe.DoesNotExistError)

    try:
        context.contact_demographics = frappe.get_all(
            "qp_IQ_DemographicType",
            filters={"dt_object_type": "Contacto"},
            fields=["name", "dt_title"],
            order_by="dt_title"
        )
    except frappe.DoesNotExistError:
        context.contact_demographics = []

    try:
        allowed_question_types = ["Likert", "Abierta", "NPS", "Selección Múltiple"]
        context.question_types = frappe.get_all(
            "qp_IQ_QuestionType",
            filters={"qnt_type_name": ["in", allowed_question_types]},
            fields=["name", "qnt_type_name"],
            order_by="qnt_type_name"
        )
    except frappe.DoesNotExistError:
        context.question_types = []

    try:
        meta = frappe.get_meta("qp_IQ_Survey")
        timezone_field = meta.get_field("su_timezone")
        if timezone_field and timezone_field.options:
            context.timezones = timezone_field.options.split('\n')
        else:
            context.timezones = []
    except frappe.DoesNotExistError:
        context.timezones = []

    template_name = frappe.request.args.get('template')
    if template_name:
        try:
            questions = frappe.call(
                'liseniq.www.iq-templates.index.get_questions_from_template',
                template_name=template_name
            )
            context.preloaded_questions_json = frappe.as_json(questions)
        except Exception as e:
            frappe.log_error(f"No se pudieron cargar las preguntas de la plantilla {template_name}: {e}", "Error en new_measurement.py")
            context.preloaded_questions_json = "[]"
    else:
        context.preloaded_questions_json = "[]"

    context.update({
        "is_navbar_custom": True,
        "no_cache": 1
    })

    return context

@frappe.whitelist()
def check_measurement_name(name, exclude_doc=None, only_open=False):
    user_company = frappe.db.get_value("Contact", {"user": frappe.session.user, "custom_is_liseniq_contact": 0}, "custom_company")
    if not user_company:
        exists = frappe.db.exists("qp_IQ_Survey", {"su_name": name})
        return {"exists": bool(exists)}

    conditions = [
        ["qp_IQ_Survey", "su_owner", "=", user_company],
        ["qp_IQ_Survey", "su_name", "=", name],
    ]
    if exclude_doc:
        conditions.append(["qp_IQ_Survey", "name", "!=", exclude_doc])

    if only_open:
        open_status_docs = frappe.get_all(
            "qp_IQ_SurveyStatus",
            filters={"se_status": ["in", ["Programada", "En Progreso", "Borrador"]]},
            fields=["name"]
        )
        open_status_ids = [d.name for d in open_status_docs]
        if open_status_ids:
            conditions.append(["qp_IQ_Survey", "su_status", "in", open_status_ids])

    rows = frappe.get_all("qp_IQ_Survey", filters=conditions, fields=["name"], limit_page_length=1)
    return {"exists": bool(rows)}

@frappe.whitelist()
def get_demographic_values_for_contacts(demographic_type):
    if not demographic_type:
        return frappe._dict({"values": [], "color": None})

    color = frappe.db.get_value("qp_IQ_DemographicType", demographic_type, "dt_tag_color")

    values = frappe.get_all(
        "qp_IQ_ContactAdditionalDetail",
        filters={"cad_demographic_type": demographic_type},
        fields=["cad_value"],
        distinct=True,
        order_by="cad_value"
    )
    
    return frappe._dict({
        "values": [d.get("cad_value") for d in values if d.get("cad_value")],
        "color": color
    })

@frappe.whitelist()
def get_filtered_contacts_count(filters='[]'):
    filters = json.loads(filters)
    user_contact_name = frappe.db.get_value("Contact", {"user": frappe.session.user, "custom_is_liseniq_contact": 0}, "name")
    user_company = frappe.db.get_value("Contact", {"user": frappe.session.user, "custom_is_liseniq_contact": 0}, "custom_company")

    base_filters = [
        ["Contact", "status", "in", ["Enabled", "Passive"]],
        ["Contact", "custom_is_liseniq_contact", "=", 1]
    ]
    if user_company:
        base_filters.append(["Contact", "custom_company", "=", user_company])

    if user_contact_name:
        base_filters.append(["Contact", "name", "!=", user_contact_name])

    if not filters:
        all_contacts = frappe.get_list(
            "Contact", 
            filters=base_filters, 
            fields=["name", "first_name", "last_name"],
            ignore_permissions=True
        )
        contacts_for_modal = [{"name": c.name, "Nombre": f"{c.first_name} {c.last_name or ''}".strip()} for c in all_contacts]
        return {
            "count": len(all_contacts),
            "headers": ["Nombre"],
            "contacts": contacts_for_modal
        }

    where_conditions = []
    params = []
    demographic_ids = []
    
    for f in filters:
        demographic_type = f.get("demographic_type")
        values = f.get("values")
        if demographic_type and values:
            demographic_ids.append(demographic_type)
            value_placeholders = ','.join(['%s'] * len(values))
            where_conditions.append(f"(cad_demographic_type = %s AND cad_value IN ({value_placeholders}))")
            params.append(demographic_type)
            params.extend(values)

    if not where_conditions:
        return {"count": 0, "headers": ["Nombre"], "contacts": []}

    query = f"""
        SELECT parent
        FROM `tabqp_IQ_ContactAdditionalDetail`
        WHERE {' OR '.join(where_conditions)}
        GROUP BY parent
        HAVING COUNT(DISTINCT cad_demographic_type) = %s
    """
    params.append(len(filters))

    matching_contact_names = [row[0] for row in frappe.db.sql(query, tuple(params))]

    if not matching_contact_names:
        return {"count": 0, "headers": ["Nombre"], "contacts": []}

    contact_filters = {
        "name": ["in", matching_contact_names], 
        "status": ["in", ["Enabled", "Passive"]],
        "custom_is_liseniq_contact": 1
    }
    if user_contact_name:
        contact_filters["name"] = ["in", [name for name in matching_contact_names if name != user_contact_name]]

    if user_company:
        contact_filters["custom_company"] = user_company


    contact_docs = frappe.get_all(
        "Contact",
        filters=contact_filters,
        fields=["name", "first_name", "last_name"],
        ignore_permissions=True
    )
    
    demographic_map_docs = frappe.get_all(
        "qp_IQ_DemographicType",
        filters={"name": ["in", list(set(demographic_ids))]},
        fields=["name", "dt_title"]
    )
    id_to_title_map = {doc.name: doc.dt_title for doc in demographic_map_docs}
    
    headers = ["Nombre"] + [id_to_title_map[demo_id] for demo_id in demographic_ids if demo_id in id_to_title_map]

    demographic_details = frappe.get_all(
        "qp_IQ_ContactAdditionalDetail",
        filters={"parent": ["in", [c.name for c in contact_docs]]},
        fields=["parent", "cad_demographic_type", "cad_value"]
    )

    details_map = {}
    for detail in demographic_details:
        if detail.parent not in details_map:
            details_map[detail.parent] = {}
        if detail.cad_demographic_type in id_to_title_map:
            demographic_title = id_to_title_map[detail.cad_demographic_type]
            details_map[detail.parent][demographic_title] = detail.cad_value

    contacts_for_modal = []
    for contact in contact_docs:
        contact_data = {"name": contact.name, "Nombre": f"{contact.first_name} {contact.last_name or ''}".strip()}
        contact_specific_details = details_map.get(contact.name, {})
        for header in headers:
            if header != "Nombre":
                contact_data[header] = contact_specific_details.get(header, "N/A")
        contacts_for_modal.append(contact_data)

    return {"count": len(contact_docs), "headers": headers, "contacts": contacts_for_modal}

@frappe.whitelist()
def save_measurement(data):
    try:
        data = json.loads(data)

        # Modo edición: actualizar solo nombre, fecha de cierre y recordatorios
        if data.get("is_edit_mode") and data.get("doc_name"):
            survey = frappe.get_doc("qp_IQ_Survey", data["doc_name"])

            # Validación de nombre único por compañía
            new_name = data.get("name")
            if new_name:
                exists = frappe.get_all(
                    "qp_IQ_Survey",
                    filters=[
                        ["qp_IQ_Survey", "su_owner", "=", survey.su_owner],
                        ["qp_IQ_Survey", "su_name", "=", new_name],
                        ["qp_IQ_Survey", "name", "!=", survey.name],
                    ],
                    fields=["name"],
                    limit_page_length=1
                )
                if exists:
                    return {"status": "error", "message": _("Ya existe una medición con ese nombre para su empresa.")}

                survey.su_name = new_name

            survey.su_end_date = data.get("endDate")

            reminders = data.get("reminders")
            if reminders:
                survey.su_send_reminders = 1
                survey.su_reminder_frequency = reminders.get("frequency")
                survey.su_reminder_max = reminders.get("max")
            else:
                survey.su_send_reminders = 0
                survey.su_reminder_frequency = None
                survey.su_reminder_max = None

            survey.save(ignore_permissions=True)
            frappe.db.commit()
            return {"status": "success", "message": f"Medición '{survey.su_name}' actualizada exitosamente.", "docname": survey.name}

        # Modo nueva encuesta o creación
        question_types_map = {qt.name: qt.qnt_type_name for qt in frappe.get_all("qp_IQ_QuestionType", fields=["name", "qnt_type_name"])}
        
        user_contact = frappe.db.get_value("Contact", {"user": frappe.session.user, "custom_is_liseniq_contact": 0}, "name")
        user_company = frappe.db.get_value("Contact", {"user": frappe.session.user, "custom_is_liseniq_contact": 0}, "custom_company")

        manual_question_map = {}
        if data.get("questions"):
            for q in data["questions"]:
                if q.get("id", "").startswith("manual-"):
                    question_text = q["text"]
                    existing_question = frappe.db.exists("qp_IQ_Question", {"qn_statement": question_text, "qn_owner": user_company})

                    if existing_question:
                        manual_question_map[q["id"]] = existing_question
                    else:
                        new_question = frappe.new_doc("qp_IQ_Question")
                        new_question.qn_statement = question_text
                        new_question.qn_type = q["type"]
                        new_question.qn_creator = user_contact
                        new_question.qn_owner = user_company
                        
                        if q.get("demographic"):
                            demographic_name = frappe.db.exists("qp_IQ_DemographicType", {"dt_title": q["demographic"]})
                            if not demographic_name:
                                demographic_doc = frappe.new_doc("qp_IQ_DemographicType")
                                demographic_doc.dt_title = q["demographic"]
                                demographic_doc.dt_object_type = "Pregunta"
                                demographic_doc.insert(ignore_permissions=True)
                                demographic_name = demographic_doc.name
                            new_question.qn_demographic = demographic_name

                        if q.get("options"):
                            if q.get("typeName") == "Likert" or (isinstance(q.get("options")[0], dict) and "value" in q["options"][0]):
                                for opt in q["options"]:
                                    new_question.append("qn_response_options", {
                                        "qo_option_text": opt["text"] if isinstance(opt, dict) else opt,
                                        "qo_option_value": opt["value"] if isinstance(opt, dict) and "value" in opt else opt
                                    })
                            else:
                                for opt_text in q["options"]:
                                    new_question.append("qn_response_options", {"qo_option_text": opt_text, "qo_option_value": opt_text})
                        
                        if q.get("negative_statement"): new_question.qn_statement_negative = q["negative_statement"]
                        if q.get("positive_statement"): new_question.qn_statement_positive = q["positive_statement"]
                        if q.get("nps_min") is not None: new_question.qn_nps_min = q["nps_min"]
                        if q.get("nps_max") is not None: new_question.qn_nps_max = q["nps_max"]
                            
                        new_question.insert(ignore_permissions=True)
                        manual_question_map[q["id"]] = new_question.name

        surveyjs_doc_name = None
        if data.get("questions"):
            elements = []
            for q in data["questions"]:
                question_name = manual_question_map.get(q["id"]) if q.get("id", "").startswith("manual-") else q["id"]
                
                question_type_title = question_types_map.get(q["type"])
                
                surveyjs_type = "text"
                if question_type_title == "Selección Múltiple":
                    surveyjs_type = "radiogroup"
                elif question_type_title == "Abierta":
                    surveyjs_type = "comment"
                elif question_type_title == "NPS":
                    surveyjs_type = "rating"
                elif question_type_title == "Likert":
                    surveyjs_type = "radiogroup"

                element = {
                    "type": surveyjs_type,
                    "name": question_name,
                    "title": q["text"],
                    "isRequired": "true"
                }

                if question_type_title == "Likert" and q.get("options"):
                    element["choices"] = [
                        {"text": opt["text"], "value": opt["value"]}
                        if isinstance(opt, dict) and "value" in opt else
                        {"text": opt, "value": idx+1}
                        for idx, opt in enumerate(q["options"])
                    ]
                elif question_type_title == "Selección Múltiple" and q.get("options"):
                    element["choices"] = q["options"]
                elif question_type_title == "NPS":
                    element["rateMin"] = q.get("nps_min", 1)
                    element["rateMax"] = q.get("nps_max", 10)

                elements.append(element)

            survey_json_content = {
                "title": data["name"],
                "description": "",
                "pages": [
                    {
                        "name": "page1",
                        "elements": elements
                    }
                ]
            }

            surveyjs_doc = frappe.new_doc("Survey")
            surveyjs_doc.name = data["name"]
            surveyjs_doc.title = data["name"]
            surveyjs_doc.survey_json = json.dumps(survey_json_content)
            surveyjs_doc.insert(ignore_permissions=True)
            surveyjs_doc_name = surveyjs_doc.name

            web_form_route = data["name"].lower().replace(" ", "-")           
            web_form = frappe.new_doc("Web Form")
            web_form.title = data["name"]
            web_form.route = web_form_route
            web_form.doc_type = "Survey Response"
            web_form.module = "Frappe Survey"
            web_form.client_script = WEB_FORM_CLIENT_SCRIPT
            web_form.custom_css = WEB_FORM_CUSTOM_CSS
            web_form.published = 1

            survey_response_meta = frappe.get_meta("Survey Response")
            fieldtype_mapping = {
                "Long Text": "Text Editor"
            }
            for field in survey_response_meta.fields:
                if field.fieldtype not in ["Section Break", "Column Break", "Tab Break"]:
                    web_form_fieldtype = fieldtype_mapping.get(field.fieldtype, field.fieldtype)
                    web_form.append("web_form_fields", {
                        "fieldname": field.fieldname,
                        "fieldtype": web_form_fieldtype,
                        "label": field.label,
                        "reqd": field.reqd,
                        "options": field.options,
                        "hidden": field.hidden,
                        "read_only": field.read_only,
                        "default": field.default,
                        "description": field.description,
                    })

            web_form.insert(ignore_permissions=True)

        user_contact_info = frappe.db.get_value("Contact", {"user": frappe.session.user, "custom_is_liseniq_contact": 0}, "custom_company")
        if not user_contact_info:
            message = "El usuario actual no tiene una compañía asignada para definir la propiedad de la medición."
            frappe.log_error(message, "Error en save_measurement")
            return {"status": "error", "message": message}
        user_company = user_contact_info
        
        default_status_text = "Programada"
        status_name = frappe.db.get_value("qp_IQ_SurveyStatus", {"se_status": default_status_text}, "name")
        
        if not status_name:
            status_doc = frappe.new_doc("qp_IQ_SurveyStatus")
            status_doc.se_status = default_status_text
            status_doc.insert(ignore_permissions=True)
            status_name = status_doc.name
        
        survey = frappe.new_doc("qp_IQ_Survey")
        survey.su_name = data["name"]
        survey.su_owner = user_company
        survey.su_start_date = data.get("startDate")
        survey.su_end_date = data.get("endDate")
        survey.su_timezone = data.get("timezone")
        
        contacts_data = data.get("contacts", {})
        survey_type = contacts_data.get("surveyType")
        response_type = contacts_data.get("responseType")

        survey.su_is_anonymous = 1 if response_type == 'anonymous' else 0

        # Por ahora, no se genera link público para encuestas de tipo 'all' (Público Externo)
        if survey_type == 'all':
            survey.custom_generate_public_link = 0
        # Se genera un link genérico para encuestas con contactos seleccionados
        elif survey_type == 'selected':
            survey.custom_generate_public_link = 1


        survey.su_status = status_name
        if surveyjs_doc_name:
            survey.su_surveyjs_survey = surveyjs_doc_name

        if data.get("reminders"):
            survey.su_send_reminders = 1
            survey.su_reminder_frequency = data["reminders"]["frequency"]
            survey.su_reminder_max = data["reminders"]["max"]
        else:
            survey.su_send_reminders = 0

        if data.get("questions"):
            for q in data["questions"]:
                question_name = manual_question_map.get(q["id"]) if q.get("id", "").startswith("manual-") else q["id"]
                if question_name:
                    survey.append("su_questions", {"sq_question": question_name})

        survey.insert(ignore_permissions=True)
        frappe.db.commit()

        if survey.custom_generate_public_link:
            if generate_public_link_for_survey(survey, "after_save"):
                survey.save(ignore_permissions=True)
                frappe.db.commit()

        if survey_type == 'selected' and contacts_data.get("list"):
            contact_names = [c.get("name") for c in contacts_data.get("list") if c.get("name")]
            if contact_names:
                for contact_name in contact_names:
                    frappe.get_doc({
                        "doctype": "qp_IQ_SurveyRecipient",
                        "sr_survey": survey.name,
                        "sr_contact": contact_name,
                        "sr_status": "Not Sent"
                    }).insert(ignore_permissions=True)
        
        frappe.db.commit()
        
        return {"status": "success", "message": f"Medición '{survey.su_name}' creada exitosamente.", "docname": survey.name}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Error en save_measurement")
        return {"status": "error", "message": str(e)}