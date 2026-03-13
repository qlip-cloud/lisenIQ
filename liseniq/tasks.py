# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import now
from frappe.utils.data import get_datetime, add_to_date
import jwt
from time import time
from email.utils import formataddr
from datetime import datetime, timezone
import pytz

DEFAULT_SENDER_NAME = "OCC Solutions "

def _now_utc_str() -> str:
	return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _get_survey_tz_name(survey_doc) -> str:
	try:
		tz_name = None
		if hasattr(survey_doc, "su_timezone"):
			tz_name = getattr(survey_doc, "su_timezone")
		elif isinstance(survey_doc, dict):
			tz_name = survey_doc.get("su_timezone")
		tz_name = (tz_name or "UTC").strip()
		_ = pytz.timezone(tz_name)
		return tz_name
	except Exception:
		return "UTC"

def _now_in_survey_tz(survey_doc) -> datetime:
	try:
		tz = pytz.timezone(_get_survey_tz_name(survey_doc))
		return datetime.now(tz)
	except Exception:
		return datetime.now(pytz.utc)

def _get_notification_sender_name() -> str:
	try:
		cache_key = "liseniq_notification_sender_aiq"
		cached = None
		try:
			cached = frappe.cache().get_value(cache_key)
		except Exception:
			pass
		if cached:
			return cached if isinstance(cached, str) else cached.decode("utf-8")

		param = frappe.db.get_value(
			"qp_IQ_Parameters",
			{"pa_abbreviation": "notification_sender_aiq"},
			["pa_data_type", "pa_data_character"],
			as_dict=True
		)
		if param:
			data_type = (param.get("pa_data_type") or "").strip().lower()
			value = (param.get("pa_data_character") or "").strip()
			if data_type.startswith("char") and value:
				try:
					frappe.cache().set_value(cache_key, value)
				except Exception:
					pass
				return value
	except Exception:
		frappe.log_error(frappe.get_traceback(), "_get_notification_sender_name")

	return DEFAULT_SENDER_NAME

