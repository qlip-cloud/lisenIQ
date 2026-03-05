import frappe
import json
import jwt
from time import time
from frappe.utils import now
from frappe.utils.data import get_datetime, add_to_date
from datetime import datetime, timezone
import pytz

def _now_utc_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def _now_in_survey_tz_by_su_name(su_name: str) -> datetime:
    try:
        tz_name = (frappe.db.get_value("qp_IQ_Survey", {"su_name": su_name}, "su_timezone") or "UTC").strip()
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = pytz.utc
    return datetime.now(tz)

@frappe.whitelist(allow_guest=True)
def get_public_survey(survey_name, token=None, dni=None):
  try:
    survey_data = frappe.db.get_value("Survey", survey_name, ["survey_json", "theme_json"], as_dict=True)
    if not survey_data:
        frappe.throw("Encuesta no encontrada.")
        
    # Verificar si es una medición de Liderazgo (360) para aplicar cambios dinámicos de preguntas
    survey_doc = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, ["name", "su_is_leadership", "su_owner"], as_dict=True)
    
    if survey_doc and survey_doc.su_is_leadership:
        recipient = None
        
        # Intentar obtener el destinatario por medio del token
        if token and token != "Anonimo":
            secret = _get_jwt_secret()
            try:
                payload = jwt.decode(token, secret, algorithms=["HS256"])
                rid = payload.get("rid")
                if rid:
                    recipient = frappe.db.get_value("qp_IQ_SurveyRecipient", rid, ["sr_evaluation_role", "sr_evaluating_to", "sr_contact"], as_dict=True)
                else:
                    recipient = frappe.db.get_value("qp_IQ_SurveyRecipient", {"sr_token": token}, ["sr_evaluation_role", "sr_evaluating_to", "sr_contact"], as_dict=True)
            except Exception:
                pass
        
        # Si no hay token personalizado, buscar por DNI
        if not recipient and dni:
            contact_name = frappe.db.get_value("Contact", {"custom_document_number": dni, "custom_company": survey_doc.su_owner}, "name")
            if contact_name:
                recipients = frappe.get_all(
                    "qp_IQ_SurveyRecipient", 
                    filters={"sr_survey": survey_doc.name, "sr_contact": contact_name, "sr_status": ["!=", "Responded"]}, 
                    fields=["sr_evaluation_role", "sr_evaluating_to", "sr_contact"],
                    limit_page_length=1
                )
                if recipients:
                    recipient = recipients[0]
        
        if recipient:
            # Validar si cumple condición de Autoevaluación
            is_auto = (recipient.sr_evaluation_role == "Autoevaluación" and recipient.sr_evaluating_to == recipient.sr_contact)
            
            # Si evalúa a un tercero, reemplazar enunciado por qn_statement_others
            if not is_auto:
                parsed_json = json.loads(survey_data.survey_json)
                survey_questions = frappe.get_all("qp_IQ_SurveyQuestion", filters={"parent": survey_doc.name}, fields=["sq_question"])
                
                q_dict = {}
                for sq in survey_questions:
                    other_stmt = frappe.db.get_value("qp_IQ_Question", sq.sq_question, "qn_statement_others")
                    if other_stmt:
                        q_dict[sq.sq_question] = other_stmt
                        
                for page in parsed_json.get("pages", []):
                    for el in page.get("elements", []):
                        q_name = el.get("name")
                        if q_name in q_dict:
                            el["title"] = q_dict[q_name]
                
                survey_data["survey_json"] = json.dumps(parsed_json)
                
    return survey_data
  except Exception as e:
    frappe.log_error(frappe.get_traceback(), 'Error en get_public_survey')
    frappe.throw("No se pudo cargar la encuesta solicitada.")

@frappe.whitelist(allow_guest=True)
def save_survey_response(survey_name, response_data, user=None):
  try:
    data = json.loads(response_data)

    token_like = False
    if user and user != "Anonimo":
      if "." in user or len(user) > 140:
        token_like = True

    if token_like:
      data["__token"] = user
      user_to_store = "Anonimo"
    else:
      user_to_store = user or "Anonimo"
    
    new_response = frappe.get_doc({
        "doctype": "Survey Response",
        "survey": survey_name,
        "response_json": json.dumps(data),
        "user": user_to_store
    })
    
    new_response.insert(ignore_permissions=True)
    
    return {"status": "Ok", "message": "Respuesta guardada con éxito."}

  except Exception as e:
    frappe.log_error(frappe.get_traceback(), 'Error en save_survey_response')
    frappe.throw("Ocurrió un error al guardar tu respuesta.")

def _get_jwt_secret():
  return frappe.conf.get("liseniq_jwt_secret") or frappe.conf.get("encryption_key")

