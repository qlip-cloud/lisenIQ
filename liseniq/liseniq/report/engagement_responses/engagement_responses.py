# Copyright (c) 2013, Mentum Group and contributors
# For license information, please see license.txt
import frappe

import json
import frappe
from frappe import _

"""
TODO: 

1. Implementar el reporte por tablas separadas para el reporte de medición de cultura organizacional
2. Agregar todos los subdemográficos y cuando no exista el dato, colocar NA
"""
CATEGORIES = {
    "Sentido de propósito": "MI INSPIRACIÓN",
    "Trabajo trascendental": "MI INSPIRACIÓN",
    "Me Conocen": "MI INSPIRACIÓN",
    "Mi líder": "LOS LÍDERES",
    "Apoyo": "LOS LÍDERES",
    "Nuestros líderes": "LOS LÍDERES",
    "Oportunidades de crecimiento en mi Rol": "MI DESARROLLO Y APRENDIZAJE",
    "Oportunidades de desarrollo en la Organización": "MI DESARROLLO Y APRENDIZAJE",
    "Cultura de Aprendizaje": "MI DESARROLLO Y APRENDIZAJE",
    "Dinámicas de Equipo": "MI EQUIPO",
    "Comunicación y Coordinación": "MI EQUIPO",
    "Agilidad y Toma de Decisiones": "MI EQUIPO",
    "Calidad de las relaciones": "AMBIENTE LABORAL POSITIVO",
    "Trato de la Gente": "AMBIENTE LABORAL POSITIVO",
    "Equidad y transparencia": "AMBIENTE LABORAL POSITIVO",
    "Reputación de la Organización": "MI TRABAJO",
    "Reputación de mi área": "MI TRABAJO",
    "Entorno de trabajo": "MI TRABAJO",
    "Principios": "RESPONSABLE",
    "Sostenibilidad": "RESPONSABLE",
    "Clientes": "RESPONSABLE",
    "Talento": "HUMANISTA",
    "Relaciones": "HUMANISTA",
    "Comunicación": "HUMANISTA",
    "Innovación": "COMPETITIVA",
    "Logro": "COMPETITIVA",
    "Liderazgo": "COMPETITIVA",
}

CARVAJAL_COMPANIES = {
    "a570be58ba": "Carvajal Corporativo",
    "a0567d22cc": "Carvajal Educación",
    "5843de47eb": "Carvajal Soluciones de comunicación",
    "9f2246bdd0": "Carvajal Pulpa y Papel",
    "be89e11a86": "Carvajal Servicios Compartidos",
    "510028895a": "Carvajal Empaques",
    "5f58f986f1": "Carvajal Tecnología y Servicios",
    "e34486d9ea": "Carvajal espacios",
}

VEDANTA_BIENESTAR = {
    "Propósito y Valores": "PILAR EMPRESARIAL",
    "Seguridad Organizacional": "PILAR EMPRESARIAL",
    "Liderazgo": "PILAR EMPRESARIAL",
    "Comunicación": "PILAR CULTURAL",
    "Desarrollo Profesional": "PILAR CULTURAL",
    "Entorno": "PILAR CULTURAL",
    "Pertenencia y Valoración": "PILAR CULTURAL",
    "Emocional": "PILAR PERSONAL",
    "Mental": "PILAR PERSONAL",
    "Física": "PILAR PERSONAL",
    "Financiera": "PILAR PERSONAL",
}

TEMAS_INDICE_DE_ENGAGEMENT = {
    "Si me ofrecieran un trabajo en condiciones similares en otra empresa, me quedaría donde estoy": "MI INSPIRACIÓN",
    "Le recomendaría a un amigo o familiar que trabaje en esta organización": "AMBIENTE LABORAL POSITIVO",
    "Siento compromiso y orgullo de trabajar en esta organización": "MI TRABAJO",
    "Hago parte de un equipo de alto desempeño en la organización": "MI EQUIPO",
    "Me veo aprendiendo y creciendo en esta organización en el futuro": "MI DESARROLLO Y APRENDIZAJE",
    "Los líderes en esta organización me inspiran": "LOS LÍDERES",
}


