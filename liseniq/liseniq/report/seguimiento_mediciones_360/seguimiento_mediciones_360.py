# Copyright (c) 2013, Mentum Group and contributors
# For license information, please see license.txt
import frappe
import json
from frappe import _

def execute(filters=None):
	filters = filters or {}
	survey = filters.get("survey")
	if not frappe.db.exists("Survey", survey):
		frappe.throw(_("Survey {0} does not exist").format(survey))

	survey_doc = frappe.get_doc("Survey", survey)
	qp_iq_survey = frappe.get_doc("qp_IQ_Survey", {"su_name": survey})

	columns = get_columns()
	data = get_data(survey_doc, qp_iq_survey)

	return columns, data

def get_columns():
	return [
		{
			"label": _("Evaluado"),
			"fieldname": "evaluated",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"label": _("Relación"),
			"fieldname": "role",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("Evaluador"),
			"fieldname": "evaluator",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"label": _("Estado"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100
		},
	]

def get_data(survey_doc, qp_iq_survey):
	data = []
	survey_recipients = frappe.get_all("qp_IQ_SurveyRecipient", filters={"sr_survey": qp_iq_survey.name}, fields=["*"], order_by="sr_contact asc")
	for recipient in survey_recipients:
		evaluated = recipient.sr_contact
		evaluator_role = recipient.sr_evaluation_role
		evaluator = recipient.sr_evaluating_to if recipient.sr_evaluating_to != evaluated else ""	
		status = get_response_status(survey_doc, recipient)

		data.append({
			"evaluated": evaluated,
			"role": evaluator_role,
			"evaluator": evaluator,
			"status": status
		})
	return data

def get_response_status(survey_doc, recipient):
	response = frappe.get_all("Survey Response", filters={"survey": survey_doc.name, "user": recipient.sr_evaluating_to, "custom_evaluatee": recipient.sr_contact}, fields=["*"])
	if response:
		return "Completado"
	else:
		return "Pendiente"