# your_app/www/survey_dashboard.py
from multiprocessing import context

import frappe

no_cache = 1


def get_context(context):
    survey = frappe.form_dict.get("survey")
    if not survey:
        frappe.throw("Falta el parámetro 'survey' en la URL", frappe.ValidationError)
    if not frappe.db.exists("Survey", survey):
        frappe.throw(f"Encuesta no encontrada: {survey}", frappe.DoesNotExistError)

    context.survey = survey
    context.title = f"Dashboard — {survey}"
    context.no_cache = 1
    context.no_breadcrumbs = True
    context.is_navbar_custom = True
    context.show_summary_section = False
    
    # No pasamos los datos aquí: el HTML los pide vía frappe.call
    # al cargar, para no incrustar un payload pesado en el HTML.
