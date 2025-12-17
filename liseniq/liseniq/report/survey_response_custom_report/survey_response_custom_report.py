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
    
    # Verificar si la encuesta está finalizada
    survey_status = get_survey_status(survey_name)
    data = get_survey_data(survey_name, question_map, demographics_map, survey_status)

    return columns, data


def get_survey_status(survey_name):
    """
    Obtiene el estado de la encuesta desde qp_IQ_Survey
    """
    try:
        query = """
            SELECT 
                iq.name as survey_id,
                iq.su_in_history as in_history
            FROM `tabqp_IQ_Survey` iq
            WHERE iq.su_name = %s
        """
        result = frappe.db.sql(query, survey_name, as_dict=True)
        if result:
            return {
                'survey_id': result[0].get('survey_id', ''),
                'in_history': result[0].get('in_history', '')
            }
        return {'survey_id': '', 'in_history': ''}
    except Exception as e:
        frappe.log_error(f"Error getting survey status: {str(e)}")
        return {'survey_id': '', 'in_history': ''}


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
                shd.shd_academic_level,
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
            WHERE shd.shd_survey_id = %s
            GROUP BY shd.name
        """
        results = frappe.db.sql(query, survey_id, as_dict=True)
        return results
    except Exception as e:
        frappe.log_error(f"Error getting historical survey data: {str(e)}")
        return []


def process_historical_response_row(hist_record, question_map, demographics_map):
    """
    Procesa un registro histórico de respuesta
    """
    row = {
        'custom_document_number': hist_record.get('shd_document_number', ''),
        'first_name': hist_record.get('shd_contact_name', '').split()[0] if hist_record.get('shd_contact_name') else '',
        'last_name': ' '.join(hist_record.get('shd_contact_name', '').split()[1:]) if hist_record.get('shd_contact_name') else '',
        'name': hist_record.get('name', ''),
        'gender': hist_record.get('shd_gender', ''),
        'custom_dob': hist_record.get('shd_dob', ''),
        'country': hist_record.get('shd_country', ''),
        'custom_academic_level': hist_record.get('shd_academic_level', ''),
        'entry_date': hist_record.get('shd_entry_date', ''),
    }

    # Procesar datos demográficos del registro histórico
    demographics_data_str = hist_record.get('demographics_data', '')
    if demographics_data_str:
        for demo_pair in demographics_data_str.split('||'):
            if ':' in demo_pair:
                demo_id, demo_value = demo_pair.split(':', 1)
                if demo_id in demographics_map:
                    row[demo_id] = demo_value

    # Procesar respuestas de la encuesta
    response_json = hist_record.get('shd_measurement_response', '{}')
    parsed_responses = parse_response_json(response_json)
    
    # Inicializar todas las preguntas con valores vacíos y llenar las que tienen respuesta
    for qid in question_map.keys():
        row[qid] = parsed_responses.get(qid, '')

    return row


def build_columns(question_map, demographics_map):
    """
    Construye las columnas del reporte de manera dinámica
    """
    columns = [
        {
            "label": _("Número de Identificación"),
            "fieldname": "custom_document_number",
            "fieldtype": "Data",
            "width": 150   
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
            "label": _("ID Respuesta"),
            "fieldname": "name",
            "fieldtype": "Data",
            "width": 150
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


def get_survey_data(survey_name, question_map, demographics_map, survey_status):
    """
    Obtiene los datos de la encuesta de manera optimizada
    """
    data = []
    
    # Si la encuesta está finalizada, usar datos históricos
    if survey_status.get('in_history') == 1:
        survey_id = survey_status.get('survey_id', '')
        if survey_id:
            historical_data = get_historical_survey_data(survey_id, question_map, demographics_map)
            for hist_record in historical_data:
                row = process_historical_response_row(hist_record, question_map, demographics_map)
                data.append(row)
            return data
    
    # Si no está finalizada, usar datos en tiempo real
    query = """
        SELECT 
            sr.name,
            sr.user,
            sr.response_json,
            c.custom_document_number,
            c.first_name,
            c.last_name,
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


    users_list = [r.user for r in responses if r.user]
    demographics_data = get_bulk_demographics(users_list, demographics_map) if users_list else {}

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
        'custom_document_number': response.get('custom_document_number', ''),
        'first_name': response.get('first_name', ''),
        'last_name': response.get('last_name', ''),
        'name': response.get('name', ''),
        'gender': response.get('gender', ''),
        'custom_dob': response.get('custom_dob', ''),
        'country': response.get('custom_country', ''),
        'custom_academic_level': response.get('al_title', ''),
        'entry_date': response.get('custom_entry_date', ''),
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
    que tienen al menos un valor en ContactAdditionalDetail.
    """
    try:
        query = """
            SELECT dem.name, dem.dt_title
            FROM `tabqp_IQ_DemographicType` dem
            WHERE dem.dt_object_type = 'Contacto'
            AND EXISTS (
                SELECT 1
                FROM `tabqp_IQ_ContactAdditionalDetail` cad
                WHERE cad.cad_demographic_type = dem.name
                LIMIT 1
            )
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
            c.name,
            cad.cad_demographic_type as cad_id,
            cad.cad_value
        FROM `tabContact` c
        INNER JOIN `tabqp_IQ_ContactAdditionalDetail` cad ON cad.parent = c.name
        WHERE c.name IN ({users_placeholder})
        AND cad.cad_demographic_type IN ({', '.join(['%s'] * len(demographics_map))})
    """
    
    params = users_list + list(demographics_map.keys())
    
    try:
        results = frappe.db.sql(query, params, as_dict=True)
    except Exception as e:
        frappe.log_error(f"Error in bulk demographics query: {str(e)}")
        return {}

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