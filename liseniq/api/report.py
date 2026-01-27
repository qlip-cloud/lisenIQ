import json
import frappe
from frappe import _
from datetime import datetime, timedelta

CATEGORIES = {
    "Sentido de propósito": "MI INSPIRACIÓN",
    "Trabajo trascendental": "MI INSPIRACIÓN",
    "Me Conocen": "MI INSPIRACIÓN",
    "Mi líder": "LOS LÍDERES",
    "Apoyo": "LOS LÍDERES",
    "Nuestros lideres": "LOS LÍDERES",
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

@frappe.whitelist()
def custom_report(filters=None):
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

    
    # Obtener datos de todas las encuestas
    data = get_all_survey_data(valid_surveys, all_questions_map, demographics_map)
    translated_data = translate_keys(data, all_questions_map, demographics_map)

    return translated_data


@frappe.whitelist()
def custom_report_by_question(filters=None):
    """
    Reporte de todas las encuestas donde cada pregunta está en un objeto separado
    con los datos demográficos repetidos
    """
    filters = filters or {}
    
    # Obtener todas las encuestas válidas
    valid_surveys = get_valid_surveys()
    
    if not valid_surveys:
        frappe.throw(_("No se encontraron encuestas válidas en qp_IQ_Survey"))

    # Obtener todas las preguntas únicas de todas las encuestas
    all_questions_map = get_all_unique_questions(valid_surveys)
    demographics_map = get_demographics_labels()


    data = get_all_survey_data_by_question(valid_surveys, all_questions_map, demographics_map)
    transformed_data = transform_data_by_question(data, all_questions_map, demographics_map)
    translated_data = translate_keys(transformed_data, all_questions_map, demographics_map)


    return translated_data

@frappe.whitelist()
def custom_report_by_question_engagement(filters=None):

    filters = filters or {}
    
    # Obtener todas las encuestas válidas
    valid_surveys = get_valid_engagement_surveys()
    
    if not valid_surveys:
        frappe.throw(_("No se encontraron encuestas válidas en qp_IQ_Survey"))

    # Obtener todas las preguntas únicas de todas las encuestas
    all_questions_map = get_all_unique_questions(valid_surveys)
    demographics_map = get_demographics_labels()


    data = get_all_survey_data_by_question(valid_surveys, all_questions_map, demographics_map)
    transformed_data = transform_data_by_question(data, all_questions_map, demographics_map)
    translated_data = translate_keys(transformed_data, all_questions_map, demographics_map)


    return translated_data

@frappe.whitelist()
def get_user_demographics():
    """
    Retorna un array de objetos con el id del usuario y sus demográficos asociados
    """
    try:
        query = """
            SELECT 
                cad.parent AS user_id,
                cad.cad_demographic_type AS demographic_id,
                cad.cad_value AS demographic_value
            FROM `tabqp_IQ_ContactAdditionalDetail` cad
            INNER JOIN `tabqp_IQ_DemographicType` dt ON dt.name = cad.cad_demographic_type
            WHERE dt.dt_object_type = 'Contacto'
        """
        results = frappe.db.sql(query, as_dict=True)
        
        demographics_map = get_demographics_labels()
        
        user_demographics_dict = {}
        for row in results:
            user_id = row['user_id']
            demographic_id = row['demographic_id']
            demographic_value = row['demographic_value']
            
            if user_id not in user_demographics_dict:
                user_demographics_dict[user_id] = {'user_id': user_id}
            
            # Traducir el demographic_id a su etiqueta legible
            demographic_label = demographics_map.get(demographic_id, demographic_id)
            user_demographics_dict[user_id][demographic_label] = demographic_value
        
        # Convertir el diccionario a un array de objetos
        user_demographics_array = list(user_demographics_dict.values())
        
        return user_demographics_array

    except Exception as e:
        frappe.log_error(f"Error getting user demographics: {str(e)}")
        return []

@frappe.whitelist()
def get_engagement_responses():
    """
    Retorna las respuestas de las encuestas de engagement sin demográficos
    """
    try:
        valid_surveys = get_valid_engagement_surveys()
        if not valid_surveys:
            return []

        all_questions_map = get_all_unique_questions(valid_surveys)
        demographics_map = get_demographics_labels()

        data = get_all_survey_data_by_question(valid_surveys, all_questions_map, demographics_map)
        transformed_data = transform_data_by_question(data, all_questions_map, demographics_map)
        
        # Definir las claves demográficas a excluir
        demographic_keys = set(demographics_map.keys())
        core_demographic_keys = {
            'first_name', 'last_name', 'custom_dob', 'gender', 
            'custom_academic_level', 'entry_date', 'country'
        }
        all_demographic_keys = demographic_keys | core_demographic_keys
        
        # Filtrar los demográficos de los datos transformados
        filtered_data = []
        for row in transformed_data:
            filtered_row = {k: v for k, v in row.items() if k not in all_demographic_keys}
            # Mantener user_id para poder relacionar con get_user_demographics
            if 'user_id' in row:
                filtered_row['user_id'] = row['user_id']
            filtered_data.append(filtered_row)
        
        # Traducir las claves restantes
        translated_data = translate_keys(filtered_data, all_questions_map, demographics_map)

        return translated_data

    except Exception as e:
        frappe.log_error(f"Error getting engagement responses: {str(e)}")
        return []
    
@frappe.whitelist()
def custom_report_by_question_yesterday(filters=None):
    """
    Reporte de las encuestas del día anterior donde cada pregunta está en un objeto separado
    con los datos demográficos repetidos
    """
    filters = filters or {}
    
    # Obtener todas las encuestas válidas
    valid_surveys = get_valid_surveys()
    
    if not valid_surveys:
        frappe.throw(_("No se encontraron encuestas válidas en qp_IQ_Survey"))

    # Obtener todas las preguntas únicas de todas las encuestas
    all_questions_map = get_all_unique_questions(valid_surveys)
    demographics_map = get_demographics_labels()

    # Obtener solo datos del día anterior
    data = get_survey_data_yesterday(valid_surveys, all_questions_map, demographics_map)
    transformed_data = transform_data_by_question(data, all_questions_map, demographics_map)
    translated_data = translate_keys(transformed_data, all_questions_map, demographics_map)

    return translated_data


def get_valid_surveys():
    try:
        query = """
            SELECT 
                s.name as survey_name,
                s.survey_json,
                iq.name as id,
                iq.su_name,
                iq.su_owner,
                iq.su_in_history as in_history,
                tp.tp_name as template_name,
                c.name as company_id,
                c.co_name as company_name
            FROM `tabSurvey` s
            INNER JOIN `tabqp_IQ_Survey` iq ON iq.su_name = s.name
            LEFT JOIN `tabqp_IQ_Company` c ON c.name = iq.su_owner
            LEFT JOIN `tabqp_IQ_Template` tp ON tp.name = iq.su_template
            LEFT JOIN `tabqp_IQ_QuestionCategory` st ON st.name = tp.tp_category
            WHERE LOWER(st.qnc_category) = 'cultura'
            ORDER BY s.name
        """
        results = frappe.db.sql(query, as_dict=True)
        return results
    except Exception as e:
        frappe.log_error(f"Error getting valid surveys: {str(e)}")
        return []

def get_valid_engagement_surveys():
    try:
        query = """
            SELECT 
                s.name as survey_name,
                s.survey_json,
                iq.name as id,
                iq.su_name,
                iq.su_owner,
                iq.su_in_history as in_history,
                tp.tp_name as template_name,
                c.name as company_id,
                c.co_name as company_name
            FROM `tabSurvey` s
            INNER JOIN `tabqp_IQ_Survey` iq ON iq.su_name = s.name
            LEFT JOIN `tabqp_IQ_Company` c ON c.name = iq.su_owner
            LEFT JOIN `tabqp_IQ_Template` tp ON tp.name = iq.su_template
            LEFT JOIN `tabqp_IQ_QuestionCategory` st ON st.name = tp.tp_category
            WHERE LOWER(st.qnc_category) = 'engagement'
            ORDER BY s.name
        """
        results = frappe.db.sql(query, as_dict=True)
        return results
    except Exception as e:
        frappe.log_error(f"Error getting valid engagement surveys: {str(e)}")
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


def get_surveys_expected_responses():
    query_survey = """
        SELECT
            s.su_name AS name,
            COUNT(DISTINCT srp.name) AS expected_responses
        FROM `tabqp_IQ_Survey` s
        LEFT JOIN `tabqp_IQ_Company` co ON co.name = s.su_owner
        LEFT JOIN `tabqp_IQ_SurveyRecipient` srp 
            ON srp.sr_survey = s.name
        LEFT JOIN `tabContact` c 
            ON c.name = srp.sr_contact
        GROUP BY s.su_name, s.su_owner 
        ORDER BY co.co_name, s.su_name
    """

    return frappe.db.sql(query_survey, as_dict=True)


def get_historical_survey_data(survey_id, all_questions_map, demographics_map):
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


def get_all_survey_data(valid_surveys, all_questions_map, demographics_map):
    """
    Obtiene los datos de todas las encuestas válidas
    """
    if not valid_surveys:
        return []
    
    # Crear mapeo de survey_name a company_name e id
    survey_company_map = {
        survey['survey_name']: {
            'company_id': survey.get('company_id', ''),
            'company_name': survey.get('company_name', '')
        }
        for survey in valid_surveys
    }
    survey_id_map = {
        survey['survey_name']: survey['id']
        for survey in valid_surveys
    }

    survey_expected_responses_map = {
        survey['name']: survey['expected_responses']
        for survey in get_surveys_expected_responses()
    }
    
    data = []
    
    # Separar encuestas finalizadas y no finalizadas
                # Usar el tema de question_variables_map (basado en CATEGORIES)
    finished_surveys = [s for s in valid_surveys if s.get('in_history') == 1]
    active_surveys = [s for s in valid_surveys if s.get('in_history') != 1]
    
    # Procesar encuestas finalizadas con datos históricos
    for survey in finished_surveys:
        historical_data = get_historical_survey_data(survey['id'], all_questions_map, demographics_map)
        for hist_record in historical_data:
            row = process_historical_response_row(
                hist_record,
                survey,
                all_questions_map,
                demographics_map,
                survey_company_map,
                survey_id_map,
                survey_expected_responses_map
            )
            data.append(row)
    
    # Procesar encuestas activas con datos en tiempo real
    if active_surveys:
        survey_names = [survey['survey_name'] for survey in active_surveys]
        survey_names_placeholder = ', '.join(['%s'] * len(survey_names))
        
        query = f"""
            SELECT 
                sr.name,
                sr.user,
                sr.survey,
                sr.response_json,
                c.custom_document_number,
                c.first_name,
                c.last_name,
                c.custom_dob,
                c.gender,
                c.custom_entry_date,
                c.custom_country,
                a.al_title
            FROM `tabSurvey Response` sr
            LEFT JOIN `tabContact` c ON c.name = sr.user
            LEFT JOIN `tabqp_IQ_AcademicLevel` a ON a.name = c.custom_academic_level
            WHERE sr.survey IN ({survey_names_placeholder})
            ORDER BY sr.survey, sr.creation DESC
        """
        
        responses = frappe.db.sql(query, survey_names, as_dict=True)
        
        if responses:
            # Obtener datos demográficos para todos los usuarios
            users_list = [r.user for r in responses if r.user]
            demographics_data = get_bulk_demographics(users_list, demographics_map) if users_list else {}

            for response in responses:
                row = process_response_row(
                    response, 
                    all_questions_map, 
                    demographics_data,
                    survey_company_map,
                    survey_id_map,
                    survey_expected_responses_map
                )
                data.append(row)

    return data

def get_all_survey_data_by_question(valid_surveys, all_questions_map, demographics_map):
    """
    Obtiene los datos de todas las encuestas válidas
    """
    if not valid_surveys:
        return []
    
    # Crear mapeo de survey_name a company_name, company_id y survey_id
    survey_company_map = {
        survey['survey_name']: {
            'company_id': survey.get('company_id', ''),
            'company_name': survey.get('company_name', '')
        }
        for survey in valid_surveys
    }
    survey_id_map = {
        survey['survey_name']: survey['id']
        for survey in valid_surveys
    }

    survey_expected_responses_map = {
        survey['name']: survey['expected_responses']
        for survey in get_surveys_expected_responses()
    }

    data = []
    
    # Separar encuestas finalizadas y no finalizadas
    finished_surveys = [s for s in valid_surveys if s.get('in_history') == 1]
    active_surveys = [s for s in valid_surveys if s.get('in_history') != 1]
    
    # Procesar encuestas finalizadas con datos históricos
    for survey in finished_surveys:
        historical_data = get_historical_survey_data(survey['id'], all_questions_map, demographics_map)
        for hist_record in historical_data:
            row = process_historical_response_row_by_question(
                hist_record,
                survey,
                all_questions_map,
                demographics_map,
                survey_company_map,
                survey_id_map,
                survey_expected_responses_map
            )
            data.append(row)
    
    # Procesar encuestas activas con datos en tiempo real
    if active_surveys:
        survey_names = [survey['survey_name'] for survey in active_surveys]
        survey_names_placeholder = ', '.join(['%s'] * len(survey_names))
        
        query = f"""
            SELECT 
                sr.name,
                sr.user,
                sr.survey,
                sr.response_json,
                c.custom_document_number,
                c.first_name,
                c.last_name,
                c.custom_dob,
                c.gender,
                c.custom_entry_date,
                c.custom_country,
                a.al_title
            FROM `tabSurvey Response` sr
            LEFT JOIN `tabContact` c ON c.name = sr.user
            LEFT JOIN `tabqp_IQ_AcademicLevel` a ON a.name = c.custom_academic_level
            WHERE sr.survey IN ({survey_names_placeholder})
            ORDER BY sr.survey, sr.creation DESC
        """
        
        responses = frappe.db.sql(query, survey_names, as_dict=True)
        
        if responses:
            # Obtener datos demográficos para todos los usuarios
            users_list = [r.user for r in responses if r.user]
            demographics_data = get_bulk_demographics(users_list, demographics_map) if users_list else {}

            for response in responses:
                row = process_response_row_by_question(
                    response, 
                    all_questions_map, 
                    demographics_data,
                    survey_company_map,
                    survey_id_map,
                    survey_expected_responses_map
                )
                data.append(row)

    return data

def get_survey_data_yesterday(valid_surveys, all_questions_map, demographics_map):
    """
    Obtiene los datos de las encuestas del día anterior
    """
    if not valid_surveys:
        return []
    
    # Calcular fecha del día anterior
    yesterday = datetime.now().date() - timedelta(days=1)
    yesterday_start = datetime.combine(yesterday, datetime.min.time())
    yesterday_end = datetime.combine(yesterday, datetime.max.time())
    
    # Crear mapeo de survey_name a company_name e id
    survey_company_map = {
        survey['survey_name']: {
            'company_id': survey.get('company_id', ''),
            'company_name': survey.get('company_name', '')
        }
        for survey in valid_surveys
    }
    survey_id_map = {
        survey['survey_name']: survey['id']
        for survey in valid_surveys
    }

    survey_expected_responses_map = {
        survey['name']: survey['expected_responses']
        for survey in get_surveys_expected_responses()
    }
    
    data = []
    
    # Separar encuestas finalizadas y no finalizadas
    finished_surveys = [s for s in valid_surveys if s.get('in_history') == 1]
    active_surveys = [s for s in valid_surveys if s.get('in_history') != 1]
    
    # Para encuestas finalizadas, obtener datos históricos (sin filtro de fecha, ya que son históricas)
    for survey in finished_surveys:
        historical_data = get_historical_survey_data(survey['id'], all_questions_map, demographics_map)
        for hist_record in historical_data:
            row = process_historical_response_row_by_question(
                hist_record,
                survey,
                all_questions_map,
                demographics_map,
                survey_company_map,
                survey_id_map,
                survey_expected_responses_map
            )
            data.append(row)
    
    # Para encuestas activas, aplicar filtro de fecha del día anterior
    if active_surveys:
        survey_names = [survey['survey_name'] for survey in active_surveys]
        survey_names_placeholder = ', '.join(['%s'] * len(survey_names))
        
        query = f"""
            SELECT 
                sr.name,
                sr.user,
                sr.survey,
                sr.response_json,
                c.custom_document_number,
                c.first_name,
                c.last_name,
                c.custom_dob,
                c.gender,
                c.custom_entry_date,
                c.custom_country,
                a.al_title
            FROM `tabSurvey Response` sr
            LEFT JOIN `tabContact` c ON c.name = sr.user
            LEFT JOIN `tabqp_IQ_AcademicLevel` a ON a.name = c.custom_academic_level
            WHERE sr.survey IN ({survey_names_placeholder})
            AND sr.creation >= %s
            AND sr.creation <= %s
            ORDER BY sr.survey, sr.creation DESC
        """
        
        params = survey_names + [yesterday_start, yesterday_end]
        responses = frappe.db.sql(query, params, as_dict=True)
        
        if responses:
            # Obtener datos demográficos para todos los usuarios
            users_list = [r.user for r in responses if r.user]
            demographics_data = get_bulk_demographics(users_list, demographics_map) if users_list else {}

            for response in responses:
                row = process_response_row_by_question(
                    response, 
                    all_questions_map, 
                    demographics_data,
                    survey_company_map,
                    survey_id_map,
                    survey_expected_responses_map
                )
                data.append(row)

    return data

def translate_keys(data, all_questions_map, demographics_map):
    """
    Traduce las claves de los datos a etiquetas legibles
    """
    if not data:
        return []

    translated_data = []
    for row in data:
        translated_row = {}
        for key, value in row.items():
            if key in all_questions_map:
                translated_key = all_questions_map[key]
            elif key in demographics_map:
                translated_key = demographics_map[key]
            else:
                translated_key = key  
            translated_row[translated_key] = value
        translated_data.append(translated_row)

    return translated_data

def process_historical_response_row(hist_record, survey, all_questions_map, demographics_map, survey_company_map, survey_id_map, survey_expected_responses_map):
    """
    Procesa un registro histórico de respuesta
    """
    survey_name = survey['survey_name']
    
    # Datos básicos desde el registro histórico
    company_data = survey_company_map.get(survey_name, {})
    row = {
        'survey_id': survey_id_map.get(survey_name, ''),
        'survey_name': survey_name,
        'company_id': company_data.get('company_id', ''),
        'company_name': company_data.get('company_name', ''),
        'survey_expected_responses': survey_expected_responses_map.get(survey_name, 0),
        'user_id': hist_record.get('shd_document_number', ''),
        'first_name': hist_record.get('shd_contact_name', '').split()[0] if hist_record.get('shd_contact_name') else '',
        'last_name': ' '.join(hist_record.get('shd_contact_name', '').split()[1:]) if hist_record.get('shd_contact_name') else '',
        'custom_dob': hist_record.get('shd_dob', ''),
        'gender': hist_record.get('shd_gender', ''),
        'custom_academic_level': hist_record.get('shd_academic_level', ''),
        'entry_date': hist_record.get('shd_entry_date', ''),
        'country': hist_record.get('shd_country', ''),
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
    
    # Agregar solo las preguntas que el usuario contestó
    for qid, answer in parsed_responses.items():
        if qid in all_questions_map and answer not in (None, ''):
            row[qid] = answer

    return row


def process_response_row(response, all_questions_map, demographics_data, survey_company_map, survey_id_map, survey_expected_responses_map):
    """
    Procesa una fila individual de respuesta
    """
    user = response.get('user', '')
    survey_name = response.get('survey', '')
    
    # Datos básicos
    company_data = survey_company_map.get(survey_name, {})
    row = {
        'survey_id': survey_id_map.get(survey_name, ''),
        'survey_name': survey_name,
        'company_id': company_data.get('company_id', ''),
        'company_name': company_data.get('company_name', ''),
        'survey_expected_responses': survey_expected_responses_map.get(survey_name, 0),
        'user_id': response.get('custom_document_number', ''),
        'first_name': response.get('first_name', ''),
        'last_name': response.get('last_name', ''),
        'custom_dob': response.get('custom_dob', ''),
        'gender': response.get('gender', ''),
        'custom_academic_level': response.get('al_title', ''),
        'entry_date': response.get('custom_entry_date', ''),
        'country': response.get('custom_country', ''),
    }

    # Procesar respuestas de la encuesta
    response_json = response.get('response_json', '{}')
    parsed_responses = parse_response_json(response_json)
    
    # Agregar datos demográficos adicionales
    user_demographics = demographics_data.get(user, {})
    for demographic_id in user_demographics:
        row[demographic_id] = user_demographics[demographic_id]

    # Agregar solo las preguntas que el usuario contestó (sin inicializar todas con '')
    for qid, answer in parsed_responses.items():
        if qid in all_questions_map and answer not in (None, ''):
            row[qid] = answer

    return row

def process_historical_response_row_by_question(hist_record, survey, all_questions_map, demographics_map, survey_company_map, survey_id_map, survey_expected_responses_map):
    """
    Procesa un registro histórico de respuesta (formato by_question)
    """
    survey_name = survey['survey_name']
    
    # Datos básicos desde el registro histórico
    company_data = survey_company_map.get(survey_name, {})
    row = {
        'survey_id': survey_id_map.get(survey_name, ''),
        'survey_name': survey_name,
        'company_id': company_data.get('company_id', ''),
        'company_name': company_data.get('company_name', ''),
        'survey_expected_responses': survey_expected_responses_map.get(survey_name, 0),
        'user_id': hist_record.get('shd_document_number', ''),
        'first_name': hist_record.get('shd_contact_name', '').split()[0] if hist_record.get('shd_contact_name') else '',
        'last_name': ' '.join(hist_record.get('shd_contact_name', '').split()[1:]) if hist_record.get('shd_contact_name') else '',
        'custom_dob': hist_record.get('shd_dob', ''),
        'gender': hist_record.get('shd_gender', ''),
        'custom_academic_level': hist_record.get('shd_academic_level', ''),
        'entry_date': hist_record.get('shd_entry_date', ''),
        'country': hist_record.get('shd_country', ''),
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
    
    # Guardar solo las respuestas válidas en una propiedad separada
    row['_responses'] = {}
    for qid, answer in parsed_responses.items():
        if qid in all_questions_map and answer not in (None, ''):
            row['_responses'][qid] = answer

    return row


def process_response_row_by_question(response, all_questions_map, demographics_data, survey_company_map, survey_id_map, survey_expected_responses_map):
    """
    Procesa una fila individual de respuesta
    """
    user = response.get('user', '')
    survey_name = response.get('survey', '')
    
    # Datos básicos
    company_data = survey_company_map.get(survey_name, {})
    row = {
        'survey_id': survey_id_map.get(survey_name, ''),
        'survey_name': survey_name,
        'company_id': company_data.get('company_id', ''),
        'company_name': company_data.get('company_name', ''),
        'survey_expected_responses': survey_expected_responses_map.get(survey_name, 0),
        'user_id': response.get('custom_document_number', ''),
        'first_name': response.get('first_name', ''),
        'last_name': response.get('last_name', ''),
        'custom_dob': response.get('custom_dob', ''),
        'gender': response.get('gender', ''),
        'custom_academic_level': response.get('al_title', ''),
        'entry_date': response.get('custom_entry_date', ''),
        'country': response.get('custom_country', ''),
    }

    # Procesar respuestas de la encuesta
    response_json = response.get('response_json', '{}')
    parsed_responses = parse_response_json(response_json)
    
    # Agregar datos demográficos adicionales
    user_demographics = demographics_data.get(user, {})
    for demographic_id in user_demographics:
        row[demographic_id] = user_demographics[demographic_id]

    # Guardar solo las respuestas válidas en una propiedad separada
    row['_responses'] = {}
    for qid, answer in parsed_responses.items():
        if qid in all_questions_map and answer not in (None, ''):
            row['_responses'][qid] = answer

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


def get_question_variables_map():
    """
    Obtiene el mapeo de preguntas a sus variables (tags) y temas
    """
    try:
        query = """
            SELECT 
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
            question_text = row.get('question_text', '')
            variable = row.get('variable', '')
            
            if question_text:
                """
                TODO: Para preguntas de mediciones de Carvajal, asignar tema "CULTURA CARVAJAL"
                basado en el mapeo de CATEGORIES
                """
                tema = CATEGORIES.get(variable, '')
                mapping[question_text] = {
                    'variable': variable,
                    'tema': tema
                }
                
        return mapping
        
    except Exception as e:
        frappe.log_error(f"Error getting question variables map: {str(e)}")
        return {}


def get_question_types_map():
    """
    Obtiene el mapeo de preguntas a sus tipos
    La clave del mapeo será el ID de la pregunta
    y el valor será el tipo de la pregunta
    """
    try:
        query = """
            SELECT 
                q.name as question_id,
                q.qn_statement as question_text,
                qt.qnt_type_name as question_type
            FROM `tabqp_IQ_Question` q
            LEFT JOIN `tabqp_IQ_QuestionType` qt ON qt.name = q.qn_type
        """
        results = frappe.db.sql(query, as_dict=True)
        
        mapping = {}
        for row in results:
            question_id = row.get('question_id', '')
            question_text = row.get('question_text', '')
            question_type = row.get('question_type', '')
            
            if question_id:
                mapping[question_id] = question_type or ''
                
        return mapping
        
    except Exception as e:
        frappe.log_error(f"Error getting question types map: {str(e)}")
        return {}

def get_survey_template_map():
    """
    Obtiene el mapeo de encuestas a sus plantillas
    La clave del mapeo será el nombre de la encuesta
    y el valor será el nombre de la plantilla
    """
    try:
        query = """
            SELECT 
                iq.su_name as survey_name,
                tp.tp_name as template_name
            FROM `tabqp_IQ_Survey` iq
            LEFT JOIN `tabqp_IQ_Template` tp ON tp.name = iq.su_template
        """
        results = frappe.db.sql(query, as_dict=True)
        
        mapping = {}
        for row in results:
            survey_name = row.get('survey_name', '')
            template_name = row.get('template_name', '')
            
            if survey_name:
                mapping[survey_name] = template_name or ''
                
        return mapping
        
    except Exception as e:
        frappe.log_error(f"Error getting survey template map: {str(e)}")
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


def transform_data_by_question(data, all_questions_map, demographics_map):
    """
    Transforma los datos para que cada pregunta esté en un objeto separado
    con los datos demográficos repetidos, usando claves 'question' y 'answer'
    (usa los IDs originales antes de traducir)
    """
    if not data:
        return []

    transformed_data = []
    
    demographic_ids = set(demographics_map.keys())
    
    # campos demográficos base que siempre deberían aparecer
    core_demographic_keys = [
        'survey_id', 'survey_name', 'company_id', 'company_name', 'first_name', 'last_name',
        'custom_dob', 'gender', 'custom_academic_level', 'entry_date', 'country'
    ]

    question_variables_map = get_question_variables_map()
    question_types_map = get_question_types_map()
    survey_template_map = get_survey_template_map()

    # conjunto total de claves demográficas (ids sin traducir)
    required_demographic_keys = set(core_demographic_keys) | set(demographic_ids)

    for row in data:
        # Extraer respuestas de la propiedad especial
        question_responses = row.get('_responses', {})
        
        # Preparar datos demográficos (sin _responses)
        demographic_data = {k: v for k, v in row.items() if k != '_responses'}

        # Asegurar que todas las claves demográficas estén presentes (aunque sean None)
        for dem_key in required_demographic_keys:
            if dem_key not in demographic_data:
                demographic_data[dem_key] = None

        # Si no hay respuestas, saltar este registro
        if not question_responses:
            continue

        # Obtener el template de la encuesta actual
        survey_name = demographic_data.get('survey_name', '')
        template_name = survey_template_map.get(survey_name, '')

        for qid, answer in question_responses.items():
            question_object = demographic_data.copy()

            question_text = all_questions_map.get(qid, qid)
            question_object['question_id'] = qid
            question_object['question'] = question_text
            question_object['answer'] = answer

            # Agregar variable y tema basado en la pregunta
            question_info = question_variables_map.get(question_text, {})
            variable = question_info.get('variable', '')
            question_object['variable'] = variable
            question_object['question_type'] = question_types_map.get(qid, '')
            
            # Determinar el tema según el template
            tema = ''
            if template_name == 'Plantilla Modelo Vedanta bienestar':
                tema = VEDANTA_BIENESTAR.get(variable, '')
            else:
                tema = question_info.get('tema', '')
                
            # Lógica especial para empresas Carvajal
            try:
                company_name_val = (demographic_data.get('company_name') or '').lower().strip()
                carvajal_names = {n.lower().strip() for n in CARVAJAL_COMPANIES.values()}
                if company_name_val and company_name_val in carvajal_names:
                    tema = "CULTURA CARVAJAL"
            except Exception:
                pass

            question_object['tema'] = tema

            transformed_data.append(question_object)
    
    return transformed_data