def execute(filters=None):
    filters = filters or {}
    survey_name = filters.get("survey")

    if not frappe.db.exists("Survey", survey_name):
        frappe.throw(_("Encuesta no encontrada: {0}").format(survey_name))

    survey_doc = frappe.get_doc("Survey", survey_name)
    survey_json = getattr(survey_doc, "survey_json", "{}") or "{}"

    survey_status = get_survey_status(survey_name)

    question_map = get_question_labels(survey_json)

    # Obtener demographics_map basado en los usuarios específicos de esta encuesta
    demographics_map = get_demographics_labels_by_status(survey_status, survey_name)

    columns = build_columns(demographics_map)

    # Verificar si la encuesta está finalizada
    data = get_survey_data(survey_name, question_map, demographics_map, survey_status)

    return columns, data


def get_survey_status(survey_name):
    """
    Obtiene el estado de la encuesta desde qp_IQ_Survey, incluyendo compañía y plantilla
    """
    try:
        query = """
            SELECT 
                iq.name as survey_id,
                iq.su_in_history as in_history,
                iq.su_owner as company_id,
                c.co_name as company_name,
                iq.su_template as template_id,
                tp.tp_name as template_name
            FROM `tabqp_IQ_Survey` iq
            LEFT JOIN `tabqp_IQ_Company` c ON c.name = iq.su_owner
            LEFT JOIN `tabqp_IQ_Template` tp ON tp.name = iq.su_template
            WHERE iq.su_name = %s
        """
        result = frappe.db.sql(query, survey_name, as_dict=True)
        if result:
            return {
                "survey_id": result[0].get("survey_id", ""),
                "in_history": result[0].get("in_history", ""),
                "company_id": result[0].get("company_id", ""),
                "company_name": result[0].get("company_name", ""),
                "template_id": result[0].get("template_id", ""),
                "template_name": result[0].get("template_name", ""),
            }
        return {
            "survey_id": "",
            "in_history": "",
            "company_id": "",
            "company_name": "",
            "template_id": "",
            "template_name": "",
        }
    except Exception as e:
        frappe.log_error(f"Error getting survey status: {str(e)}")
        return {
            "survey_id": "",
            "in_history": "",
            "company_id": "",
            "company_name": "",
            "template_id": "",
            "template_name": "",
        }


def get_historical_survey_data(survey_id, question_map, demographics_map):
    """
    Obtiene los datos históricos de una encuesta finalizada desde qp_IQ_SurveyHistoricData
    """
    try:
        query = """
            SELECT 
                shd.name,
                shd.shd_survey_id,
                shd.shd_survey_name,
                shd.shd_contact_name,
                shd.shd_document_type,
                shd.shd_document_number,
                 shd.shd_country,
                shd.shd_entry_date,
                al.al_title as academic_level,
                shd.shd_dob,
                shd.shd_gender,
                shd.shd_company,
                shd.shd_measurement_response,
                GROUP_CONCAT(
                    CONCAT(cdh.cdh_demographic_type, ':', cdh.cdh_value)
                    SEPARATOR '||'
                ) as demographics_data
            FROM `tabqp_IQ_SurveyHistoricData` shd
            LEFT JOIN `tabqp_IQ_ContactDetailHistoric` cdh ON cdh.parent = shd.name
            LEFT JOIN `tabqp_IQ_AcademicLevel` al ON al.name = shd.shd_academic_level
            WHERE shd.shd_survey_id = %s
            GROUP BY shd.name
        """
        results = frappe.db.sql(query, survey_id, as_dict=True)
        return results
    except Exception as e:
        frappe.log_error(f"Error getting historical survey data: {str(e)}")
        return []


