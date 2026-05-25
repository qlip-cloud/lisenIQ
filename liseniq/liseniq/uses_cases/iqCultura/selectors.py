import frappe


def get_all_responses_for_survey(survey_name):
    """Get all survey responses for a given survey"""
    responses = frappe.get_all(
        "Survey Response",
        filters={"survey": survey_name},
        fields=["*"]
    )
 
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
    """
    Get unique values of a demographic field for respondents in a survey.
    Returns dict: {demographic_value: [respondent_ids]}
    
    Args:
        survey_id: ID of the survey
        demographic_field: Field name to group by (e.g., 'department', 'area')
    
    Returns:
        Dictionary mapping demographic values to lists of respondent IDs
    """

    survey_doc = frappe.get_doc('qp_IQ_Survey', survey_id)
    in_history = survey_doc.su_in_history
    # Get all recipients of the survey
    recipients = frappe.get_all(
        'qp_IQ_SurveyRecipient',
        filters={'sr_survey': survey_id},
        fields=['sr_contact', 'sr_survey']
    )
    
    if not recipients:
        return {}
    
    recipient_ids = [r.sr_contact for r in recipients]
    
    # Get demographic data from Contact
    demographic_map = {}
    if not in_history:
        query = """
        SELECT c.name, cad.cad_value as demographic_value
        FROM `tabContact` c
        INNER JOIN `tabqp_IQ_ContactAdditionalDetail` cad ON cad.parent = c.name
        INNER JOIN `tabqp_IQ_DemographicType` dt ON dt.name = cad.cad_demographic_type
        WHERE c.name IN ({}) AND cad.cad_demographic_type = %s
        """

        formatted_query = query.format(','.join(['%s'] * len(recipient_ids)))
    else:
        query = """
        SELECT shd.shd_contact_name as name, cdh.cdh_value as demographic_value
        FROM `tabqp_IQ_SurveyHistoricData` shd
        INNER JOIN `tabqp_IQ_ContactDetailHistoric` cdh ON cdh.parent = shd.name
        INNER JOIN `tabqp_IQ_DemographicType` dt ON dt.name = cdh.cdh_demographic_type
        WHERE shd.shd_contact_name IN ({}) AND cdh.cdh_demographic_type = %s AND shd.shd_survey_id = %s
        """

        formatted_query = query.format(','.join(['%s'] * len(recipient_ids)))

    results = frappe.db.sql(formatted_query, recipient_ids + [demographic_field, survey_id], as_dict=True)
    
    for contact in results:
        demographic_value = contact.get('demographic_value')
        if not demographic_value:
            demographic_value = 'Sin clasificar'
        
        if demographic_value not in demographic_map:
            demographic_map[demographic_value] = []
        demographic_map[demographic_value].append(contact.name)
    
    return demographic_map


def get_responses_by_respondent(survey_name):
    """
    Get all responses grouped by respondent/user
    Returns dict: {respondent_id: [responses]}
    """
    responses = get_all_responses_for_survey(survey_name)
    responses_by_respondent = {}
    
    for response in responses:
        respondent = response.user or response.name
        if respondent not in responses_by_respondent:
            responses_by_respondent[respondent] = []
        responses_by_respondent[respondent].append(response)
    
    return responses_by_respondent
