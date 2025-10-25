import frappe

@frappe.whitelist()
def get_test_data_for_survey(survey_name, limit=1000):

    # Survey_name: Nombre de la medición (su_name)
    # Limit: Número máximo de destinatarios a recuperar

    if not frappe.session.user == "Administrator":
        frappe.throw("Solo el Administrador puede usar esta utilidad de prueba.", frappe.PermissionError)

    survey_doc_name = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "name")
    if not survey_doc_name:
        frappe.throw(f"Medición '{survey_name}' no encontrada.")

    survey_doc = frappe.get_doc("qp_IQ_Survey", survey_doc_name)
    web_form_route = frappe.db.get_value("Web Form", {"title": survey_doc.su_name}, "route")
    
    if not web_form_route:
        frappe.throw(f"Web Form para la medición '{survey_doc.su_name}' no encontrado.")

    # Obtener destinatarios con tokens pendientes
    recipients = frappe.get_all(
        "qp_IQ_SurveyRecipient",
        filters={
            "sr_survey": survey_doc.name,
            "sr_status": ["in", ["Not Sent", "Sent"]],          # Estados pendientes
            "sr_token": ["is", "set"]                           # Que el destinatario tenga token
        },
        fields=["name", "sr_contact", "sr_token"],
        limit_page_length=limit
    )
    
    if not recipients:
        frappe.throw("No se encontraron destinatarios pendientes con tokens para esta medición.")

    # Re-mapear los datos para el archivo de iteración
    tokens_list = []
    for r in recipients:
        tokens_list.append({
            "recipient_id": r.name,
            "contact": r.sr_contact,
            "token": r.sr_token
        })

    return {
        "survey_name": survey_doc.su_name,
        "web_form_route": web_form_route,
        "question_ids": [q.sq_question for q in survey_doc.su_questions],
        "tokens_data": tokens_list
    }