# Refactor de Plantillas HTML
def _get_invitation_html(survey_name, body_custom, end_date_html, unique_url, is_custom=False):
	if is_custom:
		return f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; background-color: #f7f9fc; color: #333; margin:0; padding:0; }}
    .container {{ max-width:600px; margin:20px auto; background:#fff; border-radius:8px; box-shadow:0 2px 6px rgba(0,0,0,0.08); padding:30px; }}
    .header {{ text-align:center; border-bottom:2px solid #004aad; padding-bottom:15px; margin-bottom:20px; }}
    .header h1 {{ color:#004aad; font-size:22px; margin:0; }}
    .btn {{ display:inline-block; background-color:#004aad; color:#fff !important; text-decoration:none; padding:12px 20px; border-radius:6px; font-weight:bold; margin-top:20px; }}
    .footer {{ font-size:12px; color:#777; margin-top:25px; text-align:center; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header"><h1>{survey_name}</h1></div>
    {body_custom or ""}
    {end_date_html}
    <p style="text-align:center;">
      <a href="{unique_url}" class="btn">Iniciar encuesta</a>
    </p>
  </div>
</body>
</html>
		"""
	else:
		return f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <style>
    body {{
      font-family: Arial, Helvetica, sans-serif;
      background-color: #f7f9fc;
      color: #333333;
      margin: 0;
      padding: 0;
    }}
    .container {{
      max-width: 600px;
      margin: 20px auto;
      background: #ffffff;
      border-radius: 8px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.08);
      padding: 30px;
    }}
    .header {{
      text-align: center;
      border-bottom: 2px solid #004aad;
      padding-bottom: 15px;
      margin-bottom: 20px;
    }}
    .header h1 {{
      color: #004aad;
      font-size: 22px;
      margin: 0;
    }}
    p {{
      margin-bottom: 20px;
      text-align: justify;
    }}
    .btn {{
      display: inline-block;
      background-color: #004aad;
      color: #ffffff !important;
      text-decoration: none;
      padding: 12px 20px;
      border-radius: 6px;
      font-weight: bold;
      margin-top: 20px;
    }}
    .info {{
      margin: 20px 0;
      padding: 15px;
      background-color: #f0f4ff;
      border-left: 4px solid #004aad;
    }}
    .footer {{
      font-size: 12px;
      color: #777777;
      margin-top: 25px;
      text-align: center;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1> {survey_name} </h1>
    </div>
    <p>Hola ,</p>
    <p>Te damos la bienvenida a <strong>{survey_name}</strong>, una iniciativa clave que nos permitirá obtener información valiosa acerca de nuestra compañía y avanzar en nuestro propósito de mejora continua.</p>
    <div class="info">
      <p><strong>Información importante sobre la encuesta:</strong></p>
      <ul>
        <li>Completarla tomará menos de 20 minutos.</li>
        <li>Tus respuestas serán manejadas de forma confidencial y se utilizarán únicamente con fines estadísticos.</li>
        <li>Para una mejor experiencia, te recomendamos usar Google Chrome y asegurarte de estar conectado a internet.</li>
        <li>Si tienes alguna duda o presentas inconvenientes, escríbenos a <a href="mailto:info@occsolutions.org">info@occsolutions.org</a>.</li>
        <li>Este enlace es personal e intransferible, por lo que no debe compartirse.</li>
      </ul>
    </div>
    {end_date_html}
    <p>Agradecemos de antemano tu tiempo y tus valiosos aportes en este importante proceso.</p>
    <p style="text-align:center;">
      <a href="{unique_url}" class="btn">Iniciar encuesta</a>
    </p>
  </div>
</body>
</html>
		"""

def _get_reminder_html(survey_name, body_custom, link, is_custom=False):
	if is_custom:
		return f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; background-color: #f7f9fc; color: #333; margin:0; padding:0; }}
    .container {{ max-width:600px; margin:20px auto; background:#fff; border-radius:8px; box-shadow:0 2px 6px rgba(0,0,0,0.08); padding:30px; }}
    .header {{ text-align:center; border-bottom:2px solid #e67e22; padding-bottom:15px; margin-bottom:20px; }}
    .header h1 {{ color:#e67e22; font-size:22px; margin:0; }}
    .btn {{ display:inline-block; background-color:#e67e22; color:#fff !important; text-decoration:none; padding:12px 20px; border-radius:6px; font-weight:bold; margin-top:20px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header"><h1>Recordatorio de Medición</h1></div>
    {body_custom or ""}
    <p style="text-align:center;">
      <a href="{link}" class="btn">Responder encuesta</a>
    </p>
  </div>
</body>
</html>
		"""
	else:
		return f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; background-color: #f7f9fc; color: #333333; margin: 0; padding: 0; }}
    .container {{ max-width: 600px; margin: 20px auto; background: #ffffff; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); padding: 30px; }}
    .header {{
      text-align: center;
      border-bottom: 2px solid #004aad;
      padding-bottom: 15px;
      margin-bottom: 20px;
    }}
    .header h1 {{
      color: #004aad;
      font-size: 22px;
      margin: 0;
    }}
    p {{
      margin-bottom: 20px;
      text-align: justify;
    }}
    .btn {{
      display: inline-block;
      background-color: #004aad;
      color: #ffffff !important;
      text-decoration: none;
      padding: 12px 20px;
      border-radius: 6px;
      font-weight: bold;
      margin-top: 20px;
    }}
    .info {{
      margin: 20px 0;
      padding: 15px;
      background-color: #f0f4ff;
      border-left: 4px solid #004aad;
    }}
    .footer {{
      font-size: 12px;
      color: #777777;
      margin-top: 25px;
      text-align: center;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1> {survey_name} </h1>
    </div>
    <p>Hola ,</p>
    <p>Queremos recordarte que aún tienes pendiente completar la encuesta – <strong>{survey_name}</strong>, la cual nos ayudará a obtener información valiosa acerca de nuestra compañía y continuar fortaleciendo nuestra cultura organizacional.</p>
    <div class="info">
      <p><strong>Información importante sobre la encuesta:</strong></p>
      <ul>
        <li>Completarla tomará menos de 20 minutos.</li>
        <li>Tus respuestas serán manejadas de forma confidencial y se utilizarán únicamente con fines estadísticos.</li>
        <li>Para una mejor experiencia, te recomendamos usar Google Chrome y asegurarte de estar conectado a internet.</li>
        <li>Si tienes alguna duda o presentas inconvenientes, escríbenos a <a href="mailto:info@occsolutions.org">info@occsolutions.org</a>.</li>
        <li>Este enlace es personal e intransferible, por lo que no debe compartirse.</li>
      </ul>
    </div>
    <p style="text-align:center;"><a href="{link}" class="btn">Responder encuesta</a></p>
    <p>Tu voz es fundamental para este proceso. Gracias por tu participación y compromiso.</p>
  </div>
</body>
</html>
		"""

def launch_pending_surveys():
	frappe.log_error("Iniciando tarea cron: launch_pending_surveys", "launch_pending_surveys - Inicio")
	try:
		status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "En Progreso"}, "name")
		if not status_in_progress:
			frappe.log_error("No se encontró el estado 'En Progreso' en qp_IQ_SurveyStatus.", "launch_pending_surveys - Config Error")
			return

		status_scheduled = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Programada"}, "name")
		if not status_scheduled:
			frappe.log_error("No se encontró el estado 'Programada' en qp_IQ_SurveyStatus.", "launch_pending_surveys - Config Error")
			return

		rs_not_sent = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Not Sent"}, "name")
		rs_sent = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Sent"}, "name")
		if not rs_not_sent or not rs_sent:
			frappe.log_error("No se encontraron estados de destinatario 'Not Sent' o 'Sent' en qp_IQ_RecipientStatus.", "launch_pending_surveys - Config Error")
			return

		pending_surveys = frappe.get_all(
			"qp_IQ_Survey",
			filters={"su_status": status_scheduled},
			fields=["name", "su_name", "su_start_date"]
		)

		if not pending_surveys:
			frappe.log_error("No se encontraron encuestas en estado 'Programada'.", "launch_pending_surveys - Info")
			return

		frappe.log_error(f"Se encontraron {len(pending_surveys)} encuestas programadas para revisión.", "launch_pending_surveys - Info")

		for survey in pending_surveys:
			try:
				survey_doc = frappe.get_doc("qp_IQ_Survey", survey.name)
				if not survey_doc.su_start_date:
					frappe.log_error(f"Encuesta {survey.name} omitida: No tiene fecha de inicio definida.", "launch_pending_surveys - Omitido")
					continue
				
				now_local = _now_in_survey_tz(survey_doc).replace(tzinfo=None)
				start_dt = get_datetime(survey_doc.su_start_date)
				if now_local < start_dt:
					frappe.log_error(f"Encuesta {survey.name} omitida: Fecha inicio {start_dt} es mayor a fecha actual {now_local}.", "launch_pending_surveys - Omitido")
					continue

				frappe.db.set_value("qp_IQ_Survey", survey.name, "su_status", status_in_progress)
				frappe.log_error(f"Iniciando procesamiento y envío de links para encuesta {survey.name}.", "launch_pending_surveys - Procesando")

				is_leadership = getattr(survey_doc, "su_is_leadership", 0)

				recipients_docs = frappe.get_all(
					"qp_IQ_SurveyRecipient",
					filters={"sr_survey": survey.name, "sr_status": rs_not_sent},
					fields=["name", "sr_contact", "sr_evaluating_to"]
				)

				if not recipients_docs:
					frappe.log_error(f"Encuesta {survey.name} procesada a 'En Progreso' pero no tiene destinatarios pendientes.", "launch_pending_surveys - Sin Destinatarios")
					continue
				
				# Agrupar si es 360 Liderazgo
				if is_leadership:
					groups = {}
					for r in recipients_docs:
						eval_id = r.sr_evaluating_to or r.sr_contact
						groups.setdefault(eval_id, []).append(r)
					contact_ids = list(groups.keys())
					frappe.log_error(f"Encuesta {survey.name} es Liderazgo. {len(recipients_docs)} evaluaciones agrupadas en {len(groups)} evaluadores.", "launch_pending_surveys - Liderazgo")
				else:
					contact_ids = [r.sr_contact for r in recipients_docs]
					frappe.log_error(f"Encuesta {survey.name} convencional. Destinatarios pendientes: {len(recipients_docs)}.", "launch_pending_surveys - Convencional")

				if contact_ids:
					contacts_data = frappe.get_all(
						"Contact",
						filters={"name": ["in", contact_ids]},
						fields=["name", "email_id", "custom_document_number"]
					)
					contact_details_map = {c.name: c for c in contacts_data}
				else:
					contact_details_map = {}

				is_custom_email = not getattr(survey_doc, "su_default_notif", True)
				subject = survey_doc.su_invitation_subject if is_custom_email else f"Bienvenido(a) al proceso de Medición - {survey.su_name}"

				secret = frappe.conf.get("liseniq_jwt_secret") or frappe.conf.get("encryption_key")
				if not secret:
					frappe.log_error("Fallo crítico: No se encontró 'liseniq_jwt_secret' ni 'encryption_key' en site_config para firmar JWT.", "launch_pending_surveys - Error Crítico")
					continue

				end_date_html = ""
				if getattr(survey_doc, "su_end_date", None):
					end_date_html = f'<p>La fecha máxima para diligenciar esta encuesta es el <strong>{survey_doc.su_end_date}</strong></p>'

				sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id")
				if not sender_email:
					frappe.log_error("Fallo crítico: No se encontró cuenta de correo saliente por defecto.", "launch_pending_surveys - Error Crítico")
					continue
				
				sender_formatted = formataddr((_get_notification_sender_name(), sender_email))

				enviados = 0
				errores = 0

				# Lógica de Envíos según tipo
				if is_leadership:
					base_url = frappe.utils.get_url('/iq-register')
					
					for eval_id, records in groups.items():
						contact_info = contact_details_map.get(eval_id)
						if not contact_info:
							frappe.log_error(f"Evaluador '{eval_id}' no encontrado en Contactos. Omitiendo...", "launch_pending_surveys - Advertencia Liderazgo")
							errores += len(records)
							continue

						contact_dni = contact_info.get("custom_document_number")

						# Si eval no tiene DNI
						if not contact_dni:
							frappe.log_error(f"Evaluador '{eval_id}' no tiene DNI configurado. Es imposible generar el enlace.", "launch_pending_surveys - Sin DNI")
							errores += len(records)
							continue

						first_rec = records[0]
						payload = {
							"rid": first_rec.name,
							"sur": survey.su_name,
							"iat": int(time()),
							"custom_document_number": contact_dni
						}

						try:
							token = jwt.encode(payload, secret, algorithm="HS256")
							if isinstance(token, bytes): token = token.decode("utf-8")
						except Exception as e:
							frappe.log_error(f"Error generando JWT para evaluador {eval_id}: {e}", "launch_pending_surveys - Error JWT")
							errores += len(records)
							continue

						unique_url = f"{base_url}?token={token}&uq=true"
						
						# Intentar enviar el correo solo si hay email
						contact_email = contact_info.get("email_id")
						if contact_email:
							message = _get_invitation_html(survey.su_name, survey_doc.su_invitation_body, end_date_html, unique_url, is_custom_email)
							try:
								frappe.sendmail(recipients=[contact_email], sender=sender_formatted, subject=subject, message=message, now=True)
							except Exception as e:
								frappe.log_error(f"Error enviando correo a {contact_email} (Liderazgo): {e}. El link SI se guardará en DB.", "launch_pending_surveys - Error Mail")
						else:
							frappe.log_error(f"Evaluador '{eval_id}' no tiene correo. Se generó el link en BD sin enviarlo.", "launch_pending_surveys - Sin Email")

						# Guardar en Base de Datos de manera obligatoria (siempre que tenga DNI)
						for r in records:
							try:
								frappe.db.set_value("qp_IQ_SurveyRecipient", r.name, {"sr_link": unique_url, "sr_token": token, "sr_status": rs_sent, "sr_sent_on": now()})
								enviados += 1
							except Exception as e:
								if "Data too long" in str(e):
									frappe.db.set_value("qp_IQ_SurveyRecipient", r.name, {"sr_token": token, "sr_status": rs_sent, "sr_sent_on": now()})
									enviados += 1
								else:
									frappe.log_error(f"Error guardando token en DB para registro {r.name}: {e}", "launch_pending_surveys - Error DB")
									errores += 1
				else:
					web_form_route = frappe.db.get_value("Web Form", {"title": survey.su_name}, "route")
					if not web_form_route:
						frappe.log_error(f"No se encontró ruta Web Form para encuesta {survey.su_name}.", "launch_pending_surveys - Error WebForm")
						continue
					
					base_url = frappe.utils.get_url(web_form_route)

					for recipient_doc in recipients_docs:
						contact_info = contact_details_map.get(recipient_doc.sr_contact)
						if not contact_info:
							frappe.log_error(f"Contacto '{recipient_doc.sr_contact}' no encontrado en el sistema. Omitiendo...", "launch_pending_surveys - Advertencia")
							errores += 1
							continue

						contact_dni = contact_info.get("custom_document_number")

						# Si contacto no tiene DNI
						if not contact_dni:
							frappe.log_error(f"Contacto '{recipient_doc.sr_contact}' no tiene DNI configurado. Es imposible generar el enlace.", "launch_pending_surveys - Sin DNI")
							errores += 1
							continue

						payload = {
							"rid": recipient_doc.name,
							"sur": survey.su_name,
							"iat": int(time()),
							"custom_document_number": contact_dni
						}

						try:
							token = jwt.encode(payload, secret, algorithm="HS256")
							if isinstance(token, bytes): token = token.decode("utf-8")
						except Exception as e:
							frappe.log_error(f"Error generando JWT para {recipient_doc.name}: {e}", "launch_pending_surveys - Error JWT")
							errores += 1
							continue

						unique_url = f"{base_url}?new=1&token={token}"
						
						# Intentar enviar el correo solo si hay email
						contact_email = contact_info.get("email_id")
						if contact_email:
							message = _get_invitation_html(survey.su_name, survey_doc.su_invitation_body, end_date_html, unique_url, is_custom_email)
							try:
								frappe.sendmail(recipients=[contact_email], sender=sender_formatted, subject=subject, message=message, now=True)
							except Exception as e:
								frappe.log_error(f"Error enviando correo a {contact_email} (Convencional): {e}. El link SI se guardará en DB.", "launch_pending_surveys - Error Mail")
						else:
							frappe.log_error(f"Contacto '{recipient_doc.sr_contact}' no tiene correo. Se generó el link en BD sin enviarlo.", "launch_pending_surveys - Sin Email")

						# Guardar en Base de Datos obligatoriamente
						try:
							frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, {"sr_link": unique_url, "sr_token": token, "sr_status": rs_sent, "sr_sent_on": now()})
							enviados += 1
						except Exception as e:
							if "Data too long" in str(e):
								frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, {"sr_token": token, "sr_status": rs_sent, "sr_sent_on": now()})
								enviados += 1
							else:
								frappe.log_error(f"Error guardando token en DB para {recipient_doc.name}: {e}", "launch_pending_surveys - Error DB")
								errores += 1
				
				frappe.db.commit()
				frappe.log_error(f"Procesamiento finalizado para {survey.name}. Enviados/Generados: {enviados}, Omitidos sin DNI/Error: {errores}.", "launch_pending_surveys - Éxito")
				
			except Exception as e:
				frappe.db.rollback()
				frappe.log_error(f"Error general procesando encuesta {survey.name}: {e}\n{frappe.get_traceback()}", "launch_pending_surveys - Error Bucle Principal")

	except Exception as e:
		frappe.log_error(f"Fallo general en la tarea cron launch_pending_surveys: {e}\n{frappe.get_traceback()}", "launch_pending_surveys - Fallo Crítico")

@frappe.whitelist()
def send_survey_reminders():
	frappe.log_error("Iniciando tarea cron: send_survey_reminders", "send_survey_reminders - Inicio")
	try:
		now_dt = get_datetime(now())
		today_date = now_dt.date()

		status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "En Progreso"}, "name")
		if not status_in_progress:
			frappe.log_error("No se encontró el estado 'En Progreso'.", "send_survey_reminders - Config Error")
			return

		rs_sent = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Sent"}, "name")
		if not rs_sent:
			frappe.log_error("No se encontró el estado 'Sent'.", "send_survey_reminders - Config Error")
			return

		surveys_in_progress = frappe.get_all(
			"qp_IQ_Survey",
			filters={"su_status": status_in_progress},
			fields=["name", "su_name", "su_start_date", "creation", "su_reminder_frequency", "su_reminder_max"]
		)

		if not surveys_in_progress:
			frappe.log_error("No hay encuestas 'En Progreso' para procesar recordatorios.", "send_survey_reminders - Info")
			return

		for survey in surveys_in_progress:
			try:
				survey_doc = frappe.get_doc("qp_IQ_Survey", survey.name)
				now_dt = _now_in_survey_tz(survey_doc)
				today_date = now_dt.date()

				if not survey.su_reminder_max or survey.su_reminder_max == 0:
					continue

				base_date = None
				if survey.su_start_date:
					try:
						base_date = get_datetime(survey.su_start_date).date()
					except Exception:
						base_date = None
				if not base_date:
					try:
						base_date = get_datetime(survey.creation).date()
					except Exception:
						base_date = today_date

				days_since = (today_date - base_date).days
				if days_since < 0:
					continue

				freq_raw = (survey.su_reminder_frequency or "").strip().lower()
				is_daily = freq_raw.startswith("diari")
				is_weekly = freq_raw.startswith("seman")

				if not is_daily and not is_weekly:
					continue

				expected_sends = days_since if is_daily else (days_since // 7)
				if expected_sends <= 0:
					continue

				max_allowed = int(survey.su_reminder_max) if survey.su_reminder_max else expected_sends
				expected_sends = min(expected_sends, max_allowed)

				recipients_to_remind = frappe.get_all(
					"qp_IQ_SurveyRecipient",
					filters={
						"sr_survey": survey.name,
						"sr_status": rs_sent,
						"sr_reminder_send": ["<", survey.su_reminder_max]
					},
					fields=["name", "sr_contact", "sr_evaluating_to", "sr_link", "sr_token", "sr_reminder_send", "sr_last_reminder_send"]
				)

				if not recipients_to_remind:
					continue

				frappe.log_error(f"Procesando recordatorios para {survey.name}. {len(recipients_to_remind)} registros candidatos.", "send_survey_reminders - Procesando")

				is_leadership = getattr(survey_doc, "su_is_leadership", 0)

				if is_leadership:
					groups = {}
					for r in recipients_to_remind:
						eid = r.sr_evaluating_to or r.sr_contact
						groups.setdefault(eid, []).append(r)
					contact_ids = list(groups.keys())
				else:
					contact_ids = [r.sr_contact for r in recipients_to_remind]

				if contact_ids:
					contacts_data = frappe.get_all(
						"Contact", 
						filters={"name": ["in", contact_ids]}, 
						fields=["name", "email_id"]
					)
					contact_info_map = {c.name: c for c in contacts_data}
				else:
					contact_info_map = {}

				sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id")
				if not sender_email:
					frappe.log_error("Fallo crítico: No se encontró cuenta de correo saliente por defecto.", "send_survey_reminders - Error Crítico")
					continue
				sender_formatted = formataddr((_get_notification_sender_name(), sender_email))

				is_custom_email = not getattr(survey_doc, "su_default_notif", True)
				subject = survey_doc.su_reminder_subject if is_custom_email else f"Recordatorio: Encuesta de Medición - {survey.su_name}"

				enviados = 0
				errores = 0

				# Lógica de Reminders según tipo
				if is_leadership:
					base_url = frappe.utils.get_url('/iq-register')
					
					for eval_id, records in groups.items():
						try:
							first_rec = records[0]
							current_sent = int(first_rec.sr_reminder_send or 0)
							if current_sent >= expected_sends: continue

							cinfo = contact_info_map.get(eval_id)
							if not cinfo: 
								frappe.log_error(f"Evaluador '{eval_id}' no encontrado en Contactos. Omitiendo...", "send_survey_reminders - Advertencia Liderazgo")
								errores += len(records)
								continue
							
							# Intentar enviar correo si existe
							contact_email = cinfo.get("email_id")
							if contact_email:
								link = first_rec.sr_link
								if not link or "iq-register" not in link:
									link = f"{base_url}?token={first_rec.sr_token}&uq=true"

								message = _get_reminder_html(survey.su_name, survey_doc.su_reminder_body, link, is_custom_email)

								try:
									frappe.sendmail(recipients=[contact_email], sender=sender_formatted, subject=subject, message=message, now=True)
								except Exception as e:
									frappe.log_error(f"Error enviando recordatorio a {contact_email} (Liderazgo): {e}", "send_survey_reminders - Error Mail")
							else:
								frappe.log_error(f"Evaluador '{eval_id}' no tiene correo. Se actualiza contador sin enviar email.", "send_survey_reminders - Sin Email")

							# Siempre avanzar el contador para no quedar en bucle
							next_count = current_sent + 1
							next_reminder_date = None
							if next_count < max_allowed:
								if is_daily: next_reminder_date = add_to_date(base_date, days=(next_count)).date()
								else: next_reminder_date = add_to_date(base_date, days=(7 * next_count)).date()

							for r in records:
								try:
									frappe.db.set_value("qp_IQ_SurveyRecipient", r.name, {
										"sr_reminder_send": next_count,
										"sr_last_reminder_send": now_dt,
										"sr_next_reminder": next_reminder_date
									})
									enviados += 1
								except Exception as e:
									frappe.log_error(f"Error guardando recordatorio DB {r.name}: {e}", "send_survey_reminders - Error DB")
									errores += 1
									
							frappe.db.commit()
						except Exception as e:
							frappe.db.rollback()
							frappe.log_error(f"Error general en grupo de recordatorio {eval_id}: {e}\n{frappe.get_traceback()}", "send_survey_reminders - Error Grupo Liderazgo")
				else:
					web_form_route = frappe.db.get_value("Web Form", {"title": survey.su_name}, "route")
					base_url = frappe.utils.get_url(web_form_route) if web_form_route else None
					if not base_url: 
						frappe.log_error(f"Ruta Web Form no encontrada para {survey.su_name}", "send_survey_reminders - Error WebForm")
						continue

					for recipient in recipients_to_remind:
						try:
							current_sent = int(recipient.sr_reminder_send or 0)
							if current_sent >= expected_sends: continue

							cinfo = contact_info_map.get(recipient.sr_contact)
							if not cinfo: 
								frappe.log_error(f"Contacto '{recipient.sr_contact}' no encontrado. Omitiendo...", "send_survey_reminders - Advertencia")
								errores += 1
								continue

							# Intentar enviar correo si existe
							contact_email = cinfo.get("email_id")
							if contact_email:
								link = f"{base_url}?new=1&token={recipient.sr_token}"
								message = _get_reminder_html(survey.su_name, survey_doc.su_reminder_body, link, is_custom_email)

								try:
									frappe.sendmail(recipients=[contact_email], sender=sender_formatted, subject=subject, message=message, now=True)
								except Exception as e:
									frappe.log_error(f"Error enviando recordatorio a {contact_email}: {e}", "send_survey_reminders - Error Mail")
							else:
								frappe.log_error(f"Contacto '{recipient.sr_contact}' no tiene correo. Se actualiza contador sin enviar email.", "send_survey_reminders - Sin Email")

							# Siempre avanzar el contador para no quedar en bucle
							next_count = current_sent + 1
							next_reminder_date = None
							if next_count < max_allowed:
								if is_daily: next_reminder_date = add_to_date(base_date, days=(next_count)).date()
								else: next_reminder_date = add_to_date(base_date, days=(7 * next_count)).date()

							try:
								frappe.db.set_value("qp_IQ_SurveyRecipient", recipient.name, {
									"sr_reminder_send": next_count,
									"sr_last_reminder_send": now_dt,
									"sr_next_reminder": next_reminder_date
								})
								enviados += 1
							except Exception as e:
								frappe.log_error(f"Error actualizando recordatorio DB {recipient.name}: {e}", "send_survey_reminders - Error DB")
								errores += 1
								
							frappe.db.commit()

						except Exception as e:
							frappe.db.rollback()
							frappe.log_error(f"Error general en recordatorio {recipient.name}: {e}\n{frappe.get_traceback()}", "send_survey_reminders - Error Bucle Convencional")
							
				frappe.log_error(f"Recordatorios para {survey.name} finalizados. Avances: {enviados}, Errores: {errores}", "send_survey_reminders - Éxito")

			except Exception as e:
				frappe.log_error(f"Error general evaluando recordatorios para {survey.name}: {e}\n{frappe.get_traceback()}", "send_survey_reminders - Error Bucle Principal")

	except Exception as e:
		frappe.log_error(f"Fallo general en tarea cron send_survey_reminders: {e}\n{frappe.get_traceback()}", "send_survey_reminders - Fallo Crítico")

def update_finished_surveys():
	frappe.log_error("Iniciando tarea cron: update_finished_surveys", "update_finished_surveys - Inicio")
	try:
		status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "En Progreso"}, "name")
		if not status_in_progress:
			frappe.log_error("No se encontró el estado 'En Progreso'.", "update_finished_surveys - Config Error")
			return

		status_finished = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")
		if not status_finished:
			frappe.log_error("No se encontró el estado 'Finalizada'.", "update_finished_surveys - Config Error")
			return

		rs_responded = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Responded"}, "name")
		if not rs_responded:
			frappe.log_error("No se encontró el estado 'Responded' en qp_IQ_RecipientStatus.", "update_finished_surveys - Config Error")
			return

		surveys_to_check = frappe.get_all(
			"qp_IQ_Survey",
			filters={"su_status": status_in_progress},
			fields=["name", "su_end_date"]
		)
		
		if not surveys_to_check:
			return

		for survey in surveys_to_check:
			try:
				survey_doc = frappe.get_doc("qp_IQ_Survey", survey.name)
				current_local = _now_in_survey_tz(survey_doc).replace(tzinfo=None)

				if survey.su_end_date:
					end_dt = get_datetime(survey.su_end_date)
					if current_local >= end_dt:
						frappe.db.set_value("qp_IQ_Survey", survey.name, "su_status", status_finished)
						frappe.db.commit()
						frappe.log_error(f"Encuesta {survey.name} finalizada por fecha.", "update_finished_surveys - Fecha")
						continue

				total_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey.name})
				if total_recipients > 0:
					responded_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey.name, "sr_status": rs_responded})
					if total_recipients == responded_recipients:
						frappe.db.set_value("qp_IQ_Survey", survey.name, "su_status", status_finished)
						frappe.db.commit()
						frappe.log_error(f"Encuesta {survey.name} finalizada por completitud (100%).", "update_finished_surveys - Completitud")

			except Exception as e:
				frappe.db.rollback()
				frappe.log_error(f"Error procesando finalización de encuesta {survey.name}: {e}\n{frappe.get_traceback()}", "update_finished_surveys - Error Bucle")
	except Exception as e:
		frappe.log_error(f"Fallo general en tarea cron update_finished_surveys: {e}\n{frappe.get_traceback()}", "update_finished_surveys - Fallo Crítico")


@frappe.whitelist()
def delete_iq_survey_fully(survey_name):
    try:
        web_form_title = frappe.db.get_value("qp_IQ_Survey", survey_name, "su_name")
        if not web_form_title:
            return f"Error: No se encontró la encuesta de IQ: {survey_name}"

        recipient_names = frappe.get_all("qp_IQ_SurveyRecipient", filters={"sr_survey": survey_name}, pluck="name")
        for recipient_name in recipient_names:
            frappe.delete_doc("qp_IQ_SurveyRecipient", recipient_name, force=1, ignore_permissions=True)

        web_form_name = frappe.db.get_value("Web Form", {"title": web_form_title}, "name")
        if web_form_name:
            survey_doc_name = frappe.db.get_value("Survey", {"title": web_form_title}, "name")
            if survey_doc_name:
                response_names = frappe.get_all("Survey Response", filters={"survey": survey_doc_name}, pluck="name")
                for response_name in response_names:
                    frappe.delete_doc("Survey Response", response_name, force=1, ignore_permissions=True)
                
                frappe.delete_doc("Survey", survey_doc_name, force=1, ignore_permissions=True)

            frappe.delete_doc("Web Form", web_form_name, force=1, ignore_permissions=True)

        frappe.delete_doc("qp_IQ_Survey", survey_name, force=1, ignore_permissions=True)
        frappe.db.commit()
        return f"Encuesta {survey_name} eliminada exitosamente."

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "delete_iq_survey_fully")
        return f"Error al eliminar la encuesta: {e}"

@frappe.whitelist()
def delete_all_iq_surveys():
    try:
        all_surveys = frappe.get_all("qp_IQ_Survey", pluck="name")
        if not all_surveys:
            message = "No se encontraron encuestas de IQ para eliminar."
            return message

        total_surveys = len(all_surveys)

        for i, survey_name in enumerate(all_surveys):
            delete_iq_survey_fully(survey_name)
        
        success_message = f"Proceso completado. Se eliminaron {total_surveys} encuestas de IQ."
        return success_message

    except Exception as e:
        frappe.db.rollback()
        error_message = f"Ocurrió un error durante la eliminación masiva: {frappe.get_traceback()}"
        return f"Error durante la eliminación masiva: {e}"

@frappe.whitelist()
def send_pending_links_for_survey(survey_name: str):
	frappe.log_error(f"Iniciando envío manual de enlaces pendientes para encuesta: {survey_name}", "send_pending_links_for_survey - Inicio")
	try:
		if not survey_name:
			frappe.log_error("Se llamó al método sin proporcionar survey_name", "send_pending_links_for_survey - Error")
			return {"status": "error", "message": "survey_name requerido."}

		survey = frappe.get_doc("qp_IQ_Survey", survey_name)

		status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "En Progreso"}, "name")
		if not status_in_progress or survey.su_status != status_in_progress:
			frappe.log_error(f"Encuesta {survey_name} no está en progreso (Actual: {survey.su_status}).", "send_pending_links_for_survey - Omitido")
			return {"status": "skipped", "message": "La medición no está en progreso. Envío omitido."}

		rs_not_sent = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Not Sent"}, "name")
		rs_sent = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Sent"}, "name")
		if not rs_not_sent or not rs_sent:
			frappe.log_error("No se encontraron estados de recipiente configurados.", "send_pending_links_for_survey - Error Config")
			return {"status": "error", "message": "No se encontraron estados 'Not Sent' o 'Sent' en qp_IQ_RecipientStatus."}

		recipients_docs = frappe.get_all(
			"qp_IQ_SurveyRecipient",
			filters={"sr_survey": survey.name, "sr_status": rs_not_sent},
			fields=["name", "sr_contact", "sr_evaluating_to"]
		)
		if not recipients_docs:
			frappe.log_error("No hay destinatarios en estado 'Not Sent'.", "send_pending_links_for_survey - Info")
			return {"status": "success", "message": "No hay destinatarios pendientes por enviar."}

		is_leadership = getattr(survey, "su_is_leadership", 0)

		if is_leadership:
			groups = {}
			for r in recipients_docs:
				eid = r.sr_evaluating_to or r.sr_contact
				groups.setdefault(eid, []).append(r)
			contact_ids = list(groups.keys())
			frappe.log_error(f"Es medición de Liderazgo. {len(recipients_docs)} evaluaciones agrupadas para {len(groups)} evaluadores.", "send_pending_links_for_survey - Info")
		else:
			contact_ids = [r.sr_contact for r in recipients_docs]
			frappe.log_error(f"Medición convencional. {len(recipients_docs)} destinatarios pendientes.", "send_pending_links_for_survey - Info")

		if contact_ids:
			contacts_data = frappe.get_all(
				"Contact",
				filters={"name": ["in", contact_ids]},
				fields=["name", "email_id", "custom_document_number"]
			)
			contact_details_map = {c.name: c for c in contacts_data}
		else:
			contact_details_map = {}

		is_custom_email = not getattr(survey, "su_default_notif", True)
		subject = survey.su_invitation_subject if is_custom_email else f"Bienvenido(a) al proceso de Medición - {survey.su_name}"

		secret = frappe.conf.get("liseniq_jwt_secret") or frappe.conf.get("encryption_key")
		if not secret:
			frappe.log_error("Fallo crítico: No se encontró clave secreta JWT.", "send_pending_links_for_survey - Error Crítico")
			return {"status": "error", "message": "No se encontró 'liseniq_jwt_secret' ni 'encryption_key'."}

		enviados = 0
		omitidos = 0

		end_date_html = ""
		if getattr(survey, "su_end_date", None):
			end_date_html = f'<p>La fecha máxima para diligenciar esta encuesta es el <strong>{survey.su_end_date}</strong></p>'

		sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id")
		if not sender_email:
			frappe.log_error("Fallo crítico: No hay cuenta de correo saliente configurada.", "send_pending_links_for_survey - Error Crítico")
			return {"status": "error", "message": "No hay cuenta de correo predeterminada saliente."}
		sender_formatted = formataddr((_get_notification_sender_name(), sender_email))

		if is_leadership:
			base_url = frappe.utils.get_url('/iq-register')
			for eval_id, records in groups.items():
				contact_info = contact_details_map.get(eval_id)
				if not contact_info:
					frappe.log_error(f"Evaluador '{eval_id}' no encontrado en Contactos. Omitiendo...", "send_pending_links_for_survey - Advertencia")
					omitidos += len(records)
					continue

				contact_dni = contact_info.get("custom_document_number")

				if not contact_dni:
					frappe.log_error(f"Evaluador '{eval_id}' no tiene DNI configurado. Es imposible generar el enlace.", "send_pending_links_for_survey - Sin DNI")
					omitidos += len(records)
					continue

				first_rec = records[0]
				payload = {
					"rid": first_rec.name,
					"sur": survey.su_name,
					"iat": int(time()),
					"custom_document_number": contact_dni
				}

				try:
					token = jwt.encode(payload, secret, algorithm="HS256")
					if isinstance(token, bytes): token = token.decode("utf-8")
				except Exception as e:
					frappe.log_error(f"Fallo codificando JWT para evaluador {eval_id}: {e}", "send_pending_links_for_survey - Error JWT")
					omitidos += len(records)
					continue

				unique_url = f"{base_url}?token={token}&uq=true"
				
				# Intentar enviar correo solo si hay email
				contact_email = contact_info.get("email_id")
				if contact_email:
					message = _get_invitation_html(survey.su_name, survey.su_invitation_body, end_date_html, unique_url, is_custom_email)
					try:
						frappe.sendmail(recipients=[contact_email], sender=sender_formatted, subject=subject, message=message, now=True)
					except Exception as e:
						frappe.log_error(f"Fallo enviando correo a {contact_email}: {e}. El link SI se guardará en BD.", "send_pending_links_for_survey - Error Mail")
				else:
					frappe.log_error(f"Evaluador '{eval_id}' no tiene correo. Se generó el link en BD sin enviarlo.", "send_pending_links_for_survey - Sin Email")

				# Guardar obligatoriamente en Base de Datos
				for r in records:
					try:
						frappe.db.set_value("qp_IQ_SurveyRecipient", r.name, {"sr_link": unique_url, "sr_token": token, "sr_status": rs_sent, "sr_sent_on": now()})
						enviados += 1
					except Exception as e:
						if "Data too long" in str(e):
							frappe.db.set_value("qp_IQ_SurveyRecipient", r.name, {"sr_token": token, "sr_status": rs_sent, "sr_sent_on": now()})
							enviados += 1
						else:
							frappe.log_error(f"Error actualizando DB registro {r.name}: {e}", "send_pending_links_for_survey - Error DB")
							omitidos += 1
		else:
			web_form_route = frappe.db.get_value("Web Form", {"title": survey.su_name}, "route")
			if not web_form_route:
				frappe.log_error(f"No se encontró ruta Web Form para encuesta {survey.su_name}.", "send_pending_links_for_survey - Error WebForm")
				return {"status": "error", "message": "No se encontró el Web Form de la encuesta."}
			base_url = frappe.utils.get_url(web_form_route)

			for recipient_doc in recipients_docs:
				contact_info = contact_details_map.get(recipient_doc.sr_contact)
				if not contact_info:
					frappe.log_error(f"Contacto '{recipient_doc.sr_contact}' no encontrado. Omitiendo...", "send_pending_links_for_survey - Advertencia")
					omitidos += 1
					continue

				contact_dni = contact_info.get("custom_document_number")

				if not contact_dni:
					frappe.log_error(f"Contacto '{recipient_doc.sr_contact}' no tiene DNI configurado. Es imposible generar el enlace.", "send_pending_links_for_survey - Sin DNI")
					omitidos += 1
					continue

				payload = {
					"rid": recipient_doc.name,
					"sur": survey.su_name,
					"iat": int(time()),
					"custom_document_number": contact_dni
				}
				try:
					token = jwt.encode(payload, secret, algorithm="HS256")
					if isinstance(token, bytes): token = token.decode("utf-8")
				except Exception as e:
					frappe.log_error(f"Fallo codificando JWT para {recipient_doc.name}: {e}", "send_pending_links_for_survey - Error JWT")
					omitidos += 1
					continue

				unique_url = f"{base_url}?new=1&token={token}"
				
				# Intentar enviar correo solo si hay email
				contact_email = contact_info.get("email_id")
				if contact_email:
					message = _get_invitation_html(survey.su_name, survey.su_invitation_body, end_date_html, unique_url, is_custom_email)
					try:
						frappe.sendmail(recipients=[contact_email], sender=sender_formatted, subject=subject, message=message, now=True)
					except Exception as e:
						frappe.log_error(f"Fallo enviando correo a {contact_email}: {e}. El link SI se guardará en BD.", "send_pending_links_for_survey - Error Mail")
				else:
					frappe.log_error(f"Contacto '{recipient_doc.sr_contact}' no tiene correo. Se generó el link en BD sin enviarlo.", "send_pending_links_for_survey - Sin Email")

				# Guardar obligatoriamente en Base de Datos
				try:
					frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, {"sr_link": unique_url, "sr_token": token, "sr_status": rs_sent, "sr_sent_on": now()})
					enviados += 1
				except Exception as e:
					if "Data too long" in str(e):
						frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, {"sr_token": token, "sr_status": rs_sent, "sr_sent_on": now()})
						enviados += 1
					else:
						frappe.log_error(f"Error actualizando DB registro {recipient_doc.name}: {e}", "send_pending_links_for_survey - Error DB")
						omitidos += 1

		frappe.db.commit()
		frappe.log_error(f"Proceso manual finalizado. Enviados/Generados: {enviados}, Omitidos sin DNI/Error: {omitidos}.", "send_pending_links_for_survey - Éxito")
		return {"status": "success", "sent": enviados, "skipped": omitidos}

	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(f"Fallo general enviando enlaces pendientes: {e}\n{frappe.get_traceback()}", "send_pending_links_for_survey - Fallo Crítico")
		return {"status": "error", "message": "Fallo al enviar enlaces pendientes."}
