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

DEFAULT_SENDER_NAME = "Mediciones Listen AIQ"

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

def launch_pending_surveys():
	# frappe.log_error("Iniciando tarea launch_pending_surveys, Hora: {}".format(now()), "Survey Task Start")
	try:
		status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "En Progreso"}, "name")
		if not status_in_progress:
			frappe.log_error("No se encontró el estado 'En Progreso' en qp_IQ_SurveyStatus.", "launch_pending_surveys")
			return

		status_scheduled = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Programada"}, "name")
		if not status_scheduled:
			frappe.log_error("No se encontró el estado 'Programada' en qp_IQ_SurveyStatus.", "launch_pending_surveys")
			return

		rs_not_sent = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Not Sent"}, "name")
		rs_sent = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Sent"}, "name")
		if not rs_not_sent or not rs_sent:
			frappe.log_error("No se encontraron estados de destinatario 'Not Sent' o 'Sent' en qp_IQ_RecipientStatus.", "launch_pending_surveys")
			return

		pending_surveys = frappe.get_all(
			"qp_IQ_Survey",
			filters={"su_status": status_scheduled},
			fields=["name", "su_name", "su_start_date"]
		)

		# frappe.log_error(f"Se encontraron {len(pending_surveys)} encuestas pendientes.", "Survey Task Found")

		if not pending_surveys:
			return

		for survey in pending_surveys:
			try:
				survey_doc = frappe.get_doc("qp_IQ_Survey", survey.name)
				if not survey_doc.su_start_date:
					# Si no hay fecha de inicio, no lanzar aún
					continue
				now_local = _now_in_survey_tz(survey_doc).replace(tzinfo=None)
				start_dt = get_datetime(survey_doc.su_start_date)
				if now_local < start_dt:
					# Aún no inicia según su zona horaria
					continue

				# frappe.log_error(f"Procesando encuesta: {survey.name} ({survey.su_name})", "Survey Task Processing")
				frappe.db.set_value("qp_IQ_Survey", survey.name, "su_status", status_in_progress)

				web_form_route = frappe.db.get_value("Web Form", {"title": survey.su_name}, "route")
				if not web_form_route:
					# frappe.log_error(f"No se encontró Web Form para la encuesta {survey.su_name}", "launch_pending_surveys")
					continue

				# Se comenta, cuando tengamos proceso de link de publico abierto, sin ingreso de DNI
				# is_public_survey = frappe.db.get_value("qp_IQ_Survey", survey.name, "su_public_link")
				# if is_public_survey:
				# 	frappe.log_error(f"Encuesta {survey.name} es pública. Saltando envío de correos individuales.", "Survey Task Skip")
				# 	frappe.db.commit()
				# 	continue

				recipients_docs = frappe.get_all(
					"qp_IQ_SurveyRecipient",
					filters={"sr_survey": survey.name, "sr_status": rs_not_sent},
					fields=["name", "sr_contact"]
				)

				if not recipients_docs:
					frappe.log_error(f"Encuesta {survey.name} no tiene destinatarios pendientes. Saltando.", "Survey Task Skip")
					continue
				
				contact_details_map = {
					c.name: {"email": c.email_id, "dni": c.custom_document_number}
					for c in frappe.get_all(
						"Contact",
						filters={"name": ["in", [d.sr_contact for d in recipients_docs]]},
						fields=["name", "email_id", "custom_document_number"]
					) if c.email_id and c.custom_document_number
				}

				subject = f"Bienvenido(a) al proceso de Medición - {survey.su_name}"

				for recipient_doc in recipients_docs:
					try:
						contact_details = contact_details_map.get(recipient_doc.sr_contact)
						if not contact_details:
							frappe.throw(f"El contacto {recipient_doc.sr_contact} no tiene email o DNI (custom_document_number) configurado.")

						contact_email = contact_details["email"]
						contact_dni = contact_details["dni"]

						secret = frappe.conf.get("liseniq_jwt_secret") or frappe.conf.get("encryption_key")
						if not secret:
							frappe.log_error("No se encontró 'liseniq_jwt_secret' ni 'encryption_key' para firmar JWT.", "launch_pending_surveys")
							continue
						
						survey_doc = frappe.get_doc("qp_IQ_Survey", survey.name)
						payload = {
							"rid": recipient_doc.name,
							"sur": survey.su_name,
							"iat": int(time()),
							"custom_document_number": contact_dni
						}

						# if survey_doc.su_end_date:
						# 	end_date_timestamp = int(get_datetime(survey_doc.su_end_date).timestamp())
						# 	payload["exp"] = end_date_timestamp

						try:
							token = jwt.encode(payload, secret, algorithm="HS256")
							if isinstance(token, bytes):
								token = token.decode("utf-8")
						except Exception:
							frappe.log_error(frappe.get_traceback(), "Error generando JWT para recipient")
							continue

						web_form_route = frappe.db.get_value("Web Form", {"title": survey.su_name}, "route")
						base_url = frappe.utils.get_url(web_form_route)
						unique_url = f"{base_url}?new=1&token={token}"
						try:
							frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, {
								"sr_link": unique_url,
								"sr_token": token
							})
						except Exception as e:
							if "Data too long for column 'sr_link'" in str(e):
								frappe.log_error("Columna 'sr_link' es muy corta. Guardando solo sr_token.", "launch_pending_surveys")
								frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, {
									"sr_token": token
								})
							else:
								raise

						end_date_html = ""
						if getattr(survey_doc, "su_end_date", None):
							end_date_html = f'<p>La fecha máxima para diligenciar esta encuesta es el <strong>{survey_doc.su_end_date}</strong></p>'

						message = f"""
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
      <h1> {survey.su_name} </h1>
    </div>
    <p>Cordial saludo, </p>
	<p>Te damos la bienvenida al proceso de <strong>Medición - {survey.su_name}</strong>, la cual, es de gran valor para nosotros, pues nos arroja información acerca de la percepción que tienes de la cultura actual y nos da claridad de las acciones que debemos implementar para continuar desarrollando una cultura sana y las mejores condiciones para asegurar que vivas la mejor experiencia en tu día a día.</p>

    <div class="info">
      <p><strong>Información importante sobre la encuesta:</strong></p>
      <ul>
        <li>La valoración te tomará menos de 20 minutos para realizarla</li>
        <li>La información que compartas será manejada de manera confidencial y utilizada con fines estadísticos.</li>
        <li>Te pedimos por favor contestar con total sinceridad.</li>
        <li>Es necesario que uses <strong>Google Chrome</strong> para desarrollar la valoración, recuerda que debes estar conectado a internet.</li>
		<li>Te recomendamos <strong>revisar permanentemente tu bandeja de correos</strong> no deseados, en caso de que no encuentres en tu carpeta de entrada los mails correspondientes a la medición.</li>
		<li>Este enlace es <strong>personal e intransferible</strong>.</li>
      </ul>
    </div>

	<p><strong>Recuerda que recibirás dos mails, este de cultura y otro de compromiso (engagement) que debe estar en tu bandeja de correo o de no deseados.</strong></p>

	<p>Si tienes dudas o problemas con la encuesta, escríbenos a <a href="mailto:info@occsolutions.org">info@occsolutions.org</a></p>

	{end_date_html}

    <p>De antemano, agradecemos por tu tiempo y tus valiosos aportes en este importante proceso que nos permitirá continuar trabajando por hacer las cosas bien.</p>

	<p>Atentamente,</p>

	<p>Equipo de Experiencia de Personas</p>
	
	<p style="text-align:center;">
      <a href="{unique_url}" class="btn">Iniciar encuesta</a>
    </p>

  </div>
</body>
</html>
					"""
					
						recipients = [contact_email]
						sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id")
						if not sender_email:
							# frappe.log_error("No se ha configurado un remitente de correo por defecto (default_outgoing=1).", "launch_pending_surveys")
							continue

						sender_name = _get_notification_sender_name()
						sender_formatted = formataddr((sender_name, sender_email))
						frappe.sendmail(
							recipients=recipients,
							sender=sender_formatted,
							subject=subject,
							message=message,
							now=True
						)

						frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, {
							"sr_status": rs_sent,
							"sr_sent_on": now()
						})

						# frappe.log_error(f"Correo para la encuesta {survey.name} enviado a {contact_email} (o encolado).", "Survey Task Email Sent")
					except Exception:
						frappe.log_error(f"Error con el destinatario {recipient_doc.name}: {frappe.get_traceback()}", "launch_pending_surveys")
						continue
				frappe.db.commit()
				
			except Exception as e:
				frappe.db.rollback()
				frappe.log_error(f"Error procesando encuesta {survey.name}: {frappe.get_traceback()}", "launch_pending_surveys")

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Error en launch_pending_surveys")

