# Copyright (c) 2025, Mentum Group and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, formatdate

def get_context(context):
    """
    Prepara y pasa el contexto a la plantilla para la página de inicio.
    Carga las mediciones (encuestas) asociadas al usuario actual.
    """
    context.no_cache = 1
    context.page_title = "Inicio"
    context.no_breadcrumbs = True
    context.is_navbar_custom = True

    # Validación para mostrar la sección de gráficos de resumen.
    context.show_summary_section = False

    # Obtener la compañía del usuario logueado
    user_company = frappe.db.get_value("User", frappe.session.user, "custom_company")

    if not user_company:
        context.measurements = []
        frappe.log_error("El usuario actual no tiene una compañía asignada.", "Error en iq-home/index.py")
        return context

    # Obtener todas las mediciones (encuestas) de la compañía del usuario
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
        # Contar el total de destinatarios y el total de respuestas
        total_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"parent": survey.name})
        total_responses = frappe.db.count("qp_IQ_Response", {"rs_survey": survey.name})

        # Calcular el porcentaje de finalización
        percentage = 0
        if total_recipients > 0:
            percentage = round((total_responses / total_recipients) * 100)

        # Determinar el estado de la medición
        status_doc = frappe.get_doc("qp_IQ_SurveyStatus", survey.su_status)
        status_text = status_doc.se_status if status_doc else "Desconocido"
        
        # Formatear las fechas
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

    # Añadir una tarjeta con datos de ejemplo para visualización
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
    
    # Mock data para la sección "Algo para Medir"
    context.summary_data = [
        {"status": "En Proceso", "bar1_height": 75, "bar2_height": 50},
        {"status": "En Proceso", "bar1_height": 85, "bar2_height": 40},
        {"status": "En Proceso", "bar1_height": 60, "bar2_height": 45}
    ]
     
    return context
