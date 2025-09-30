from __future__ import unicode_literals
import frappe
import jwt
import json

def process_survey_response(doc, method):
    frappe.log_error("Iniciando process_survey_response", "Survey Response Hook")

    try:
        token = None

        try:
            resp = json.loads(doc.response_json or "{}")
            token = resp.get("__token")
        except Exception:
            token = None

        if not token:
            if doc.user and doc.user != "Anonimo" and "." in doc.user:
                 token = doc.user
            else:
                frappe.log_error("Respuesta sin token (anónima o inválida). Saltando enlace de recipient.", "Survey Response Hook")
                return

        secret = frappe.conf.get("liseniq_jwt_secret") or frappe.conf.get("encryption_key")
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            frappe.throw("El enlace ha expirado.")
        except jwt.InvalidTokenError:
            frappe.throw("Enlace inválido o expirado.")

        is_public = payload.get("public", False)
        
        if is_public:
            frappe.log_error(f"Respuesta de encuesta pública para {doc.survey}. User/DNI: {doc.user}", "Survey Response Hook")
            return

        rid = payload.get("rid")
        token_sur = payload.get("sur")

        if token_sur and token_sur != doc.survey:
            frappe.throw("Enlace inválido o expirado.")

        if not rid:
            frappe.log_error(f"Respuesta de enlace genérico para {doc.survey}. User/DNI: {doc.user}", "Survey Response Hook")
            
            # Validar que no exista otra respuesta para esta encuesta con el mismo DNI/user
            if doc.user and doc.user != "Anonimo":
                existing_response = frappe.db.exists(
                    "Survey Response",
                    {
                        "survey": doc.survey,
                        "user": doc.user,
                        "name": ["!=", doc.name] # Excluir el documento actual
                    }
                )
                if existing_response:
                    frappe.throw("Esta encuesta ya fue completada con el DNI proporcionado. Gracias por tu participación.")
            
            return

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

        frappe.db.set_value(
            "qp_IQ_SurveyRecipient",
            recipient.name,
            {"sr_status": "Responded", "sr_survey_response": doc.name}
        )
        frappe.log_error(f"Destinatario {recipient.name} actualizado a 'Responded'.", "Survey Response Hook")

        survey_name = recipient.sr_survey
        total_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey_name})
        responded_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey_name, "sr_status": "Responded"})

        if total_recipients > 0 and total_recipients == responded_recipients:
            status_finished = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")
            if status_finished:
                frappe.db.set_value("qp_IQ_Survey", survey_name, "su_status", status_finished)
                frappe.log_error(f"Encuesta {survey_name} finalizada por completitud (100%).", "Survey Response Hook")

        dni_from_token = payload.get("custom_document_number")
        contact_name = None
        if dni_from_token:
            contact_name = frappe.db.get_value(
                "Contact",
                {"custom_document_number": dni_from_token},
                "name"
            )

        if not contact_name:
            contact_name = recipient.sr_contact

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

        # Procesar respuestas tipo Likert para almacenar valor numérico
        try:
            resp = json.loads(doc.response_json or "{}")
            survey_doc = frappe.get_doc("qp_IQ_Survey", recipient.sr_survey)
            likert_map = {}
            for sq in survey_doc.su_questions:
                q_doc = frappe.get_doc("qp_IQ_Question", sq.sq_question)
                if q_doc.qn_type and frappe.db.get_value("qp_IQ_QuestionType", q_doc.qn_type, "qnt_type_name") == "Likert":
                    likert_map[q_doc.name] = {opt.qo_option_text: opt.qo_option_value for opt in q_doc.qn_response_options}

            for q_name, options_map in likert_map.items():
                if q_name in resp:
                    answer = resp[q_name]
                    # Si la respuesta es texto y existe en el mapeo, reemplaza por valor
                    if isinstance(answer, str) and answer in options_map:
                        resp[q_name] = options_map[answer]
                    # Si la respuesta es objeto con 'text', usa el valor
                    elif isinstance(answer, dict) and "text" in answer and answer["text"] in options_map:
                        resp[q_name] = options_map[answer["text"]]
            doc.response_json = json.dumps(resp)
        except Exception:
            pass

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Error en process_survey_response")
        raise

