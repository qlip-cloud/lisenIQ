import frappe
import json
import jwt

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
def validate_survey_link(survey_name, user):
  try:
    if not user or user == "Anonimo":
      return {"allow": True}

    secret = _get_jwt_secret()
    try:
      payload = jwt.decode(user, secret, algorithms=["HS256"])
      rid = payload.get("rid")
      sur_claim = payload.get("sur")

      if sur_claim and sur_claim != survey_name:
        return {"allow": False, "message": "Enlace inválido o expirado."}

      recipient = None
      if rid:
        recipient = frappe.db.get_value(
          "qp_IQ_SurveyRecipient", rid, ["name", "sr_status", "sr_survey"], as_dict=True
        )
      if not recipient:
        recipient = frappe.db.get_value(
          "qp_IQ_SurveyRecipient", {"sr_token": user}, ["name", "sr_status", "sr_survey"], as_dict=True
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
