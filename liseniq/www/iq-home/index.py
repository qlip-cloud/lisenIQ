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

    user_company = frappe.db.get_value("Contact", {"user": frappe.session.user, "custom_is_liseniq_contact": 0}, "custom_company")


    if not user_company:
        context.measurements = []
        frappe.log_error("El usuario actual no tiene una compañía asignada.", "Error en iq-home/index.py")
        return context

    try:
        survey_statuses = frappe.get_all("qp_IQ_SurveyStatus", fields=["name", "se_status"], order_by="se_status")
        context.survey_statuses = survey_statuses
    except frappe.DoesNotExistError:
        context.survey_statuses = []

    query_filters = {"su_owner": user_company}
    selected_status_name = frappe.request.args.get('status')

    if selected_status_name:
        status_id = frappe.db.get_value("qp_IQ_SurveyStatus", {"se_status": selected_status_name}, "name")
        if status_id:
            query_filters["su_status"] = status_id
            context.selected_status = selected_status_name
        else:
            context.selected_status = "Todos"
    else:
        context.selected_status = "Todos"

    try:
        surveys = frappe.get_all(
            "qp_IQ_Survey",
            filters=query_filters,
            fields=["name", "su_name", "su_status", "su_start_date", "su_end_date", "su_public_link", "modified", "creation"],
            order_by="modified desc"
        )
    except frappe.DoesNotExistError:
        surveys = []

    rs_responded = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Responded"}, "name") or "Responded"

    measurements_data = []
    for survey in surveys:
        total_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey.name})
        total_responses = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey.name, "sr_status": rs_responded})

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
            "percentage": percentage,
            "public_link": survey.su_public_link
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
