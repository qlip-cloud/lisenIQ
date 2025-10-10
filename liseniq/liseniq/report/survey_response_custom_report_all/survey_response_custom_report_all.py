# Copyright (c) 2013, Mentum Group and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _

def execute(filters=None):
    """
    Reporte de todas las encuestas con preguntas únicas y datos demográficos
    """
    filters = filters or {}
    
    # Obtener todas las encuestas válidas
    valid_surveys = get_valid_surveys()
    
    if not valid_surveys:
        frappe.throw(_("No se encontraron encuestas válidas en qp_IQ_Survey"))

    # Obtener todas las preguntas únicas de todas las encuestas
    all_questions_map = get_all_unique_questions(valid_surveys)
    demographics_map = get_demographics_labels()

    # Construir columnas dinámicamente
    columns = build_columns(all_questions_map, demographics_map)
    
    # Obtener datos de todas las encuestas
    data = get_all_survey_data(valid_surveys, all_questions_map, demographics_map)

    return columns, data


def get_valid_surveys():
    try:
        query = """
            SELECT 
                s.name as survey_name,
                s.survey_json,
                iq.su_name,
                iq.su_owner,
                c.co_name as company_name
            FROM `tabSurvey` s
            INNER JOIN `tabqp_IQ_Survey` iq ON iq.su_name = s.name
            LEFT JOIN `tabqp_IQ_Company` c ON c.name = iq.su_owner
            ORDER BY s.name
        """
        results = frappe.db.sql(query, as_dict=True)
        return results
    except Exception as e:
        frappe.log_error(f"Error getting valid surveys: {str(e)}")
        return []


def get_all_unique_questions(valid_surveys):
    """
    Obtiene todas las preguntas únicas de todas las encuestas válidas
    """
    all_questions = {}
    
    for survey in valid_surveys:
        survey_json = survey.get('survey_json', '{}')
        questions = get_question_labels(survey_json)
        
        # Agregar preguntas que no existan ya
        for qid, title in questions.items():
            if qid not in all_questions:
                all_questions[qid] = title
    
    return all_questions


def build_columns(all_questions_map, demographics_map):
    """
    Construye las columnas del reporte de manera dinámica
    """
    columns = [
        {
            "label": _("Survey"),
            "fieldname": "survey_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Compañía"),
            "fieldname": "company_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Nombre"),
            "fieldname": "first_name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Apellidos"),
            "fieldname": "last_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Género"),
            "fieldname": "gender",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Fecha de Nacimiento"),
            "fieldname": "custom_dob",
            "fieldtype": "Date",
            "width": 150
        },
        {
            "label": _("País"),
            "fieldname": "country",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Nivel Académico"),
            "fieldname": "custom_academic_level",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Fecha de Ingreso"),
            "fieldname": "entry_date",
            "fieldtype": "Date",
            "width": 150
        },
    ]

    # Agregar columnas demográficas
    for did, dtitle in demographics_map.items():
        columns.append({
            "label": dtitle or did,
            "fieldname": did,
            "fieldtype": "Data",
            "width": 200
        })

    # Agregar todas las preguntas únicas
    for qid, title in all_questions_map.items():
        columns.append({
            "label": title or qid,
            "fieldname": qid,
            "fieldtype": "Data",
            "width": 300
        })

    return columns


def get_all_survey_data(valid_surveys, all_questions_map, demographics_map):
    """
    Obtiene los datos de todas las encuestas válidas
    """
    if not valid_surveys:
        return []
    
    # Crear mapeo de survey_name a company_name
    survey_company_map = {
        survey['survey_name']: survey['company_name'] or ''
        for survey in valid_surveys
    }
    
    # Obtener nombres de encuestas válidas
    survey_names = [survey['survey_name'] for survey in valid_surveys]
    survey_names_placeholder = ', '.join(['%s'] * len(survey_names))
    
    query = f"""
        SELECT 
            sr.name,
            sr.user,
            sr.survey,
            sr.response_json,
            c.first_name,
            c.last_name,
            c.custom_dob,
            c.gender,
            c.custom_entry_date,
            c.country,
            a.al_title
        FROM `tabSurvey Response` sr
        LEFT JOIN `tabContact` c ON c.name = sr.user
        LEFT JOIN `tabqp_IQ_AcademicLevel` a ON a.name = c.custom_academic_level
        WHERE sr.survey IN ({survey_names_placeholder})
        ORDER BY sr.survey, sr.creation DESC
    """
    
    responses = frappe.db.sql(query, survey_names, as_dict=True)
    
    if not responses:
        return []

    # Obtener datos demográficos para todos los usuarios
    users_list = [r.user for r in responses if r.user]
    demographics_data = get_bulk_demographics(users_list, demographics_map) if users_list else {}

    data = []
    for response in responses:
        row = process_response_row(
            response, 
            all_questions_map, 
            demographics_data,
            survey_company_map
        )
        data.append(row)

    return data