@frappe.whitelist()
def send_survey_reminders():
	# frappe.log_error("Iniciando tarea send_survey_reminders", "Reminder Task Start")
	try:
		now_dt = get_datetime(now())
		today_date = now_dt.date()

		status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "En Progreso"}, "name")
		if not status_in_progress:
			# frappe.log_error("No se encontró el estado 'En Progreso'.", "send_survey_reminders")
			return

		rs_sent = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Sent"}, "name")
		if not rs_sent:
			frappe.log_error("No se encontró el estado 'Sent' en qp_IQ_RecipientStatus.", "send_survey_reminders")
			return

		surveys_in_progress = frappe.get_all(
			"qp_IQ_Survey",
			filters={"su_status": status_in_progress},
			fields=["name", "su_name", "su_start_date", "creation", "su_reminder_frequency", "su_reminder_max"]
		)

		for survey in surveys_in_progress:
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

			# Número de recordatorios esperados según la fecha (sin hora)
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
				fields=["name", "sr_contact", "sr_link", "sr_token", "sr_reminder_send", "sr_last_reminder_send"]
			)

			if not recipients_to_remind:
				continue

			# Obtener ruta del Web Form una sola vez
			web_form_route = frappe.db.get_value("Web Form", {"title": survey.su_name}, "route")
			base_url = frappe.utils.get_url(web_form_route) if web_form_route else None
			if not base_url:
				# frappe.log_error(f"No se encontró Web Form para la encuesta {survey.su_name}.", "send_survey_reminders")
				continue

			contact_names = {
				c.name: c.get("first_name") or c.name
				for c in frappe.get_all("Contact", filters={"name": ["in", [r.sr_contact for r in recipients_to_remind]]}, fields=["name", "first_name"])
			}

			for recipient in recipients_to_remind:
				try:
					# Si aún no alcanza el número esperado de envíos, enviar hoy
					current_sent = int(recipient.sr_reminder_send or 0)
					if current_sent >= expected_sends:
						continue

					link = f"{base_url}?new=1&token={recipient.sr_token}"
					contact_name = contact_names.get(recipient.sr_contact, "Participante")

					message = f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; background-color: #f7f9fc; color: #333333; margin: 0; padding: 0; }}
    .container {{ max-width: 600px; margin: 20px auto; background: #ffffff; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); padding: 30px; }}
    .header {{ text-align: center; border-bottom: 2px solid #e67e22; padding-bottom: 15px; margin-bottom: 20px; }}
    .header h1 {{ color: #e67e22; font-size: 22px; margin: 0; }}
    p {{ text-align: justify; }}
    .btn {{ display: inline-block; background-color: #e67e22; color: #ffffff !important; text-decoration: none; padding: 12px 20px; border-radius: 6px; font-weight: bold; margin-top: 20px; }}
    .info {{ margin: 20px 0; padding: 15px; background-color: #fff7f0; border-left: 4px solid #e67e22; }}
    .footer {{ font-size: 12px; color: #777777; margin-top: 25px; text-align: center; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header"><h1>Recordatorio de Medición</h1></div>
    <p>Hola <strong>{contact_name}</strong>,</p>
    <p>Aún tienes pendiente completar la <strong>encuesta de Medición {survey.su_name}</strong>. Tu participación es fundamental para obtener información valiosa acerca de nuestra compañía y fortalecer nuestra cultura organizacional.</p>
    <div class="info">
      <p><strong>Información importante sobre la encuesta:</strong></p>
      <ul>
        <li>Completarla tomará menos de <strong>20 minutos</strong>.</li>
        <li>Tus respuestas serán manejadas de forma <strong>confidencial</strong> y con fines estadísticos.</li>
        <li>Usa <strong>Google Chrome</strong> y asegúrate de estar conectado a internet.</li>
        <li>Este enlace es <strong>personal e intransferible</strong>.</li>
      </ul>
    </div>
    <p style="text-align:center;"><a href="{link}" class="btn">Responder encuesta</a></p>
    <p>Tu voz es clave en este proceso. ¡Gracias por tu tiempo y compromiso!</p>
    <div class="footer">Si tienes dudas o problemas con la encuesta, escríbenos a <a href="mailto:info@occsolutions.org">info@occsolutions.org</a></div>
  </div>
</body>
</html>
					"""

					contact_email = frappe.db.get_value("Contact", recipient.sr_contact, "email_id")
					if not contact_email:
						# frappe.log_error(f"Contacto {recipient.sr_contact} no tiene email. Saltando recordatorio.", "send_survey_reminders")
						continue

					recipients_list = [contact_email]
					# Se elimina modo debug: siempre se envía al destinatario real

					# Remitente solo desde Email Account por defecto
					sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id")
					if not sender_email:
						# frappe.log_error("No se ha configurado un remitente de correo por defecto.", "send_survey_reminders")
						continue

					sender_name = _get_notification_sender_name()
					sender_formatted = formataddr((sender_name, sender_email))
					frappe.sendmail(
						recipients=recipients_list,
						sender=sender_formatted,
						subject=f"Recordatorio: Encuesta de Medición - {survey.su_name}",
						message=message,
						now=True
					)

					# Actualizar contadores de recordatorio
					next_count = current_sent + 1
					next_reminder_date = None
					if next_count < max_allowed:
						# Calcular próxima fecha esperada (solo para referencia)
						if is_daily:
							next_reminder_date = add_to_date(base_date, days=(next_count)).date()
						else:
							next_reminder_date = add_to_date(base_date, days=(7 * next_count)).date()

					frappe.db.set_value("qp_IQ_SurveyRecipient", recipient.name, {
						"sr_reminder_send": next_count,
						"sr_last_reminder_send": now_dt,
						"sr_next_reminder": next_reminder_date
					})
					frappe.db.commit()
					# frappe.log_error(f"Recordatorio para encuesta {survey.name} enviado a {recipients_list[0]}.", "send_survey_reminders")

				except Exception:
					frappe.db.rollback()
					frappe.log_error(f"Error enviando recordatorio para destinatario {recipient.name}: {frappe.get_traceback()}", "send_survey_reminders")

	except Exception:
		frappe.log_error(frappe.get_traceback(), "Error en send_survey_reminders")

def update_finished_surveys():
	frappe.log_error("Iniciando tarea update_finished_surveys, Hora: {}".format(now()), "Survey Finish Task Start")
	try:
		status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "En Progreso"}, "name")
		if not status_in_progress:
			frappe.log_error("No se encontró el estado 'En Progreso'.", "update_finished_surveys")
			return

		status_finished = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")
		if not status_finished:
			frappe.log_error("No se encontró el estado 'Finalizada'.", "update_finished_surveys")
			return

		rs_responded = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Responded"}, "name")
		if not rs_responded:
			frappe.log_error("No se encontró el estado 'Responded' en qp_IQ_RecipientStatus.", "update_finished_surveys")
			return

		surveys_to_check = frappe.get_all(
			"qp_IQ_Survey",
			filters={"su_status": status_in_progress},
			fields=["name", "su_end_date"]
		)

		for survey in surveys_to_check:
			try:
				survey_doc = frappe.get_doc("qp_IQ_Survey", survey.name)
				current_local = _now_in_survey_tz(survey_doc).replace(tzinfo=None)

				if survey.su_end_date:
					end_dt = get_datetime(survey.su_end_date)
					if current_local >= end_dt:
						frappe.db.set_value("qp_IQ_Survey", survey.name, "su_status", status_finished)
						frappe.db.commit()
						frappe.log_error(f"Encuesta {survey.name} finalizada por fecha.", "update_finished_surveys")
						continue

				total_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey.name})
				if total_recipients > 0:
					responded_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey.name, "sr_status": rs_responded})
					if total_recipients == responded_recipients:
						frappe.db.set_value("qp_IQ_Survey", survey.name, "su_status", status_finished)
						frappe.db.commit()
						frappe.log_error(f"Encuesta {survey.name} finalizada por completitud (100%).", "update_finished_surveys")

			except Exception:
				frappe.db.rollback()
				frappe.log_error(f"Error procesando finalización de encuesta {survey.name}: {frappe.get_traceback()}", "update_finished_surveys")
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Error en update_finished_surveys")


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
	try:
		if not survey_name:
			return {"status": "error", "message": "survey_name requerido."}

		survey = frappe.get_doc("qp_IQ_Survey", survey_name)

		# Se verifica que la encuesta esté en progreso
		status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "En Progreso"}, "name")
		if not status_in_progress or survey.su_status != status_in_progress:
			return {"status": "skipped", "message": "La medición no está en progreso. Envío omitido."}

		rs_not_sent = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Not Sent"}, "name")
		rs_sent = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Sent"}, "name")
		if not rs_not_sent or not rs_sent:
			return {"status": "error", "message": "No se encontraron estados 'Not Sent' o 'Sent' en qp_IQ_RecipientStatus."}

		# Buscar destinatarios pendientes
		recipients_docs = frappe.get_all(
			"qp_IQ_SurveyRecipient",
			filters={"sr_survey": survey.name, "sr_status": rs_not_sent},
			fields=["name", "sr_contact"]
		)
		if not recipients_docs:
			return {"status": "success", "message": "No hay destinatarios pendientes por enviar."}

		# Mapa de email y DNI
		contact_details_map = {
			c.name: {"email": c.email_id, "dni": c.custom_document_number}
			for c in frappe.get_all(
				"Contact",
				filters={"name": ["in", [d.sr_contact for d in recipients_docs]]},
				fields=["name", "email_id", "custom_document_number"]
			) if c.email_id and c.custom_document_number
		}

		web_form_route = frappe.db.get_value("Web Form", {"title": survey.su_name}, "route")
		if not web_form_route:
			return {"status": "error", "message": "No se encontró el Web Form de la encuesta."}
		base_url = frappe.utils.get_url(web_form_route)

		subject = f"Bienvenido(a) al proceso de Medición - {survey.su_name}"
		secret = frappe.conf.get("liseniq_jwt_secret") or frappe.conf.get("encryption_key")
		if not secret:
			return {"status": "error", "message": "No se encontró 'liseniq_jwt_secret' ni 'encryption_key'."}

		enviados = 0
		omitidos = 0

		for recipient_doc in recipients_docs:
			try:
				contact_details = contact_details_map.get(recipient_doc.sr_contact)
				if not contact_details:
					omitidos += 1
					continue

				contact_email = contact_details["email"]
				contact_dni = contact_details["dni"]

				payload = {
					"rid": recipient_doc.name,
					"sur": survey.su_name,
					"iat": int(time()),
					"custom_document_number": contact_dni
				}
				try:
					token = jwt.encode(payload, secret, algorithm="HS256")
					if isinstance(token, bytes):
						token = token.decode("utf-8")
				except Exception:
					omitidos += 1
					continue

				unique_url = f"{base_url}?new=1&token={token}"
				try:
					frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, {
						"sr_link": unique_url,
						"sr_token": token
					})
				except Exception as e:
					if "Data too long for column 'sr_link'" in str(e):
						frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, {"sr_token": token})
					else:
						omitidos += 1

				end_date_html = ""
				if getattr(survey, "su_end_date", None):
					end_date_html = f'<p>La fecha máxima para diligenciar esta encuesta es el <strong>{survey.su_end_date}</strong></p>'

				message = f"""
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
      <h1> {survey.su_name} </h1>
    </div>
    <p>Cordial saludo, </p>
	<p>Te damos la bienvenida al proceso de <strong>Medición - {survey.su_name}</strong>, la cual, es de gran valor para nosotros, pues nos arroja información acerca de la percepción que tienes de la cultura actual y nos da claridad de las acciones que debemos implementar para continuar desarrollando una cultura sana y las mejores condiciones para asegurar que vivas la mejor experiencia en tu día a día.</p>

    <div class="info">
      <p><strong>Información importante sobre la encuesta:</strong></p>
      <ul>
        <li>La valoración te tomará menos de 20 minutos para realizarla</li>
        <li>La información que compartas será manejada de manera confidencial y utilizada con fines estadísticos.</li>
        <li>Te pedimos por favor contestar con total sinceridad.</li>
        <li>Es necesario que uses <strong>Google Chrome</strong> para desarrollar la valoración, recuerda que debes estar conectado a internet.</li>
		<li>Te recomendamos <strong>revisar permanentemente tu bandeja de correos</strong> no deseados, en caso de que no encuentres en tu carpeta de entrada los mails correspondientes a la medición.</li>
		<li>Este enlace es <strong>personal e intransferible</strong>.</li>
      </ul>
    </div>

	<p><strong>Recuerda que recibirás dos mails, este de cultura y otro de compromiso (engagement) que debe estar en tu bandeja de correo o de no deseados.</strong></p>

	<p>Si tienes dudas o problemas con la encuesta, escríbenos a <a href="mailto:info@occsolutions.org">info@occsolutions.org</a></p>

	{end_date_html}

    <p>De antemano, agradecemos por tu tiempo y tus valiosos aportes en este importante proceso que nos permitirá continuar trabajando por hacer las cosas bien.</p>

	<p>Atentamente,</p>

	<p>Equipo de Experiencia de Personas</p>
	
	<p style="text-align:center;">
      <a href="{unique_url}" class="btn">Iniciar encuesta</a>
    </p>

  </div>
</body>
</html>
				"""

				recipients = [contact_email]
				sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id")
				if not sender_email:
					omitidos += 1
					continue

				sender_name = _get_notification_sender_name()
				sender_formatted = formataddr((sender_name, sender_email))
				try:
					frappe.sendmail(
						recipients=recipients,
						sender=sender_formatted,
						subject=subject,
						message=message,
						now=True
					)
				except Exception:
					# Si falla el envío, no interrumpe el resto
					frappe.log_error(frappe.get_traceback(), "send_pending_links_for_survey.sendmail")
					omitidos += 1
					continue

				frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, {
					"sr_status": rs_sent,
					"sr_sent_on": now()
				})
				enviados += 1

			except Exception:
				frappe.log_error(f"Error enviando link a recipient {recipient_doc.name}: {frappe.get_traceback()}", "send_pending_links_for_survey")
				omitidos += 1
				continue

		frappe.db.commit()
		return {"status": "success", "sent": enviados, "skipped": omitidos}

	except Exception:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "send_pending_links_for_survey")
		return {"status": "error", "message": "Fallo al enviar enlaces pendientes."}