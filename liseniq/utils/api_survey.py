import frappe
import json
import jwt
from time import time
from frappe.utils import now
from frappe.utils.data import get_datetime, add_to_date
from datetime import datetime, timezone  # NUEVO

def _now_utc_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

@frappe.whitelist(allow_guest=True)
def get_public_survey(survey_name):
  try:
    survey_data = frappe.db.get("Survey", survey_name, ["survey_json", "theme_json"])
    if not survey_data:
        frappe.throw("Encuesta no encontrada.")
        
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
def validate_survey_link(survey_name, user=None, token=None, dni=None):
  # frappe.log_error(
  #     message=f"Iniciando validación. survey_name='{survey_name}', token presente: {'Sí' if token else 'No'}",
  #     title="validate_survey_link Trace"
  # )
  try:
    status_finished = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")
    rs_responded = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Responded"}, "name") or "Responded"
    su_status, su_end_date = frappe.db.get_value(
        "qp_IQ_Survey", {"su_name": survey_name}, ["su_status", "su_end_date"]
    ) or (None, None)
    if status_finished and su_status == status_finished:
      return {"allow": False, "message": "La medición ha finalizado."}
    if su_end_date and get_datetime(su_end_date) <= get_datetime(_now_utc_str()):
      return {"allow": False, "message": "El enlace ha expirado."}

    if not token or token == "Anonimo":
      # Permitir acceso público si el DNI corresponde a un destinatario registrado
      if dni:
        survey_name_id = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "name")
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

      # frappe.log_error(
      #     message=f"Payload decodificado: sur_claim='{sur_claim}', is_public={is_public}",
      #     title="validate_survey_link Trace"
      # )

      if sur_claim != survey_name:
          # frappe.log_error(
          #     message=f"Validación fallida: sur_claim ('{sur_claim}') != survey_name ('{survey_name}')",
          #     title="validate_survey_link Trace"
          # )
          return {"allow": False, "message": "Enlace inválido o expirado."}

      # frappe.log_error(message="Validación de 'sur' exitosa.", title="validate_survey_link Trace")

      # Verificar expiración de la encuesta
      survey_end_date = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "su_end_date")
      if survey_end_date and get_datetime(survey_end_date) < get_datetime(_now_utc_str()):
          return {"allow": False, "message": "El enlace ha expirado."}

      # Obtener ID interno y cantidad de destinatarios
      survey_name_id = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "name")
      recipients_count = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey_name_id}) if survey_name_id else 0

      # Enlace público (genérico)
      if is_public:
        # Si hay destinatarios definidos para la medición, exigir validación por DNI
        if recipients_count > 0 and dni:
          survey_owner_company = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "su_owner")
          if not survey_owner_company:
              return {"allow": False, "message": "No se pudo determinar la empresa propietaria de la encuesta."}

          contact_info = frappe.db.get_value(
              "Contact",
              {"custom_document_number": dni},
              ["name", "custom_company", "status"],
              as_dict=True
          )
          if not contact_info:
              return {"allow": False, "valid_dni": False, "message": "El DNI proporcionado no corresponde a un contacto registrado."}
          if contact_info.custom_company != survey_owner_company:
              return {"allow": False, "valid_dni": False, "message": "El DNI proporcionado no pertenece a un contacto válido para esta encuesta."}
          if contact_info.status not in ("Enabled", "Passive"):
              return {"allow": False, "valid_dni": False, "message": "El contacto no está activo para responder esta encuesta."}

          recipient_exists = frappe.db.exists(
              "qp_IQ_SurveyRecipient",
              {"sr_survey": survey_name_id, "sr_contact": contact_info.name}
          )
          if recipient_exists:
              # Permitir acceso si el destinatario existe, sin requerir envío directo
              return {"allow": True}
          else:
              return {"allow": False, "valid_dni": False, "message": "No está habilitado para responder esta encuesta."}

        # Si aún no hay DNI ingresado, permitir continuar. Se bloqueará al validar el DNI.
        return {"allow": True}

      # Lógica para encuestas no públicas (con destinatarios)
      if not rid and dni:
          survey_owner_company = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "su_owner")
          if not survey_owner_company:
              return {"allow": False, "message": "No se pudo determinar la empresa propietaria de la encuesta."}

          contact_info = frappe.db.get_value(
              "Contact",
              {"custom_document_number": dni},
              ["name", "custom_company", "status"],
              as_dict=True
          )
          if not contact_info:
              return {"allow": False, "valid_dni": False, "message": "El DNI proporcionado no corresponde a un contacto registrado."}
          if contact_info.custom_company != survey_owner_company:
              return {"allow": False, "valid_dni": False, "message": "El DNI proporcionado no pertenece a un contacto válido para esta encuesta."}
          if contact_info.status not in ("Enabled", "Passive"):
              return {"allow": False, "valid_dni": False, "message": "El contacto no está activo para responder esta encuesta."}

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
              if existing_response_by_contact:
                  return {"allow": False, "message": "Esta encuesta ya fue completada. Gracias por tu participación."}

              existing_recipient = frappe.db.exists(
                  "qp_IQ_SurveyRecipient",
                  {"sr_survey": survey_name_id, "sr_contact": contact_name, "sr_status": rs_responded}
              )
              if existing_recipient:
                  return {"allow": False, "message": "Esta encuesta ya fue completada. Gracias por tu participación."}

          existing_response = frappe.db.exists(
              "Survey Response",
              {"survey": survey_name, "user": dni}
          )
          if existing_response:
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

      # Si el enlace es personal pero el destinatario fue eliminado, bloquear
      if rid and not recipient:
        return {"allow": False, "message": "Este enlace ya no es válido. El destinatario fue removido de la medición."}

      if recipient:
        # Verificar que el contacto asociado esté activo
        if recipient.get("sr_contact"):
            contact_status = frappe.db.get_value("Contact", recipient.sr_contact, "status")
            if contact_status and contact_status not in ("Enabled", "Passive"):
                return {"allow": False, "message": "El contacto no está activo para responder esta encuesta."}

            dni_from_contact = frappe.db.get_value("Contact", recipient.sr_contact, "custom_document_number")
            if dni_from_contact:
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
def get_survey_route_for_public_link(token):
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
    su_status, su_end_date = frappe.db.get_value(
        "qp_IQ_Survey", {"su_name": survey_name}, ["su_status", "su_end_date"]
    ) or (None, None)
    if status_finished and su_status == status_finished:
        frappe.throw("El enlace ha expirado.")
    if su_end_date and get_datetime(su_end_date) <= get_datetime(_now_utc_str()):
        frappe.throw("El enlace ha expirado.")

    web_form_route = frappe.db.get_value("Web Form", {"title": survey_name}, "route")
    if not web_form_route:
        frappe.throw("No se encontró el formulario para la encuesta.")
    
    return {"route": web_form_route}

