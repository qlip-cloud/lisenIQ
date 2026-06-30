import frappe
from frappe.utils import getdate, formatdate
from frappe import _
from liseniq.utils.login_util import global_website_context

def get_context(context):

    context = global_website_context(context)

    # Configuración base de la página
    context.no_cache = 1
    context.page_title = _("Inicio")
    context.no_breadcrumbs = True
    context.is_navbar_custom = True
    context.show_summary_section = False

    user = frappe.session.user

    if not context.get("has_portal_access"):
        context.measurements = []
        return context

    # Logica para determinar la empresa activa del usuario
    user_company = context.get("liseniq_company_name")
    
    if "Administrator" not in frappe.get_roles(user):
        # Leemos estrictamente de la sesión actual
        active_company = frappe.session.data.get("liseniq_active_company")
        
        # Si no hay empresa activa en sesión, forzamos a que seleccione
        if not active_company:
            contact_name = frappe.db.get_value("Contact", {"user": user}, "name")
            if contact_name:
                companies = frappe.get_all("qp_IQ_ContactCompany", filters={"parent": contact_name, "parenttype": "Contact"}, fields=["cc_company"])
                
                if len(companies) > 1:
                    frappe.local.flags.redirect_location = "/iq-home/select_company"
                    raise frappe.Redirect
                elif len(companies) == 1:
                    active_company = companies[0].cc_company
                    frappe.session.data["liseniq_active_company"] = active_company
                    if hasattr(frappe.local, "session_obj") and frappe.local.session_obj:
                        frappe.local.session_obj.update()

        if active_company:
            user_company = active_company


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
            fields=["name", "su_name", "su_status", "su_start_date", "su_end_date", "su_public_link", "su_is_anonymous", "su_is_leadership", "su_report_generated", "modified", "creation"],
            order_by="modified desc"
        )
    except frappe.DoesNotExistError:
        surveys = []

    rs_responded = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Responded"}, "name") or "Responded"

    measurements_data = []
    for survey in surveys:
        is_anonymous = bool(survey.su_is_anonymous)
        
        if is_anonymous:
            total_responses = frappe.db.count("Survey Response", {"survey": survey.su_name})
            total_recipients = 0 
            percentage = 0
        else:
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
            "public_link": survey.su_public_link,
            "is_anonymous": is_anonymous,
            "is_leadership": bool(survey.su_is_leadership),
            "has_generated_reports": bool(getattr(survey, "su_report_generated", 0))
        })

    context.measurements = measurements_data
    
    context.summary_data = [
        {"status": "En Proceso", "bar1_height": 75, "bar2_height": 50},
        {"status": "En Proceso", "bar1_height": 85, "bar2_height": 40},
        {"status": "En Proceso", "bar1_height": 60, "bar2_height": 45}
    ]
     
    return context