def process_historical_response_row(
    hist_record, question_map, demographics_map, survey_status, question_variables_map
):
    """
    Procesa un registro histórico de respuesta y retorna múltiples filas (una por pregunta)
    """
    # Datos base del registro histórico que se repiten en cada fila
    base_row = {
        "name": hist_record.get("name", ""),
        "gender": hist_record.get("shd_gender", ""),
        "custom_dob": hist_record.get("shd_dob", ""),
        "country": hist_record.get("shd_country", ""),
        "custom_academic_level": hist_record.get("academic_level", ""),
        "entry_date": hist_record.get("shd_entry_date", ""),
    }

    # Inicializar campos demográficos
    for demographic_id in demographics_map.keys():
        base_row[demographic_id] = ""

    # Sobrescribir con los valores del registro histórico
    demographics_data_str = hist_record.get("demographics_data", "")
    if demographics_data_str:
        for demo_pair in demographics_data_str.split("||"):
            if ":" in demo_pair:
                demo_type, demo_value = demo_pair.split(":", 1)
                base_row[demo_type] = demo_value

    # Procesar respuestas de la encuesta
    response_json = hist_record.get("shd_measurement_response", "{}")
    parsed_responses = parse_response_json(response_json)

    # Obtener información de la encuesta para lógica de tema
    company_name = survey_status.get("company_name", "")
    template_name = survey_status.get("template_name", "")

    # Crear una fila por cada pregunta
    rows = []
    for qid, question_label in question_map.items():
        row = base_row.copy()
        row["question"] = question_label
        row["answer"] = parsed_responses.get(qid, "")

        # Agregar variable y tema
        question_info = question_variables_map.get(question_label, {})
        variable = question_info.get("variable", "")
        row["variable"] = variable

        # Determinar el tema según el template y la compañía
        tema = ""
        if template_name == "Plantilla Modelo Vedanta bienestar":
            tema = VEDANTA_BIENESTAR.get(variable, "")
        else:
            tema = question_info.get("tema", "")

        # Lógica especial para empresas Carvajal
        try:
            company_name_val = (company_name or "").lower().strip()
            carvajal_names = {n.lower().strip() for n in CARVAJAL_COMPANIES.values()}
            if company_name_val and company_name_val in carvajal_names:
                tema = "CULTURA CARVAJAL"
        except Exception:
            pass

        row["theme"] = tema
        rows.append(row)

    return rows


def build_columns(demographics_map):
    """
    Construye las columnas del reporte de manera dinámica
    Documento Evaluador	Evaluador	Correo Evaluador	Documento Evaluado	Evaluado	Correo evaluado	Relación	Competencia	Comportamiento	Respuesta	Area Evaluado	Cargo Evaluado	Demo 1 Evaluado	Demo 2 Evaluado	Pais Evaluado	Sede Evaluado

    """
    columns = [
        {
            "fieldname": "id_evaluator",
            "label": "Documento Evaluador",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "evaluator",
            "label": "Evaluador",
            "fieldtype": "Data",
            "width": 300,
        },
        {
            "fieldname": "email_evaluator",
            "label": "Email Evaluador",
            "fieldtype": "Data",
            "width": 300,
        },
        {
            "fieldname": "id_evaluatee",
            "label": "Documento Evaluado",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "evaluatee",
            "label": "Evaluado",
            "fieldtype": "Data",
            "width": 300,
        },
        {
            "fieldname": "email_evaluatee",
            "label": "Email Evaluado",
            "fieldtype": "Data",
            "width": 300,
        },
        {
            "fieldname": "relation",
            "label": "Relación",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "variable",
            "label": "Competencia",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "question",
            "label": "Comportamiento",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "answer",
            "label": "Respuesta",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": _("Género"),
            "fieldname": "gender",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "label": _("Fecha de Nacimiento"),
            "fieldname": "custom_dob",
            "fieldtype": "Date",
            "width": 150,
        },
        {
            "label": _("País"), 
            "fieldname": "country", 
            "fieldtype": "Data", 
            "width": 150},
        {
            "label": _("Nivel Académico"),
            "fieldname": "custom_academic_level",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": _("Fecha de Ingreso"),
            "fieldname": "entry_date",
            "fieldtype": "Date",
            "width": 150,
        },
    ]

    # Agregar columnas demográficas
    for did, dtitle in demographics_map.items():
        columns.append(
            {
                "label": dtitle or did,
                "fieldname": did,
                "fieldtype": "Data",
                "width": 200,
            }
        )

    return columns


