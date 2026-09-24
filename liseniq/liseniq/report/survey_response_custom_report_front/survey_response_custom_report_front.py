# Copyright (c) 2013, Mentum Group and contributors
# For license information, please see license.txt

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
    "e34486d9ea": "Carvajal espacios"
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
    "Los líderes en esta organización me inspiran": "LOS LÍDERES"
}

def execute(filters=None):
    filters = filters or {}
    survey_name = filters.get('survey')

    if not frappe.db.exists("Survey", survey_name):
        frappe.throw(_("Encuesta no encontrada: {0}").format(survey_name))

    survey_doc = frappe.get_doc("Survey", survey_name)
    survey_json = getattr(survey_doc, "survey_json", "{}") or "{}"

    survey_status = get_survey_status(survey_name)
    is_anonymous = bool(survey_status.get('is_anonymous'))

    question_map = get_question_labels(survey_name)

    # En encuestas anónimas no hay contacto asociado, así que no hay demográficos
    if is_anonymous:
        demographics_map = {}
    else:
        # Obtener demographics_map basado en los usuarios específicos de esta encuesta
        demographics_map = get_demographics_labels_by_status(survey_status, survey_name)

    columns = build_columns(demographics_map, is_anonymous)

    data = get_survey_data(survey_name, question_map, demographics_map, survey_status)

    return columns, data


def get_survey_status(survey_name):
    """
    Obtiene el estado de la encuesta desde qp_IQ_Survey, incluyendo compañía, plantilla
    y si la encuesta es anónima (su_is_anonymous)
    """
    default = {
        'survey_id': '',
        'in_history': '',
        'company_id': '',
        'company_name': '',
        'template_id': '',
        'template_name': '',
        'is_anonymous': 0,
    }
    try:
        query = """
            SELECT 
                iq.name as survey_id,
                iq.su_in_history as in_history,
                iq.su_owner as company_id,
                c.co_name as company_name,
                iq.su_template as template_id,
                tp.tp_name as template_name,
                iq.su_is_anonymous as is_anonymous
            FROM `tabqp_IQ_Survey` iq
            LEFT JOIN `tabqp_IQ_Company` c ON c.name = iq.su_owner
            LEFT JOIN `tabqp_IQ_Template` tp ON tp.name = iq.su_template
            WHERE iq.su_name = %s
        """
        result = frappe.db.sql(query, survey_name, as_dict=True)
        if result:
            r = result[0]
            return {
                'survey_id': r.get('survey_id', ''),
                'in_history': r.get('in_history', ''),
                'company_id': r.get('company_id', ''),
                'company_name': r.get('company_name', ''),
                'template_id': r.get('template_id', ''),
                'template_name': r.get('template_name', ''),
                'is_anonymous': 1 if r.get('is_anonymous') else 0,
            }
        return default
    except Exception as e:
        frappe.log_error(f"Error getting survey status: {str(e)}")
        return default


def get_historical_survey_data(survey_id, question_map, demographics_map, is_anonymous=False):
    """
    Obtiene los datos históricos de una encuesta finalizada desde qp_IQ_SurveyHistoricData.
    Si la encuesta es anónima solo trae el id y las respuestas.
    """
    try:
        if is_anonymous:
            query = """
                SELECT 
                    shd.name,
                    shd.shd_measurement_response
                FROM `tabqp_IQ_SurveyHistoricData` shd
                WHERE shd.shd_survey_id = %s
            """
            return frappe.db.sql(query, survey_id, as_dict=True)

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


def build_question_rows(base_row, parsed_responses, question_map, question_variables_map):
    """
    Genera una fila por pregunta a partir de los datos base de la respuesta.
    El texto de la pregunta cae a question_map (qn_statement) y solo al ID como último recurso.
    Variable y tema quedan vacíos si la pregunta no los tiene.
    """
    rows = []
    for qid, question_label in question_map.items():
        question_info = question_variables_map.get(qid, {})
        row = base_row.copy()
        row['question'] = question_info.get('question_text') or question_label or qid
        row['answer'] = format_answer(parsed_responses.get(qid, ''))
        row['variable'] = question_info.get('variable') or ''
        row['theme'] = question_info.get('tema') or ''
        rows.append(row)
    return rows