def process_response_row(response, all_questions_map, demographics_data, survey_company_map):
    """
    Procesa una fila individual de respuesta
    """
    user = response.get('user', '')
    survey_name = response.get('survey', '')
    
    # Datos básicos
    row = {
        'survey_name': survey_name,
        'company_name': survey_company_map.get(survey_name, ''),
        'first_name': response.get('first_name', ''),
        'last_name': response.get('last_name', ''),
        'gender': response.get('gender', ''),
        'custom_dob': response.get('custom_dob', ''),
        'country': response.get('country', ''),
        'custom_academic_level': response.get('al_title', ''),
        'entry_date': response.get('custom_entry_date', ''),
    }

    # Procesar respuestas de la encuesta
    response_json = response.get('response_json', '{}')
    parsed_responses = parse_response_json(response_json)
    
    # Inicializar todas las preguntas con valores vacíos
    for qid in all_questions_map.keys():
        row[qid] = ''
    
    # Llenar solo las preguntas que tienen respuesta
    for qid, answer in parsed_responses.items():
        if qid in all_questions_map:
            row[qid] = answer

    # Agregar datos demográficos adicionales
    user_demographics = demographics_data.get(user, {})
    for demographic_id in user_demographics:
        row[demographic_id] = user_demographics[demographic_id]

    return row


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
    """
    Extrae las etiquetas de las preguntas del JSON de la encuesta
    """
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


def get_demographics_labels():
    """
    Obtiene las etiquetas de los campos demográficos
    """
    try:
        query = """
            SELECT dem.name, dem.dt_title
            FROM `tabqp_IQ_DemographicType` dem
            WHERE dem.dt_object_type = 'Contacto'
            ORDER BY dem.name
        """
        results = frappe.db.sql(query, as_dict=True)
        
        mapping = {}
        for row in results:
            mapping[row.name] = row.dt_title or row.name
            
        return mapping
        
    except Exception as e:
        frappe.log_error(f"Error getting demographics labels: {str(e)}")
        return {}


def get_bulk_demographics(users_list, demographics_map):
    """
    Obtiene datos demográficos adicionales para múltiples usuarios de manera optimizada
    """
    if not users_list or not demographics_map:
        return {}

    users_placeholder = ', '.join(['%s'] * len(users_list))
    demographics_placeholder = ', '.join(['%s'] * len(demographics_map))
    
    query = f"""
        SELECT 
            c.name,
            cad.cad_demographic_type as cad_id,
            cad.cad_value
        FROM `tabContact` c
        INNER JOIN `tabqp_IQ_ContactAdditionalDetail` cad ON cad.parent = c.name
        WHERE c.name IN ({users_placeholder})
        AND cad.cad_demographic_type IN ({demographics_placeholder})
    """
    
    params = users_list + list(demographics_map.keys())
    
    try:
        results = frappe.db.sql(query, params, as_dict=True)
    except Exception as e:
        frappe.log_error(f"Error in bulk demographics query: {str(e)}")
        return {}

    # Organizar datos por usuario
    demographics_data = {}
    for result in results:
        user = result.get('name')
        tag = result.get('cad_id')
        value = result.get('cad_value')

        if user and tag and value:
            if user not in demographics_data:
                demographics_data[user] = {}
            demographics_data[user][tag] = value

    return demographics_data