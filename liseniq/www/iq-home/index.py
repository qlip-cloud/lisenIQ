import frappe
from frappe.utils import getdate, formatdate
from frappe import _


def get_context(context):

    if frappe.session.user == "Guest":
        frappe.throw(_("Cliente aún no ha sido registrado. Por favor comunique al Administrador."), frappe.PermissionError)

    context.no_cache = 1
    context.page_title = "Inicio"
    context.no_breadcrumbs = True
    context.is_navbar_custom = True

    context.show_summary_section = False

    user_company = frappe.db.get_value("User", frappe.session.user, "custom_company")

    if not user_company:
        context.measurements = []
        frappe.log_error("El usuario actual no tiene una compañía asignada.", "Error en iq-home/index.py")
        return context

    try:
        surveys = frappe.get_all(
            "qp_IQ_Survey",
            filters={"su_owner": user_company},
            fields=["name", "su_name", "su_status", "su_start_date", "su_end_date"]
        )
    except frappe.DoesNotExistError:
        surveys = []

    measurements_data = []
    for survey in surveys:
        total_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"parent": survey.name})
        total_responses = frappe.db.count("qp_IQ_Response", {"rs_survey": survey.name})

        percentage = 0
        if total_recipients > 0:
            percentage = round((total_responses / total_recipients) * 100)

        status_doc = frappe.get_doc("qp_IQ_SurveyStatus", survey.su_status)
        status_text = status_doc.se_status if status_doc else "Desconocido"
        
        start_date_formatted = formatdate(survey.su_start_date, "dd MMM yyyy") if survey.su_start_date else ""
        end_date_formatted = formatdate(survey.su_end_date, "dd MMM yyyy") if survey.su_end_date else ""

        measurements_data.append({
            "name": survey.name,
            "title": survey.su_name,
            "status": status_text,
            "start_date": start_date_formatted,
            "end_date": end_date_formatted,
            "completed": total_responses,
            "total": total_recipients,
            "percentage": percentage
        })

    measurements_data.append({
        "name": "mock-data-card",
        "title": "Medición de Clima Laboral",
        "status": "En Proceso",
        "start_date": "01 Sep 2024",
        "end_date": "30 Sep 2024",
        "completed": 50,
        "total": 150,
        "percentage": 33
    })

    context.measurements = measurements_data
    
    context.summary_data = [
        {"status": "En Proceso", "bar1_height": 75, "bar2_height": 50},
        {"status": "En Proceso", "bar1_height": 85, "bar2_height": 40},
        {"status": "En Proceso", "bar1_height": 60, "bar2_height": 45}
    ]

    context.update({
        "is_navbar_custom": True,
        "no_cache": 1
    })
     
    return context