@frappe.whitelist(allow_guest=True)
def get_survey_is_anonymous(survey_name):
    is_anonymous = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "su_is_anonymous")
    return bool(is_anonymous)

@frappe.whitelist(allow_guest=True)
def validate_survey_link(survey_name, user=None, token=None, dni=None, uq=None):
  uq_flag = str(uq).lower() == "true"
  try:
    status_finished = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")
    rs_responded = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Responded"}, "name") or "Responded"
    
    survey_doc = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, ["name", "su_status", "su_end_date", "su_is_leadership", "su_owner"], as_dict=True)
    if not survey_doc:
         return {"allow": False, "message": "Encuesta no encontrada."}
         
    su_status = survey_doc.su_status
    su_end_date = survey_doc.su_end_date
    survey_name_id = survey_doc.name
    is_leadership = survey_doc.su_is_leadership

    if status_finished and su_status == status_finished:
      return {"allow": False, "message": "La medición ha finalizado."}
    if su_end_date:
      now_local = _now_in_survey_tz_by_su_name(survey_name).replace(tzinfo=None)
      if get_datetime(su_end_date) <= now_local:
        return {"allow": False, "message": "El enlace ha expirado."}

    if not token or token == "Anonimo":
      # Permitir acceso público si el DNI corresponde a un destinatario registrado
      if dni:
        if survey_name_id:
          recipient_exists = frappe.db.exists(
            "qp_IQ_SurveyRecipient",
            {"sr_survey": survey_name_id, "sr_contact": frappe.db.get_value("Contact", {"custom_document_number": dni}, "name")}
          )
          if recipient_exists:
            return {"allow": True}
      return {"allow": True}

    secret = _get_jwt_secret()
    try:
      payload = jwt.decode(token, secret, algorithms=["HS256"])
      rid = payload.get("rid")
      sur_claim = payload.get("sur")
      is_public = payload.get("public", False)

      if sur_claim != survey_name:
          return {"allow": False, "message": "Enlace inválido o expirado."}

      survey_end_date = survey_doc.su_end_date
      if survey_end_date:
          now_local = _now_in_survey_tz_by_su_name(survey_name).replace(tzinfo=None)
          if get_datetime(survey_end_date) < now_local:
              return {"allow": False, "message": "El enlace ha expirado."}

      recipients_count = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey_name_id}) if survey_name_id else 0

      # Enlace público (genérico)
      if is_public:
        # Si hay destinatarios definidos para la medición, exigir validación por DNI
        if recipients_count > 0 and dni:
          survey_owner_company = survey_doc.su_owner
          if not survey_owner_company:
              return {"allow": False, "message": "No se pudo determinar la empresa propietaria de la encuesta."}

          contact_info = frappe.db.get_value(
              "Contact",
              {"custom_document_number": dni, "custom_company": survey_owner_company},
              ["name", "custom_company", "status"],
              as_dict=True
          )
          public_token = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "su_public_token")

          if not contact_info:
              return {"allow": False, "valid_dni": False, "message": "El DNI proporcionado no corresponde a un contacto registrado.", "redirect_register": True, "register_token": public_token}
          if contact_info.custom_company != survey_owner_company:
              return {"allow": False, "valid_dni": False, "message": "El DNI proporcionado no pertenece a un contacto válido para esta encuesta.", "redirect_register": True, "register_token": public_token}
          if contact_info.status not in ("Enabled", "Passive"):
              return {"allow": False, "valid_dni": False, "message": "El contacto no está activo para responder esta encuesta.", "redirect_register": True, "register_token": public_token}

          recipient_exists = frappe.db.exists(
              "qp_IQ_SurveyRecipient",
              {"sr_survey": survey_name_id, "sr_contact": contact_info.name}
          )
          if recipient_exists:
              return {"allow": True}
          else:
              return {"allow": False, "valid_dni": False, "message": "No está habilitado para responder esta encuesta."}

        return {"allow": True}

      # Lógica para encuestas no públicas (con destinatarios)
      if not rid and dni:
          survey_owner_company = survey_doc.su_owner
          if not survey_owner_company:
              return {"allow": False, "message": "No se pudo determinar la empresa propietaria de la encuesta."}

          contact_info = frappe.db.get_value(
              "Contact",
              {"custom_document_number": dni, "custom_company": survey_owner_company},
              ["name", "custom_company", "status"],
              as_dict=True
          )
          public_token = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "su_public_token")

          if not contact_info:
              return {"allow": False, "valid_dni": False, "message": "El DNI proporcionado no corresponde a un contacto registrado.", "redirect_register": True, "register_token": public_token}
          if contact_info.custom_company != survey_owner_company:
              return {"allow": False, "valid_dni": False, "message": "El DNI proporcionado no pertenece a un contacto válido para esta encuesta.", "redirect_register": True, "register_token": public_token}
          if contact_info.status not in ("Enabled", "Passive"):
              return {"allow": False, "valid_dni": False, "message": "El contacto no está activo para responder esta encuesta.", "redirect_register": True, "register_token": public_token}

          contact_name = contact_info.name
          if contact_name and survey_name_id:
              recipient_exists = frappe.db.exists(
                  "qp_IQ_SurveyRecipient",
                  {"sr_survey": survey_name_id, "sr_contact": contact_name}
              )
              if not recipient_exists:
                  return {"allow": False, "valid_dni": False, "message": "No está habilitado para responder esta encuesta."}

              existing_response_by_contact = frappe.db.exists(
                  "Survey Response",
                  {"survey": survey_name, "user": contact_name}
              )
              # Evitar validación directa de completado por nombre/dni si es liderazgo
              if existing_response_by_contact and not is_leadership:
                  return {"allow": False, "message": "Esta encuesta ya fue completada. Gracias por tu participación."}

              existing_recipient = frappe.db.exists(
                  "qp_IQ_SurveyRecipient",
                  {"sr_survey": survey_name_id, "sr_contact": contact_name, "sr_status": rs_responded}
              )
              if existing_recipient and not is_leadership:
                  return {"allow": False, "message": "Esta encuesta ya fue completada. Gracias por tu participación."}

          existing_response = frappe.db.exists(
              "Survey Response",
              {"survey": survey_name, "user": dni}
          )
          if existing_response and not is_leadership:
              return {"allow": False, "message": "Esta encuesta ya fue completada con el DNI proporcionado. Gracias por tu participación."}

      recipient = None
      if rid:
        recipient = frappe.db.get_value(
          "qp_IQ_SurveyRecipient", rid, ["name", "sr_status", "sr_survey", "sr_contact"], as_dict=True
        )
      if not recipient:
        recipient = frappe.db.get_value(
          "qp_IQ_SurveyRecipient", {"sr_token": token}, ["name", "sr_status", "sr_survey", "sr_contact"], as_dict=True
        )

      if rid and not recipient:
        return {"allow": False, "message": "Este enlace ya no es válido. El destinatario fue removido de la medición."}

      if recipient:
        if recipient.get("sr_contact"):
            contact_status = frappe.db.get_value("Contact", recipient.sr_contact, "status")
            if contact_status and contact_status not in ("Enabled", "Passive"):
                return {"allow": False, "message": "El contacto no está activo para responder esta encuesta."}

            dni_from_contact = frappe.db.get_value("Contact", recipient.sr_contact, "custom_document_number")
            if dni_from_contact and not is_leadership:
                existing_response = frappe.db.exists(
                    "Survey Response",
                    {"survey": survey_name, "user": dni_from_contact}
                )
                if existing_response:
                    return {"allow": False, "message": "Esta encuesta ya fue completada con el DNI proporcionado. Gracias por tu participación."}

        su_name_of_recipient = frappe.db.get_value("qp_IQ_Survey", recipient.sr_survey, "su_name")
        if su_name_of_recipient != survey_name:
          return {"allow": False, "message": "Enlace inválido o expirado."}
        if recipient.sr_status == rs_responded:
          return {"allow": False, "message": "Esta encuesta ya fue completada. Gracias por tu participación."}

      return {"allow": True}

    except jwt.ExpiredSignatureError:
      return {"allow": False, "message": "El enlace ha expirado."}
    except jwt.InvalidTokenError:
      return {"allow": False, "message": "Enlace inválido o expirado."}
  except Exception:
    frappe.log_error(frappe.get_traceback(), "Error en validate_survey_link")
    return {"allow": True}
  except jwt.InvalidTokenError:
    return {"allow": False, "message": "Enlace inválido o expirado."}