def get_survey_data(survey_name, question_map, demographics_map, survey_status):
    """
    Obtiene los datos de la encuesta de manera optimizada
    Ahora cada pregunta genera una fila separada
    """
    data = []

    # Obtener mapeo de preguntas a variables y temas
    question_variables_map = get_question_variables_map()

    # Si la encuesta está finalizada, usar datos históricos
    # if survey_status.get("in_history") == 1:
    #     survey_id = survey_status.get("survey_id", "")
    #     if survey_id:
    #         historical_data = get_historical_survey_data(
    #             survey_id, question_map, demographics_map
    #         )
    #         for hist_record in historical_data:
    #             rows = process_historical_response_row(
    #                 hist_record,
    #                 question_map,
    #                 demographics_map,
    #                 survey_status,
    #                 question_variables_map,
    #             )
    #             data.extend(rows)  # Ahora devuelve múltiples filas
    #         return data

    # Si no está finalizada, usar datos en tiempo real
    query = """
        SELECT 
            sr.name,
            sr.user,
            sr.response_json,
            sr.custom_evaluatee,
            c.custom_dob,
            c.custom_entry_date,
            c.custom_country,
            c.gender,
            a.al_title
        FROM `tabSurvey Response` sr
        LEFT JOIN `tabContact` c ON c.name = sr.user
        LEFT JOIN `tabqp_IQ_AcademicLevel` a ON a.name = c.custom_academic_level
        WHERE sr.survey = %s
        ORDER BY sr.creation DESC
    """

    responses = frappe.db.sql(query, (survey_name,), as_dict=True)

    if not responses:
        return []


    evaluatee_list = [r.custom_evaluatee for r in responses if r.custom_evaluatee]
    demographics_data = (
        get_bulk_demographics(evaluatee_list, demographics_map) if evaluatee_list else {}
    )

    user_list = [r.user for r in responses if r.user]
    contacts = list(set(user_list + evaluatee_list))
    users_data_map = {}
    for user in contacts:
        users_data_map[user] = {
            "email": get_user_email(user),
            "id": get_user_id(user),
            }
    

    for response in responses:
        rows = process_response_row(
            survey_name,
            response,
            question_map,
            demographics_map,
            demographics_data,
            users_data_map,
            survey_status,
            question_variables_map,
        )
        data.extend(rows) 

    return data


def process_response_row(
    survey_name,
    response,
    question_map,
    demographics_map,
    demographics_data,
    users_data_map,
    survey_status,
    question_variables_map,
):
    """
    Procesa una respuesta individual y retorna múltiples filas (una por pregunta)
    """
    user = response.get("user", "")
    evaluatee = response.get("custom_evaluatee", "")
    # Datos base de la respuesta que se repiten en cada fila
    base_row = {
        "id_evaluator": users_data_map.get(user, {}).get("id", ""),
				"evaluator": response.get("user", ""),
				"email_evaluator": users_data_map.get(user, {}).get("email", ""),
				"id_evaluatee": users_data_map.get(response.get("custom_evaluatee", ""), {}).get("id", ""),
				"evaluatee": response.get("custom_evaluatee", ""),
				"email_evaluatee": users_data_map.get(response.get("custom_evaluatee", ""), {}).get("email", ""),
				"relation": get_relation(survey_name, user, response.get("custom_evaluatee", "")), 
        "gender": response.get("gender", ""),
        "custom_dob": response.get("custom_dob", ""),
        "country": response.get("custom_country", ""),
        "custom_academic_level": response.get("al_title", ""),
        "entry_date": response.get("custom_entry_date", ""),

    }

    # Agregar datos demográficos al base_row
    for demographic_id in demographics_map.keys():
        base_row[demographic_id] = ""

    user_demographics = demographics_data.get(evaluatee, {})
    for demographic_id in user_demographics:
        base_row[demographic_id] = user_demographics[demographic_id]

    # Parsear respuestas
    response_json = response.get("response_json", "{}")
    parsed_responses = parse_response_json(response_json)

    # Obtener información de la encuesta para lógica de tema
    company_name = survey_status.get("company_name", "")
    template_name = survey_status.get("template_name", "")

    # Crear una fila por cada pregunta
    rows = []
    for qid, question_label in question_map.items():
        row = base_row.copy()
        row["question"] = question_label
        row["answer"] = parsed_responses.get(qid, "")

        # Agregar variable y tema
        question_info = question_variables_map.get(question_label, {})
        variable = question_info.get("variable", "")
        row["variable"] = variable

        # Determinar el tema según el template y la compañía
        tema = ""
        if template_name == "Plantilla Modelo Vedanta bienestar":
            tema = VEDANTA_BIENESTAR.get(variable, "")
        else:
            tema = question_info.get("tema", "")

        # Lógica especial para empresas Carvajal
        try:
            company_name_val = (company_name or "").lower().strip()
            carvajal_names = {n.lower().strip() for n in CARVAJAL_COMPANIES.values()}
            if company_name_val and company_name_val in carvajal_names:
                tema = "CULTURA CARVAJAL"
        except Exception:
            pass

        row["theme"] = tema
        rows.append(row)

    return rows


