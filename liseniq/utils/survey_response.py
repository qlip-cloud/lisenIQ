from __future__ import unicode_literals
import frappe
import jwt
import json
from frappe.utils import get_datetime, now
from datetime import datetime, timezone  # NUEVO

def _now_utc_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def process_survey_response(doc, method):
    # frappe.log_error("Iniciando process_survey_response", "Survey Response Hook")

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
                # frappe.log_error("Respuesta sin token (anónima o inválida). Saltando enlace de recipient.", "Survey Response Hook")
                return

        secret = frappe.conf.get("liseniq_jwt_secret") or frappe.conf.get("encryption_key")
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            frappe.throw("El enlace ha expirado.")
        except jwt.InvalidTokenError:
            frappe.throw("Enlace inválido o expirado.")

        status_finished = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")
        su_status, su_end_date = frappe.db.get_value(
            "qp_IQ_Survey", {"su_name": doc.survey}, ["su_status", "su_end_date"]
        ) or (None, None)
        if status_finished and su_status == status_finished:
            frappe.throw("Esta encuesta ya fue completada. Gracias por tu participación.")
        if su_end_date and get_datetime(su_end_date) <= get_datetime(_now_utc_str()):  # CAMBIO: UTC
            frappe.throw("El enlace ha expirado.")

        is_public = payload.get("public", False)
        
        if is_public:
            # Si la medición tiene destinatarios, exigir que el DNI pertenezca a un destinatario válido
            survey_name_id = frappe.db.get_value("qp_IQ_Survey", {"su_name": doc.survey}, "name")
            recipients_count = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey_name_id}) if survey_name_id else 0
            if recipients_count > 0:
                if not (doc.user and doc.user != "Anonimo"):
                    frappe.throw("Debe ingresar su DNI para responder esta encuesta.")
                survey_owner_company = frappe.db.get_value("qp_IQ_Survey", {"su_name": doc.survey}, "su_owner")
                contact_info = frappe.db.get_value(
                    "Contact",
                    {"custom_document_number": doc.user},
                    ["name", "custom_company"],
                    as_dict=True
                )
                if not contact_info or contact_info.custom_company != survey_owner_company:
                    frappe.throw("No está habilitado para responder esta encuesta.")
                recipient_exists = frappe.db.exists(
                    "qp_IQ_SurveyRecipient",
                    {"sr_survey": survey_name_id, "sr_contact": contact_info.name}
                )
                if not recipient_exists:
                    frappe.throw("No está habilitado para responder esta encuesta.")
            return

        rid = payload.get("rid")
        token_sur = payload.get("sur")

        if token_sur and token_sur != doc.survey:
            frappe.throw("Enlace inválido o expirado.")

        survey_end_date = frappe.db.get_value("qp_IQ_Survey", {"su_name": doc.survey}, "su_end_date")
        if survey_end_date and get_datetime(survey_end_date) < get_datetime(_now_utc_str()):  # CAMBIO: UTC
            frappe.throw("El enlace ha expirado.")

        if not rid:
            # frappe.log_error(f"Respuesta de enlace genérico para {doc.survey}. User/DNI: {doc.user}", "Survey Response Hook")
            
            contact_name = None
            if doc.user and doc.user != "Anonimo":
                survey_owner_company = frappe.db.get_value("qp_IQ_Survey", {"su_name": doc.survey}, "su_owner")
                if not survey_owner_company:
                    frappe.throw("No se pudo determinar la empresa propietaria de la encuesta.")

                contact_info = frappe.db.get_value("Contact", {"custom_document_number": doc.user}, ["name", "custom_company"], as_dict=True)

                if not contact_info:
                    frappe.throw("El DNI proporcionado no corresponde a un contacto registrado.")
                
                if contact_info.custom_company != survey_owner_company:
                    frappe.throw("El DNI proporcionado no pertenece a un contacto válido para esta encuesta.")

                contact_name = contact_info.name

                if contact_name:
                    survey_name_id = frappe.db.get_value("qp_IQ_Survey", {"su_name": doc.survey}, "name")
                    
                    if survey_name_id:
                        existing_response_by_contact = frappe.db.exists(
                            "Survey Response",
                            {
                                "survey": doc.survey,
                                "user": contact_name,
                                "name": ["!=", doc.name]
                            }
                        )
                        if existing_response_by_contact:
                            frappe.throw("Esta encuesta ya fue completada. Gracias por tu participación.")

                        recipient_exists = frappe.db.exists(
                            "qp_IQ_SurveyRecipient",
                            {
                                "sr_survey": survey_name_id,
                                "sr_contact": contact_name,
                            }
                        )
                        if recipient_exists:
                            frappe.db.set_value(
                                "qp_IQ_SurveyRecipient",
                                {
                                    "sr_survey": survey_name_id,
                                    "sr_contact": contact_name,
                                },
                                {"sr_status": "Responded", "sr_survey_response": doc.name}
                            )
                        else:
                            pass

                existing_response = frappe.db.exists(
                    "Survey Response",
                    {
                        "survey": doc.survey,
                        "user": doc.user,
                        "name": ["!=", doc.name]
                    }
                )
                if existing_response:
                    frappe.throw("Esta encuesta ya fue completada con el DNI proporcionado. Gracias por tu participación.")
            
            if contact_name:
                doc.user = contact_name
            
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

        if recipient.sr_contact:
            doc.user = recipient.sr_contact
            dni = frappe.db.get_value("Contact", recipient.sr_contact, "custom_document_number")
            if dni:
                existing_response = frappe.db.exists(
                    "Survey Response",
                    {
                        "survey": doc.survey,
                        "user": dni,
                        "name": ["!=", doc.name]
                    }
                )
                if existing_response:
                    frappe.throw("Esta encuesta ya fue completada con el DNI proporcionado. Gracias por tu participación.")

        su_name_of_recipient = frappe.db.get_value("qp_IQ_Survey", recipient.sr_survey, "su_name")
        if su_name_of_recipient != doc.survey:
            frappe.throw("Enlace inválido o expirado.")

        if recipient.sr_status == "Responded":
            # frappe.log_error(f"El destinatario {recipient.name} ya tiene estado 'Responded'. Abortando guardado.", "Survey Response Hook")
            frappe.throw("Esta encuesta ya fue completada. Gracias por tu participación.")

        frappe.db.set_value(
            "qp_IQ_SurveyRecipient",
            recipient.name,
            {"sr_status": "Responded", "sr_survey_response": doc.name}
        )
        # frappe.log_error(f"Destinatario {recipient.name} actualizado a 'Responded'.", "Survey Response Hook")

        survey_name = recipient.sr_survey
        total_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey_name})
        responded_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey_name, "sr_status": "Responded"})

        if total_recipients > 0 and total_recipients == responded_recipients:
            status_finished = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")
            if status_finished:
                frappe.db.set_value("qp_IQ_Survey", survey_name, "su_status", status_finished)
                frappe.log_error(f"Encuesta {survey_name} finalizada por completitud (100%).", "Survey Response Hook")

        # dni_from_token = payload.get("custom_document_number")
        # contact_name = None
        # if dni_from_token:
        #     contact_name = frappe.db.get_value(
        #         "Contact",
        #         {"custom_document_number": dni_from_token},
        #         "name"
        #     )

        # if not contact_name:
        #     contact_name = recipient.sr_contact

        # if contact_name and len(contact_name) > 140:
        #     contact_name = contact_name[:140]
        # doc.user = contact_name or "Anonimo"

        # frappe.log_error(f"Actualizando destinatario {recipient.name} a 'Responded' y enlazando respuesta {doc.name}", "Survey Response Hook")
        # frappe.db.set_value(
        #     "qp_IQ_SurveyRecipient",
        #     recipient.name,
        #     {"sr_status": "Responded", "sr_survey_response": doc.name}
        # )
        frappe.db.commit()
        # frappe.log_error(f"Destinatario {recipient.name} actualizado correctamente.", "Survey Response Hook")

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
                    if isinstance(answer, str) and answer in options_map:
                        resp[q_name] = options_map[answer]
                    elif isinstance(answer, dict) and "text" in answer and answer["text"] in options_map:
                        resp[q_name] = options_map[answer["text"]]
            doc.response_json = json.dumps(resp)
        except Exception:
            pass

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Error en process_survey_response")
        raise

