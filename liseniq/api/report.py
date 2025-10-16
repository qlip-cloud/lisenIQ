import json
import frappe
from frappe import _


CATEGORIES = {
    "Sentido de propósito": "MI INSPIRACIÓN",
    "Trabajo trascendental": "MI INSPIRACIÓN",
    "Me Conocen": "MI INSPIRACIÓN",
    "Mi lider": "LOS LÍDERES",
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
    "Logros": "COMPETITIVA",
    "Liderazgo": "COMPETITIVA",
    "Integridad": "CULTURA CARVAJAL",
    "Respeto": "CULTURA CARVAJAL",
    "Orientación al cliente": "CULTURA CARVAJAL",
    "Compromiso social": "CULTURA CARVAJAL",
    "Protección y cuidado de la vida": "CULTURA CARVAJAL",
    "Compromiso con los resultados": "CULTURA CARVAJAL"
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


    data = get_all_survey_data(valid_surveys, all_questions_map, demographics_map)
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


def get_all_survey_data(valid_surveys, all_questions_map, demographics_map):
    """
    Obtiene los datos de todas las encuestas válidas
    """
    if not valid_surveys:
        return []
    
    # Crear mapeo de survey_name a company_name e id
    survey_company_map = {
        survey['survey_name']: survey['company_name'] or ''
        for survey in valid_surveys
    }
    survey_id_map = {
        survey['survey_name']: survey['id']
        for survey in valid_surveys
    }
    
    # Obtener nombres de encuestas válidas
    survey_names = [survey['survey_name'] for survey in valid_surveys]
    survey_ids = [survey['id'] for survey in valid_surveys]
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
            survey_company_map,
            survey_id_map
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

def process_response_row(response, all_questions_map, demographics_data, survey_company_map, survey_id_map):
    """
    Procesa una fila individual de respuesta
    """
    user = response.get('user', '')
    survey_name = response.get('survey', '')
    
    # Datos básicos
    row = {
        'survey_id': survey_id_map.get(survey_name, ''),
        'survey_name': survey_name,
        'company_name': survey_company_map.get(survey_name, ''),
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

    # Inicializar todas las preguntas con valores vacíos
    for qid in all_questions_map.keys():
        row[qid] = ''
    
    # Llenar solo las preguntas que tienen respuesta
    for qid, answer in parsed_responses.items():
        if qid in all_questions_map:
            row[qid] = answer

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
                tema = CATEGORIES.get(variable, '')
                mapping[question_text] = {
                    'variable': variable,
                    'tema': tema
                }
                
        return mapping
        
    except Exception as e:
        frappe.log_error(f"Error getting question variables map: {str(e)}")
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
    

    question_ids = set(all_questions_map.keys())
    demographic_ids = set(demographics_map.keys())
    
    # campos demográficos base que siempre deberían aparecer
    core_demographic_keys = [
        'survey_id', 'survey_name', 'company_name', 'first_name', 'last_name',
        'custom_dob', 'gender', 'custom_academic_level', 'entry_date', 'country'
    ]

    question_variables_map = get_question_variables_map()

    # conjunto total de claves demográficas (ids sin traducir)
    required_demographic_keys = set(core_demographic_keys) | set(demographic_ids)

    for row in data:
        demographic_data = {}
        question_responses = {}

        # separar respuestas de preguntas del resto
        for key, value in row.items():
            if key in question_ids and value not in (None, ''):
                question_responses[key] = value
            else:
                demographic_data[key] = value

        # Asegurar que todas las claves demográficas estén presentes (aunque sean None)
        for dem_key in required_demographic_keys:
            if dem_key not in demographic_data:
                demographic_data[dem_key] = None

        for qid, answer in question_responses.items():
            question_object = demographic_data.copy()

            # usar el texto de la pregunta para 'question'
            question_text = all_questions_map.get(qid, qid)
            question_object['question'] = question_text
            question_object['answer'] = answer

            # Agregar variable y tema basado en la pregunta
            question_info = question_variables_map.get(question_text, {})
            question_object['variable'] = question_info.get('variable', '')
            question_object['tema'] = question_info.get('tema', '')

            transformed_data.append(question_object)
    
    return transformed_data