def parse_response_json(response_json):
    """
    Parsea el JSON de respuestas de manera segura
    """
    if not response_json:
        return {}

    try:
        if isinstance(response_json, str):
            return json.loads(response_json)
        elif isinstance(response_json, dict):
            return response_json
        else:
            return {}
    except (json.JSONDecodeError, TypeError):
        frappe.log_error(f"Error parsing response JSON: {response_json}")
        return {}


def get_question_labels(survey_json):
    if not survey_json:
        return {}

    try:
        data = json.loads(survey_json) if isinstance(survey_json, str) else survey_json
    except (json.JSONDecodeError, TypeError):
        frappe.log_error(f"Error parsing survey JSON: {survey_json}")
        return {}

    mapping = {}
    pages = data.get("pages", []) if isinstance(data, dict) else []

    for page in pages:
        elements = page.get("elements", []) if isinstance(page, dict) else []
        for element in elements:
            if isinstance(element, dict):
                name = element.get("name")
                title = element.get("title", name)
                if name:
                    mapping[name] = title or name

    return mapping


def get_demographics_labels_by_status(survey_status, survey_name):
    """
    Obtiene las etiquetas de los campos demográficos según el estado de la encuesta.
    Si está en históricos, busca en ContactDetailHistoric para ese survey_id.
    Si no, busca en ContactAdditionalDetail para los usuarios de esa encuesta.
    """
    is_historical = survey_status.get("in_history") == 1

    if is_historical:
        survey_id = survey_status.get("survey_id", "")
        return get_demographics_labels_from_historic(survey_id)
    else:
        # Obtener usuarios de esta encuesta específica
        users_list = get_survey_users(survey_name)
        return get_demographics_labels(users_list)


def get_survey_users(survey_name):
    """
    Obtiene la lista de usuarios únicos que respondieron una encuesta.
    """
    try:
        query = """
            SELECT DISTINCT sr.user
            FROM `tabSurvey Response` sr
            WHERE sr.survey = %s AND sr.user IS NOT NULL
        """
        results = frappe.db.sql(query, survey_name, as_dict=True)
        return [r.user for r in results]
    except Exception as e:
        frappe.log_error(f"Error getting survey users: {str(e)}")
        return []


def get_demographics_labels_from_historic(survey_id):
    """
    Obtiene las etiquetas de los campos demográficos que tienen al menos un valor
    en ContactDetailHistoric para un survey_id específico.
    """
    if not survey_id:
        return {}

    try:
        query = """
            SELECT DISTINCT
                cdh.cdh_tag as demographic_tag, 
                cdh.cdh_demographic_type as demographic_id
            FROM `tabqp_IQ_ContactDetailHistoric` cdh
            INNER JOIN `tabqp_IQ_SurveyHistoricData` shd ON shd.name = cdh.parent
            WHERE shd.shd_survey_id = %s
        """
        results = frappe.db.sql(query, survey_id, as_dict=True)

        mapping = {}
        for row in results:
            mapping[row.demographic_id] = row.demographic_tag

        return mapping

    except Exception as e:
        frappe.log_error(f"Error getting demographics labels from historic: {str(e)}")
        return {}


