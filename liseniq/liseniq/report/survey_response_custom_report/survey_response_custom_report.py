# Copyright (c) 2013, Mentum Group and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _

def execute(filters=None):
    filters = filters or {}
    survey_name = filters.get('survey')
    

    if not frappe.db.exists("Survey", survey_name):
        frappe.throw(_("Encuesta no encontrada: {0}").format(survey_name))

    survey_doc = frappe.get_doc("Survey", survey_name)
    survey_json = getattr(survey_doc, "survey_json", "{}") or "{}"
    

    question_map = get_question_labels(survey_json)
    demographics_map = get_demographics_labels()

    columns = build_columns(question_map, demographics_map)
    
    data = get_survey_data(survey_name, question_map, demographics_map)

    return columns, data


def build_columns(question_map, demographics_map):
    """
    Construye las columnas del reporte de manera dinámica
    """
    columns = [
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
            "label": _("Fecha de Nacimiento"),
            "fieldname": "custom_dob",
            "fieldtype": "Date",
            "width": 150
        },
        {
            "label": _("Nivel Académico"),
            "fieldname": "custom_academic_level",
            "fieldtype": "Data",
            "width": 200
        }
    ]

    for did, dtitle in demographics_map.items():
        columns.append({
            "label": dtitle or did,
            "fieldname": did,
            "fieldtype": "Data",
            "width": 200
        })

    for qid, title in question_map.items():
        columns.append({
            "label": title or qid,
            "fieldname": qid,
            "fieldtype": "Data",
            "width": 300
        })


    return columns


def get_survey_data(survey_name, question_map, demographics_map):
    """
    Obtiene los datos de la encuesta de manera optimizada
    """
    query = """
        SELECT 
            sr.name as response_name,
            sr.user,
            sr.response_json,
            c.first_name,
            c.last_name,
            c.custom_dob,
            c.custom_academic_level
        FROM `tabSurvey Response` sr
        LEFT JOIN `tabContact` c ON c.name = sr.user
        WHERE sr.survey = %s
        ORDER BY sr.creation DESC
    """
    
    responses = frappe.db.sql(query, (survey_name,), as_dict=True)
    
    if not responses:
        return []


    users_list = [r.user for r in responses if r.user]
    demographics_data = get_bulk_demographics(users_list, demographics_map) if users_list else {}

    data = []
    for response in responses:
        row = process_response_row(response, question_map, demographics_data)
        data.append(row)

    return data


def process_response_row(response, question_map, demographics_data):
    """
    Procesa una fila individual de respuesta
    """
    user = response.get('user', '')
    
    row = {
        'first_name': response.get('first_name', ''),
        'last_name': response.get('last_name', ''),
        'custom_dob': response.get('custom_dob', ''),
        'custom_academic_level': response.get('custom_academic_level', '')
    }

    response_json = response.get('response_json', '{}')
    parsed_responses = parse_response_json(response_json)
    
    for qid in question_map.keys():
        row[qid] = parsed_responses.get(qid, '')

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
            FROM `tabqp_IQ_DemographiqType` dem
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

    if not users_list or not demographics_map:
        return {}

    users_placeholder = ', '.join(['%s'] * len(users_list))
    
    query = f"""
        SELECT 
            c.user,
            cad.cad_tag,
            cad.cad_value
        FROM `tabContact` c
        INNER JOIN `tabCustom Additional Details` cad ON cad.parent = c.name
        WHERE c.user IN ({users_placeholder})
        AND cad.cad_tag IN ({', '.join(['%s'] * len(demographics_map))})
    """
    
    # Preparar parámetros para la consulta
    params = users_list + list(demographics_map.keys())
    
    try:
        results = frappe.db.sql(query, params, as_dict=True)
    except Exception as e:
        frappe.log_error(f"Error in bulk demographics query: {str(e)}")
        return {}

    demographics_data = {}
    for result in results:
        user = result.get('user')
        tag = result.get('cad_tag')
        value = result.get('cad_value')
        
        if user and tag and value:
            if user not in demographics_data:
                demographics_data[user] = {}
            demographics_data[user][tag] = value

    return demographics_data