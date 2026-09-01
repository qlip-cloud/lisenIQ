# your_app/www/survey_dashboard.py
from multiprocessing import context

import frappe

no_cache = 1


def get_context(context):
	survey = frappe.form_dict.get("survey") or frappe.form_dict.get("survey_name")
	survey_title = frappe.form_dict.get("survey_title")
	if not survey:
			frappe.throw("Falta el parámetro 'survey' (o 'survey_name') en la URL", frappe.ValidationError)

	if not (frappe.db.exists("qp_IQ_Survey", survey) or frappe.db.exists("qp_IQ_Survey", survey)):
			frappe.throw(f"Encuesta no encontrada: {survey}", frappe.DoesNotExistError)

	context.survey = survey
	context.survey_title = survey_title or frappe.db.get_value("qp_IQ_Survey", survey, "su_name") or survey
	context.title = f"Engagement Dashboard — {context.survey_title}"
	context.no_cache = 1
	context.no_breadcrumbs = True
	context.is_navbar_custom = True
	context.show_summary_section = False

# No pasamos los datos aquí: el HTML los pide vía frappe.call
# al cargar, para no incrustar un payload pesado en el HTML.