@frappe.whitelist(allow_guest=True)
def get_survey_route_for_public_link(token, dni=None):
    if not token:
        frappe.throw("Token no proporcionado.")

    secret = _get_jwt_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        frappe.throw("El enlace ha expirado o no es válido.")

    survey_name = payload.get("sur")
    if not survey_name:
        frappe.throw("Token de encuesta inválido.")

    status_finished = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")
    su_doc = frappe.db.get_value(
        "qp_IQ_Survey", {"su_name": survey_name}, ["name", "su_status", "su_end_date", "su_is_leadership", "su_owner"], as_dict=True
    )
    if not su_doc:
        frappe.throw("Encuesta no encontrada.")
        
    if status_finished and su_doc.su_status == status_finished:
        frappe.throw("El enlace ha expirado.")

    if su_doc.su_end_date:
        now_local = _now_in_survey_tz_by_su_name(survey_name).replace(tzinfo=None)
        if get_datetime(su_doc.su_end_date) <= now_local:
            frappe.throw("El enlace ha expirado.")

    web_form_route = frappe.db.get_value("Web Form", {"title": survey_name}, "route")
    if not web_form_route:
        frappe.throw("No se encontró el formulario para la encuesta.")
        
    if not su_doc.su_is_leadership:
        return {"route": web_form_route, "is_leadership": False}
        
    # Es medición de Liderazgo (360), requiere generar listado de evaluaciones
    if not dni:
        frappe.throw("El DNI es obligatorio para esta medición.")
        
    contact_name = frappe.db.get_value("Contact", {"custom_document_number": dni, "custom_company": su_doc.su_owner}, "name")
    if not contact_name:
        frappe.throw("El DNI proporcionado no corresponde a un contacto registrado.")
        
    rs_responded = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Responded"}, "name") or "Responded"
    
    recipients = frappe.get_all(
        "qp_IQ_SurveyRecipient", 
        filters={"sr_survey": su_doc.name, "sr_contact": contact_name, "sr_status": ["!=", rs_responded]}, 
        fields=["name", "sr_evaluation_role", "sr_evaluating_to"]
    )
    
    if not recipients:
        frappe.throw("No tienes evaluaciones pendientes para esta medición.")
        
    evaluations = []
    for r in recipients:
        c_data = frappe.db.get_value("Contact", r.sr_evaluating_to, ["first_name", "last_name"], as_dict=True)
        if c_data:
            evaluatee_name = f"{(c_data.first_name or '').strip()} {(c_data.last_name or '').strip()}".strip()
        else:
            evaluatee_name = r.sr_evaluating_to
            
        # Generar un token con el Recipient ID embebido (comportamiento de enlace personal)
        eval_payload = {
            "sur": survey_name,
            "rid": r.name,
            "iat": int(time()),
        }
        eval_token = jwt.encode(eval_payload, secret, algorithm="HS256")
        if isinstance(eval_token, bytes):
            eval_token = eval_token.decode("utf-8")
            
        is_auto = (r.sr_evaluation_role == "Autoevaluación" and r.sr_evaluating_to == contact_name)
        
        evaluations.append({
            "id": r.name,
            "role": r.sr_evaluation_role or "Evaluador",
            "evaluatee_name": evaluatee_name,
            "is_auto": is_auto,
            "token": eval_token
        })
        
    return {"route": web_form_route, "is_leadership": True, "evaluations": evaluations}