def get_demographics_labels(users_list):
    """
    Obtiene las etiquetas de los campos demográficos que tienen al menos un valor
    en ContactAdditionalDetail para una lista específica de usuarios.
    """
    if not users_list:
        return {}

    try:
        users_placeholder = ", ".join(["%s"] * len(users_list))
        query = f"""
            SELECT DISTINCT
                cad.cad_tag as demographic_tag, 
                cad.cad_demographic_type as demographic_id
            FROM `tabqp_IQ_ContactAdditionalDetail` cad
            WHERE cad.parent IN ({users_placeholder})
        """
        results = frappe.db.sql(query, users_list, as_dict=True)

        mapping = {}
        for row in results:
            mapping[row.demographic_id] = row.demographic_tag

        return mapping

    except Exception as e:
        frappe.log_error(f"Error getting demographics labels: {str(e)}")
        return {}


def get_bulk_demographics(users_list, demographics_map):

    if not users_list or not demographics_map:
        return {}

    users_placeholder = ", ".join(["%s"] * len(users_list))

    query = f"""
        SELECT 
            c.name,
            cad.cad_demographic_type as cad_tag,
            cad.cad_value
        FROM `tabContact` c
        INNER JOIN `tabqp_IQ_ContactAdditionalDetail` cad ON cad.parent = c.name
        WHERE c.name IN ({users_placeholder})
    """

    params = users_list

    try:
        results = frappe.db.sql(query, params, as_dict=True)
    except Exception as e:
        frappe.log_error(f"Error in bulk demographics query: {str(e)}")
        return {}

    demographics_data = {}
    for result in results:
        user = result.get("name")
        tag = result.get("cad_tag")
        value = result.get("cad_value")

        if user and tag and value:
            if user not in demographics_data:
                demographics_data[user] = {}
            demographics_data[user][tag] = value

    return demographics_data


def get_question_variables_map():
    """
    Obtiene el mapeo de preguntas a sus variables (tags) y temas
    """
    try:
        query = """
            SELECT 
                a.name as question_id,
                a.qn_statement as question_text,
                b.dt_title as variable,
                b.dt_title as tag
            FROM `tabqp_IQ_Question` a
            INNER JOIN `tabqp_IQ_DemographicType` b ON a.qn_demographic = b.name
            WHERE b.dt_object_type = 'Pregunta'
        """
        results = frappe.db.sql(query, as_dict=True)

        mapping = {}
        for row in results:
            question_text = row.get("question_text", "")
            variable = row.get("variable", "")

            if question_text:
                # Determinar el tema basado en CATEGORIES
                tema = CATEGORIES.get(variable, "")

                # Si la variable es "Índice de Engagement", sobreescribir con tema específico
                if variable == "Índice de Engagement":
                    tema = TEMAS_INDICE_DE_ENGAGEMENT.get(question_text, "")

                mapping[question_text] = {"variable": variable, "tema": tema}

        return mapping
    except Exception as e:
        frappe.log_error(f"Error getting question variables map: {str(e)}")
        return {}


def get_user_email(user):
    if not user:
        return ""
    try:
        email = frappe.db.get_value("Contact", user, "email_id")
        return email or ""
    except Exception as e:
        frappe.log_error(f"Error getting email for user {user}: {str(e)}")
        return ""
    
def get_user_id(user):
    if not user:
        return ""
    try:
        user_id = frappe.db.get_value("Contact", user, "custom_document_number")
        return user_id or ""
    except Exception as e:
        frappe.log_error(f"Error getting ID for user {user}: {str(e)}")
        return ""

def get_relation(survey_name, evaluator, evaluatee):
  try:
      survey_id = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "name")
      relation = frappe.db.get_value("qp_IQ_SurveyRecipient", {"sr_evaluating_to": evaluator, "sr_contact": evaluatee, "sr_survey": survey_id}, "sr_evaluation_role")
      return relation or ""
  except Exception as e:      
    frappe.log_error(f"Error getting relation for survey {survey_name}, evaluator {evaluator}, evaluatee {evaluatee}: {str(e)}")
    return ""