def process_historical_response_row(hist_record, question_map, demographics_map, survey_status, question_variables_map):
    """
    Procesa un registro histórico de respuesta y retorna múltiples filas (una por pregunta)
    """
    is_anonymous = bool(survey_status.get('is_anonymous'))

    # Datos base del registro histórico que se repiten en cada fila
    base_row = {'name': hist_record.get('name', '')}

    if not is_anonymous:
        base_row.update({
            'gender': hist_record.get('shd_gender', ''),
            'custom_dob': hist_record.get('shd_dob', ''),
            'country': hist_record.get('shd_country', ''),
            'custom_academic_level': hist_record.get('academic_level', ''),
            'entry_date': hist_record.get('shd_entry_date', ''),
        })

        # Inicializar campos demográficos
        for demographic_id in demographics_map.keys():
            base_row[demographic_id] = ''

        # Sobrescribir con los valores del registro histórico
        demographics_data_str = hist_record.get('demographics_data', '')
        if demographics_data_str:
            for demo_pair in demographics_data_str.split('||'):
                if ':' in demo_pair:
                    demo_type, demo_value = demo_pair.split(':', 1)
                    base_row[demo_type] = demo_value

    # Procesar respuestas de la encuesta
    parsed_responses = parse_response_json(hist_record.get('shd_measurement_response', '{}'))

    return build_question_rows(base_row, parsed_responses, question_map, question_variables_map)


