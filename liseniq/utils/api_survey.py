import frappe
import json
import jwt
from time import time
from frappe.utils import now
from frappe.utils.data import get_datetime, add_to_date

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
def validate_survey_link(survey_name, user, token):
  frappe.log_error(
      message=f"Iniciando validación. survey_name='{survey_name}', token presente: {'Sí' if token else 'No'}",
      title="validate_survey_link Trace"
  )
  try:
    if not token or token == "Anonimo":
      return {"allow": True}

    secret = _get_jwt_secret()
    try:
      payload = jwt.decode(token, secret, algorithms=["HS256"])
      rid = payload.get("rid")
      sur_claim = payload.get("sur")
      is_public = payload.get("public", False)

      frappe.log_error(
          message=f"Payload decodificado: sur_claim='{sur_claim}', is_public={is_public}",
          title="validate_survey_link Trace"
      )

      if sur_claim != survey_name:
          frappe.log_error(
              message=f"Validación fallida: sur_claim ('{sur_claim}') != survey_name ('{survey_name}')",
              title="validate_survey_link Trace"
          )
          return {"allow": False, "message": "Enlace inválido o expirado."}

      frappe.log_error(message="Validación de 'sur' exitosa.", title="validate_survey_link Trace")

      if is_public:
        return {"allow": True}

      # Lógica para encuestas no públicas (con destinatarios)
      recipient = None
      if rid:
        recipient = frappe.db.get_value(
          "qp_IQ_SurveyRecipient", rid, ["name", "sr_status", "sr_survey"], as_dict=True
        )
      if not recipient:
        recipient = frappe.db.get_value(
          "qp_IQ_SurveyRecipient", {"sr_token": token}, ["name", "sr_status", "sr_survey"], as_dict=True
        )

      if recipient:
        su_name_of_recipient = frappe.db.get_value("qp_IQ_Survey", recipient.sr_survey, "su_name")
        if su_name_of_recipient != survey_name:
          return {"allow": False, "message": "Enlace inválido o expirado."}
        if recipient.sr_status == "Responded":
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

    web_form_route = frappe.db.get_value("Web Form", {"title": survey_name}, "route")
    if not web_form_route:
        frappe.throw("No se encontró el formulario para la encuesta.")
    
    return {"route": web_form_route}

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
            "public": True
        }

        if doc.su_end_date:
            end_date_timestamp = int(get_datetime(doc.su_end_date).timestamp())
            payload["exp"] = end_date_timestamp

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
        
        if hasattr(doc, 'custom_generate_public_link'):
            doc.custom_generate_public_link = 0
        
        modified = True
    
    return modified
