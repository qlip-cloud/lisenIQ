# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import base64

def process_survey_response(doc, method):
    """
    Se ejecuta al enviar una Survey Response.
    Decodifica el ID del usuario, encuentra el destinatario y actualiza su estado.
    """
    frappe.log_error("Iniciando process_survey_response", "Survey Response Hook")
    if not doc.user or doc.user == "Anonimo":
        frappe.log_error("Respuesta anónima o sin usuario. Saltando.", "Survey Response Hook")
        return

    try:
        frappe.log_error(f"Procesando respuesta para usuario codificado: {doc.user}", "Survey Response Hook")
        # Decodificar el ID
        decoded_payload = base64.b64decode(doc.user).decode('utf-8')
        dni, timestamp = decoded_payload.split('|')
        frappe.log_error(f"ID decodificado: DNI={dni}, Timestamp={timestamp}", "Survey Response Hook")

        # Encontrar el contacto por DNI
        contact_name = frappe.db.get_value("Contact", {"custom_document_number": dni}, "name")
        if not contact_name:
            frappe.log_error(f"No se encontró un contacto con DNI {dni}", "process_survey_response")
            return
        frappe.log_error(f"Contacto encontrado: {contact_name}", "Survey Response Hook")

        # Encontrar el Survey (qp_IQ_Survey) a través del Web Form (Survey)
        survey_name = frappe.db.get_value("qp_IQ_Survey", {"su_name": doc.survey}, "name")
        if not survey_name:
            frappe.log_error(f"No se encontró la medición (qp_IQ_Survey) para la encuesta {doc.survey}", "process_survey_response")
            return
        frappe.log_error(f"Medición (qp_IQ_Survey) encontrada: {survey_name}", "Survey Response Hook")

        # Encontrar el registro del destinatario
        recipient_doc_name = frappe.db.get_value(
            "qp_IQ_SurveyRecipient",
            {"sr_survey": survey_name, "sr_contact": contact_name},
            "name"
        )

        if not recipient_doc_name:
            frappe.log_error(f"No se encontró un destinatario para la medición {survey_name} y contacto {contact_name}", "process_survey_response")
            return
        frappe.log_error(f"Destinatario (qp_IQ_SurveyRecipient) encontrado: {recipient_doc_name}", "Survey Response Hook")

        # Actualizar el estado y enlazar la respuesta
        frappe.log_error(f"Actualizando destinatario {recipient_doc_name} a 'Responded' y enlazando respuesta {doc.name}", "Survey Response Hook")
        frappe.db.set_value(
            "qp_IQ_SurveyRecipient",
            recipient_doc_name,
            {
                "sr_status": "Responded",
                "sr_survey_response": doc.name
            }
        )
        frappe.db.commit()
        frappe.log_error(f"Destinatario {recipient_doc_name} actualizado correctamente.", "Survey Response Hook")

    except (base64.binascii.Error, ValueError, IndexError) as e:
        frappe.log_error(f"ID de usuario inválido o malformado: {doc.user}. Error: {e}", "process_survey_response")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error en process_survey_response")

