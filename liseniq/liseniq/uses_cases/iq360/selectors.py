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
      'category': frappe.db.get_value('qp_IQ_DemographicType', question_doc.qn_demographic, 'dt_title') if question_doc.qn_demographic else None
    }
  return question_details


def get_leader_evaluators(leader_name, survey_name):
  evaluators = frappe.get_all('qp_IQ_SurveyRecipient', filters={'sr_contact': leader_name, 'sr_survey': survey_name}, fields=['sr_contact', 'sr_evaluation_role', 'sr_evaluating_to'])
  return evaluators
