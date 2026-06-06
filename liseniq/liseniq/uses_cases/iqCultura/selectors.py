import frappe


def get_all_responses_for_survey(survey_name):
    survey_doc = frappe.get_doc('qp_IQ_Survey', {'su_name': survey_name})
    in_history = survey_doc.su_in_history
    if not in_history:
        """Get all survey responses for a given survey"""
        responses = frappe.get_all(
            "Survey Response",
            filters={"survey": survey_name},
            fields=["*"]
        )
    else:
        """Get all survey responses for a given survey from history"""
        responses_historic = frappe.get_all(
            "qp_IQ_SurveyHistoricData",
            filters={"shd_survey_name": survey_name},
            fields=["*"]
        )
        responses = []
        for resp in responses_historic:
            survey_response = {
                "name": resp.name,
                "survey": resp.shd_survey_name,
                "user": resp.shd_contact_name,
                "creation": resp.creation,
                "modified": resp.modified,
                "response_json": resp.shd_measurement_response,
            }
            responses.append(survey_response)
 
    return responses


def get_survey_questions(survey_id):
    """Get all questions for a given survey"""
    questions = frappe.get_all(
        'qp_IQ_SurveyQuestion',
        filters={'parent': survey_id},
        fields=['sq_question']
    )
    return [q.sq_question for q in questions]


def get_question_metadata(survey_id):
    """Get metadata for all questions in a survey (text, dimension, theme)"""
    questions = get_survey_questions(survey_id)
    question_details = {}
    
    for question in questions:
        try:
            question_doc = frappe.get_doc('qp_IQ_Question', question)
            dimension = frappe.db.get_value(
                'qp_IQ_DemographicType',
                question_doc.qn_demographic,
                'dt_title'
            ) if question_doc.qn_demographic else None
            
            theme = frappe.db.get_value(
                'qp_IQ_DemographicType',
                question_doc.qp_topic,
                'dt_title'
            ) if question_doc.qp_topic else None
            
            question_details[question] = {
                'text': question_doc.qn_statement_others or question_doc.qn_statement,
                'dimension': dimension,
                'theme': theme,
            }
        except Exception:
            question_details[question] = {
                'text': question,
                'dimension': None,
                'theme': None,
            }
    
    return question_details


def get_respondents_by_demographic(survey_id, demographic_field):
    in_history = frappe.db.get_value('qp_IQ_Survey', survey_id, 'su_in_history')
    
    demographic_map = {}
    
    if not in_history:
        query = """
            SELECT 
                c.name, 
                IFNULL(cad.cad_value, 'Sin clasificar') as demographic_value
            FROM `tabContact` c
            INNER JOIN `tabqp_IQ_ContactAdditionalDetail` cad ON cad.parent = c.name
            INNER JOIN `tabqp_IQ_SurveyRecipient` sr ON sr.sr_contact = c.name
            WHERE sr.sr_survey = %s 
              AND cad.cad_demographic_type = %s
        """
        results = frappe.db.sql(query, (survey_id, demographic_field), as_dict=True)
        
    else:
        query = """
            SELECT 
                shd.shd_contact_name as name, 
                IFNULL(cdh.cdh_value, 'Sin clasificar') as demographic_value
            FROM `tabqp_IQ_SurveyHistoricData` shd
            INNER JOIN `tabqp_IQ_ContactDetailHistoric` cdh ON cdh.parent = shd.name
            INNER JOIN `tabqp_IQ_SurveyRecipient` sr ON sr.sr_contact = shd.shd_contact_name
            WHERE sr.sr_survey = %s 
              AND shd.shd_survey_id = %s
              AND cdh.cdh_demographic_type = %s
        """
        results = frappe.db.sql(query, (survey_id, survey_id, demographic_field), as_dict=True)

    if not results:
        return {}

    for contact in results:
        demo_val = contact.demographic_value
        if not demo_val or str(demo_val).strip() == "":
            demo_val = 'Sin clasificar'
            
        if demo_val not in demographic_map:
            demographic_map[demo_val] = []
        demographic_map[demo_val].append(contact.name)
    
    return demographic_map


def get_responses_by_respondent(survey_name):
    """
    Get all responses grouped by respondent/user
    Returns dict: {respondent_id: [responses]}
    """
    responses = get_all_responses_for_survey(survey_name)
    responses_by_respondent = {}
    
    for response in responses:
        if isinstance(response, dict):
            respondent = response.get('user') or response.get('name')
        else:
            respondent = response.user or response.name
        
        if respondent not in responses_by_respondent:
            responses_by_respondent[respondent] = []
        responses_by_respondent[respondent].append(response)
    
    return responses_by_respondent