def generate_public_link_for_survey_hook(doc, method):
    # frappe.log_error(
    #     message=f"Hook 'generate_public_link_for_survey_hook' ejecutado para {doc.name}. Flag 'su_custom_generate_public_link' es: {doc.su_custom_generate_public_link}",
    #     title="Link Generation Hook"
    # )
    if doc.su_custom_generate_public_link:
        # frappe.log_error(
        #     message=f"Intentando generar enlace genérico para la encuesta {doc.name}.",
        #     title="Link Generation Hook"
        # )

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
                # frappe.log_error(
                #     message=f"Enlace genérico generado y guardado exitosamente para {doc.name}.",
                #     title="Link Generation Hook"
                # )
            else:
                # frappe.log_error(
                #     message=f"La función generate_public_link_for_survey retornó False. No se generó enlace para {doc.name}.",
                #     title="Link Generation Hook"
                # )
                pass
        finally:
            frappe.flags.ignore_permissions = original_ignore_permissions
    else:
        # frappe.log_error(
        #     message=f"No se requiere generar enlace genérico para {doc.name}. Saltando.",
        #     title="Link Generation Hook"
        # )
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

        # if doc.su_end_date:
        #     end_date_timestamp = int(get_datetime(doc.su_end_date).timestamp())
        #     payload["exp"] = end_date_timestamp

        try:
            token = jwt.encode(payload, secret, algorithm="HS256")
            if isinstance(token, bytes):
                token = token.decode("utf-8")
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Error generando JWT para enlace público")
            return modified

        if doc.su_is_anonymous:
            base_url = frappe.utils.get_url(web_form_route)
            unique_url = f"{base_url}?new=1&token={token}"
        else:
            base_url = frappe.utils.get_url('/iq-register')
            unique_url = f"{base_url}?token={token}"

        doc.su_public_link = unique_url
        doc.su_public_token = token
        doc.su_public_link_created_on = now()
        doc.su_public_link_created_by = frappe.session.user
        
        if hasattr(doc, 'su_custom_generate_public_link'):
            doc.su_custom_generate_public_link = 0
        
        modified = True
    
    return modified
