import frappe

def get_all_responses_for_survey(survey_name):
  responses = frappe.get_all("Survey Response", filters={"survey": survey_name}, fields=["*"])
  return responses
def get_survey_questions(survey_name):
  questions = frappe.get_all('qp_IQ_SurveyQuestion', filters={'parent': survey_name}, fields=['sq_question'])
  return [q.sq_question for q in questions]

def get_question_text_and_category(survey_name):
  questions = get_survey_questions(survey_name)
  question_details = {}
  for question in questions:
    question_doc = frappe.get_doc('qp_IQ_Question', {'name': question})
    question_details[question] = {
      'text': question_doc.qn_statement_others or question_doc.qn_statement,
      'dimension': frappe.db.get_value('qp_IQ_DemographicType', question_doc.qn_demographic, 'dt_title') if question_doc.qn_demographic else None,
      'theme': frappe.db.get_value('qp_IQ_DemographicType', question_doc.qp_topic, 'dt_title') if question_doc.qp_topic else None
    }
  return question_details


def get_leader_evaluators(leader_name, survey_name):
  evaluators = frappe.get_all('qp_IQ_SurveyRecipient', filters={'sr_contact': leader_name, 'sr_survey': survey_name}, fields=['sr_contact', 'sr_evaluation_role', 'sr_evaluating_to'])
  return evaluators

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

def get_survey_evaluator_map(survey_id):
    recipients = frappe.get_all(
        'qp_IQ_SurveyRecipient',
        filters={'sr_survey': survey_id},
        fields=['sr_contact', 'sr_evaluating_to', 'sr_evaluation_role']
    )
    
    evaluator_map = {}
    contact_ids = set()
    
    for r in recipients:
        if r.sr_evaluating_to and r.sr_contact and r.sr_evaluation_role:
            evaluator_map[(r.sr_evaluating_to, r.sr_contact)] = r.sr_evaluation_role
            contact_ids.add(r.sr_evaluating_to)
            
    if contact_ids:
        contacts_dni = frappe.get_all(
            'Contact',
            filters={'name': ['in', list(contact_ids)]},
            fields=['name', 'custom_document_number']
        )
        
        for c in contacts_dni:
            if not c.custom_document_number:
                continue
            dni_key = str(c.custom_document_number).strip()
            
            
            for (eval_to, target_leader), role in list(evaluator_map.items()):
                if eval_to == c.name:
                    evaluator_map[(dni_key, target_leader)] = role
                
    return evaluator_map