def generate_public_link_for_survey_hook(doc, method):

    if doc.su_custom_generate_public_link:
        original_ignore_permissions = frappe.flags.ignore_permissions
        frappe.flags.ignore_permissions = True
        try:
            if generate_public_link_for_survey(doc, method):
                frappe.db.set_value(doc.doctype, doc.name, {
                    "su_public_link": doc.su_public_link,
                    "su_public_token": doc.su_public_token,
                    "su_public_link_created_on": doc.su_public_link_created_on,
                    "su_public_link_created_by": doc.su_public_link_created_by,
                    "su_custom_generate_public_link": 0
                })
            else:
                pass
        finally:
            frappe.flags.ignore_permissions = original_ignore_permissions
    else:
        pass

def generate_public_link_for_survey(doc, method):
    modified = False
    if not doc.su_public_link:
        web_form_route = frappe.db.get_value("Web Form", {"title": doc.su_name}, "route")
        if not web_form_route:
            frappe.log_error(f"No se encontró Web Form para la encuesta {doc.su_name}", "generate_public_link_for_survey")
            return modified

        secret = frappe.conf.get("liseniq_jwt_secret") or frappe.conf.get("encryption_key")
        if not secret:
            frappe.log_error("No se encontró 'liseniq_jwt_secret' ni 'encryption_key' para firmar JWT.", "generate_public_link_for_survey")
            return modified

        payload = {
            "sur": doc.su_name,
            "iat": int(time()),
        }

        if doc.su_is_anonymous:
            payload["public"] = True

        try:
            token = jwt.encode(payload, secret, algorithm="HS256")
            if isinstance(token, bytes):
                token = token.decode("utf-8")
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Error generando JWT para enlace público")
            return modified

        if doc.su_is_anonymous:
            base_url = frappe.utils.get_url(web_form_route)
            unique_url = f"{base_url}?new=1"
        else:
            base_url = frappe.utils.get_url('/iq-register')
            unique_url = f"{base_url}?token={token}&uq=true"

        doc.su_public_link = unique_url
        doc.su_public_token = token
        doc.su_public_link_created_on = now()
        doc.su_public_link_created_by = frappe.session.user
        
        if hasattr(doc, 'su_custom_generate_public_link'):
            doc.su_custom_generate_public_link = 0
        
        modified = True
    
    return modified