def build_columns(demographics_map, is_anonymous=False):
    """
    Construye las columnas del reporte de manera dinámica.
    En encuestas anónimas se omiten las columnas de género, país, etc.
    """
    columns = [
        {
            "label": _("ID Respuesta"),
            "fieldname": "name",
            "fieldtype": "Data",
            "width": 150
        },
    ]

    if not is_anonymous:
        columns += [
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

    # Agregar columnas de Pregunta y Respuesta al final
    columns.append({
        "label": _("Pregunta"),
        "fieldname": "question",
        "fieldtype": "Data",
        "width": 300
    })
    columns.append({
        "label": _("Variable"),
        "fieldname": "variable",
        "fieldtype": "Data",
        "width": 200
    })
    columns.append({
        "label": _("Tema"),
        "fieldname": "theme",
        "fieldtype": "Data",
        "width": 200
    })
    columns.append({
        "label": _("Respuesta"),
        "fieldname": "answer",
        "fieldtype": "Data",
        "width": 300
    })

    return columns


def get_survey_data(survey_name, question_map, demographics_map, survey_status):
    """
    Obtiene los datos de la encuesta de manera optimizada
    Ahora cada pregunta genera una fila separada
    """
    data = []
    is_anonymous = bool(survey_status.get('is_anonymous'))

    # Obtener mapeo de preguntas a variables y temas (solo las de esta encuesta)
    question_variables_map = get_question_variables_map(list(question_map.keys()))

    # Si la encuesta está finalizada, usar datos históricos
    if survey_status.get('in_history') == 1:
        survey_id = survey_status.get('survey_id', '')
        if survey_id:
            historical_data = get_historical_survey_data(survey_id, question_map, demographics_map, is_anonymous)
            for hist_record in historical_data:
                rows = process_historical_response_row(hist_record, question_map, demographics_map, survey_status, question_variables_map)
                data.extend(rows)  # Ahora devuelve múltiples filas
            return data

    # Si no está finalizada, usar datos en tiempo real
    if is_anonymous:
        query = """
            SELECT 
                sr.name,
                sr.user,
                sr.response_json
            FROM `tabSurvey Response` sr
            WHERE sr.survey = %s
            ORDER BY sr.creation DESC
        """
    else:
        query = """
            SELECT 
                sr.name,
                sr.user,
                sr.response_json,
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

    demographics_data = {}
    if not is_anonymous:
        users_list = [r.user for r in responses if r.user]
        demographics_data = get_bulk_demographics(users_list, demographics_map) if users_list else {}

    for response in responses:
        rows = process_response_row(response, question_map, demographics_map, demographics_data, survey_status, question_variables_map)
        data.extend(rows)  # Ahora devuelve múltiples filas

    return data


def process_response_row(response, question_map, demographics_map, demographics_data, survey_status, question_variables_map):
    """
    Procesa una respuesta individual y retorna múltiples filas (una por pregunta)
    """
    is_anonymous = bool(survey_status.get('is_anonymous'))

    base_row = {'name': response.get('name', '')}

    if not is_anonymous:
        user = response.get('user', '')
        base_row.update({
            'gender': response.get('gender', ''),
            'custom_dob': response.get('custom_dob', ''),
            'country': response.get('custom_country', ''),
            'custom_academic_level': response.get('al_title', ''),
            'entry_date': response.get('custom_entry_date', ''),
        })

        # Agregar datos demográficos al base_row
        for demographic_id in demographics_map.keys():
            base_row[demographic_id] = ''

        user_demographics = demographics_data.get(user, {})
        for demographic_id in user_demographics:
            base_row[demographic_id] = user_demographics[demographic_id]

    # Parsear respuestas
    parsed_responses = parse_response_json(response.get('response_json', '{}'))

    return build_question_rows(base_row, parsed_responses, question_map, question_variables_map)


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

def format_answer(value):
    if value is None:
        return ''
    if isinstance(value, (list, tuple)):
        return '; '.join(str(v) for v in value if v not in (None, ''))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return value

def get_question_labels(survey_name):
    if not survey_name:
        return {}
    template_name = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "su_template")
    template = frappe.get_doc("qp_IQ_Template", template_name)

    questions = frappe.get_all(
        "qp_IQ_TemplateQuestion",
        filters={"parent": template.name},
        fields=["tq_question"],
        order_by="idx asc",
    )

    question_labels = {}
    for question in questions:
        question_label = frappe.db.get_value("qp_IQ_Question", question.tq_question, "qn_statement")
        question_labels[question.tq_question] = question_label

    return question_labels


def get_demographics_labels_by_status(survey_status, survey_name):
    """
    Obtiene las etiquetas de los campos demográficos según el estado de la encuesta.
    Si está en históricos, busca en ContactDetailHistoric para ese survey_id.
    Si no, busca en ContactAdditionalDetail para los usuarios de esa encuesta.
    """
    is_historical = survey_status.get('in_history') == 1
    
    if is_historical:
        survey_id = survey_status.get('survey_id', '')
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
        users_placeholder = ', '.join(['%s'] * len(users_list))
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

    users_placeholder = ', '.join(['%s'] * len(users_list))
    
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
        user = result.get('name')
        tag = result.get('cad_tag')
        value = result.get('cad_value')
        
        if user and tag and value:
            if user not in demographics_data:
                demographics_data[user] = {}
            demographics_data[user][tag] = value

    return demographics_data

def get_question_variables_map(question_ids=None):
    """
    Obtiene el mapeo de preguntas a sus variables (tags) y temas.
    Usa LEFT JOIN real: las preguntas sin variable ni tema se incluyen igual
    (con variable/tema vacíos). Si se pasan question_ids, solo trae esas preguntas.
    """
    try:
        conditions = ""
        params = None
        if question_ids:
            placeholders = ', '.join(['%s'] * len(question_ids))
            conditions = f"WHERE a.name IN ({placeholders})"
            params = list(question_ids)

        query = f"""
            SELECT 
                a.name as question_id,
                a.qn_statement as question_text,
                b.dt_title as variable,
                c.dt_title as tema
            FROM `tabqp_IQ_Question` a
            LEFT JOIN `tabqp_IQ_DemographicType` b 
                ON b.name = a.qn_demographic AND b.dt_object_type = 'Pregunta'
            LEFT JOIN `tabqp_IQ_DemographicType` c ON c.name = a.qp_topic
            {conditions}
        """
        results = frappe.db.sql(query, params, as_dict=True)

        mapping = {}
        for row in results:
            mapping[row.get('question_id', '')] = {
                'question_text': row.get('question_text', ''),
                'variable': row.get('variable', '') or '',
                'tema': row.get('tema', '') or '',
            }

        return mapping
    except Exception as e:
        frappe.log_error(f"Error getting question variables map: {str(e)}")
        return {}