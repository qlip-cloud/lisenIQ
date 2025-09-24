from __future__ import unicode_literals
import frappe
import jwt
import json

def process_survey_response(doc, method):
    frappe.log_error("Iniciando process_survey_response", "Survey Response Hook")

    try:
        token = None
        if doc.user and doc.user != "Anonimo":
            token = doc.user
        else:
            try:
                resp = json.loads(doc.response_json or "{}")
                token = resp.get("__token")
            except Exception:
                token = None

        if not token:
            frappe.log_error("Respuesta sin token (anónima o inválida). Saltando enlace de recipient.", "Survey Response Hook")
            return

        secret = frappe.conf.get("liseniq_jwt_secret") or frappe.conf.get("encryption_key")
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            frappe.throw("El enlace ha expirado.")
        except jwt.InvalidTokenError:
            frappe.throw("Enlace inválido o expirado.")

        rid = payload.get("rid")
        token_sur = payload.get("sur")

        if token_sur and token_sur != doc.survey:
            frappe.throw("Enlace inválido o expirado.")

        recipient = None
        if rid:
            recipient = frappe.db.get_value(
                "qp_IQ_SurveyRecipient", rid, ["name", "sr_status", "sr_survey", "sr_contact"], as_dict=True
            )
        if not recipient:
            recipient = frappe.db.get_value(
                "qp_IQ_SurveyRecipient", {"sr_token": token}, ["name", "sr_status", "sr_survey", "sr_contact"], as_dict=True
            )

        if not recipient:
            frappe.throw("Enlace inválido o expirado.")

        su_name_of_recipient = frappe.db.get_value("qp_IQ_Survey", recipient.sr_survey, "su_name")
        if su_name_of_recipient != doc.survey:
            frappe.throw("Enlace inválido o expirado.")

        if recipient.sr_status == "Responded":
            frappe.log_error(f"El destinatario {recipient.name} ya tiene estado 'Responded'. Abortando guardado.", "Survey Response Hook")
            frappe.throw("Esta encuesta ya fue completada. Gracias por tu participación.")

        # Resolver Contact por DNI desde el token (custom_document_number)
        dni_from_token = payload.get("custom_document_number")
        contact_name = None
        if dni_from_token:
            contact_name = frappe.db.get_value(
                "Contact",
                {"custom_document_number": dni_from_token},
                "name"
            )

        if not contact_name:
            contact_name = recipient.sr_contact  # respaldo por vínculo del recipient

        if contact_name and len(contact_name) > 140:
            contact_name = contact_name[:140]
        doc.user = contact_name or "Anonimo"

        frappe.log_error(f"Actualizando destinatario {recipient.name} a 'Responded' y enlazando respuesta {doc.name}", "Survey Response Hook")
        frappe.db.set_value(
            "qp_IQ_SurveyRecipient",
            recipient.name,
            {"sr_status": "Responded", "sr_survey_response": doc.name}
        )
        frappe.db.commit()
        frappe.log_error(f"Destinatario {recipient.name} actualizado correctamente.", "Survey Response Hook")

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Error en process_survey_response")
        raise

