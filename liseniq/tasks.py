# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import now
from frappe.utils.data import get_datetime, add_to_date
import jwt
from time import time

def launch_pending_surveys():
	# frappe.log_error("Iniciando tarea launch_pending_surveys", "Survey Task Start")
	try:
		status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "En Progreso"}, "name")
		if not status_in_progress:
			# frappe.log_error("No se encontró el estado 'En Progreso' en qp_IQ_SurveyStatus.", "launch_pending_surveys")
			return

		status_scheduled = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Programada"}, "name")
		if not status_scheduled:
			# frappe.log_error("No se encontró el estado 'Programada' en qp_IQ_SurveyStatus.", "launch_pending_surveys")
			return

		# frappe.log_error(f"Estados: En Progreso='{status_in_progress}', Programada='{status_scheduled}'", "Survey Task Status")

		pending_surveys = frappe.get_all(
			"qp_IQ_Survey",
			filters={
				"su_start_date": ["<", now()],
				"su_status": status_scheduled
			},
			fields=["name", "su_name"]
		)

		# frappe.log_error(f"Se encontraron {len(pending_surveys)} encuestas pendientes.", "Survey Task Found")

		if not pending_surveys:
			return

		for survey in pending_surveys:
			try:
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
					filters={"sr_survey": survey.name, "sr_status": "Not Sent"},
					fields=["name", "sr_contact"]
				)

				if not recipients_docs:
					# frappe.log_error(f"Encuesta {survey.name} no tiene destinatarios pendientes. Saltando.", "Survey Task Skip")
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
							# frappe.log_error("No se encontró 'liseniq_jwt_secret' ni 'encryption_key' para firmar JWT.", "launch_pending_surveys")
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
    <p>Hola,</p>
    <p>Te damos la bienvenida al <strong>proceso de Medición - {survey.su_name}</strong>, una iniciativa clave que nos permitirá obtener información valiosa acerca de nuestra compañía y avanzar en nuestro propósito de mejora continua.</p>

    <div class="info">
      <p><strong>Información importante sobre la encuesta:</strong></p>
      <ul>
        <li>Completarla tomará menos de <strong>20 minutos</strong>.</li>
        <li>Tus respuestas serán manejadas de forma <strong>confidencial</strong> y con fines estadísticos.</li>
        <li>Usa <strong>Google Chrome</strong> y asegúrate de estar conectado a internet.</li>
        <li>Este enlace es <strong>personal e intransferible</strong>.</li>
      </ul>
    </div>

    <p style="text-align:center;">
      <a href="{unique_url}" class="btn">Iniciar encuesta</a>
    </p>

    <p>Agradecemos de antemano tu tiempo y tus valiosos aportes en este importante proceso.</p>

    <div class="footer">
      Si tienes dudas o problemas con la encuesta, escríbenos a <a href="mailto:info@occsolutions.org">info@occsolutions.org</a>
    </div>
  </div>
</body>
</html>
					"""
					
						recipients = [contact_email]
						if frappe.conf.get("send_emails_for_debug"):
							debug_recipient = frappe.conf.get("debug_email_recipient")
							if debug_recipient:
								recipients = [debug_recipient]
								# frappe.log_error(f"Modo DEBUG activo. Redirigiendo correo a: {recipients}", "Survey Task Debug Email")
							else:
								# frappe.log_error("Modo debug de correo activo pero 'debug_email_recipient' no está configurado.", "launch_pending_surveys")
								continue

						sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id") or frappe.conf.get("debug_email_recipient")

						if not sender_email:
							# frappe.log_error("No se ha configurado un remitente de correo por defecto (default_outgoing=1).", "launch_pending_surveys")
							continue
					
						# frappe.log_error(f"Intentando enviar correo. De: {sender_email}, Para: {recipients}", "Survey Task Sending Email")

						frappe.sendmail(
							recipients=recipients,
							sender=sender_email,
							subject=subject,
							message=message,
							now=True
						)

						frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, {
							"sr_status": "Sent",
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

		surveys_in_progress = frappe.get_all(
			"qp_IQ_Survey",
			filters={"su_status": status_in_progress},
			fields=["name", "su_name", "su_start_date", "creation", "su_reminder_frequency", "su_reminder_max"]
		)

		for survey in surveys_in_progress:
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
				# Si la fecha base es futura, no enviar
				continue

			freq_raw = (survey.su_reminder_frequency or "").strip().lower()
			is_daily = freq_raw.startswith("diari")   # "Diaria" / "Diario"
			is_weekly = freq_raw.startswith("seman")  # "Semanal"

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
					"sr_status": "Sent",
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
					if frappe.conf.get("send_emails_for_debug"):
						debug_recipient = frappe.conf.get("debug_email_recipient")
						if debug_recipient:
							recipients_list = [debug_recipient]
							# frappe.log_error(f"Modo DEBUG activo. Redirigiendo correo de recordatorio a: {recipients_list}", "send_survey_reminders")
						else:
							# frappe.log_error("Modo debug de correo activo pero 'debug_email_recipient' no está configurado.", "send_survey_reminders")
							continue

					sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id") or frappe.conf.get("debug_email_recipient")
					if not sender_email:
						# frappe.log_error("No se ha configurado un remitente de correo por defecto.", "send_survey_reminders")
						continue

					frappe.sendmail(
						recipients=recipients_list,
						sender=sender_email,
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
	# frappe.log_error("Iniciando tarea update_finished_surveys", "Survey Finish Task Start")
	try:
		status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "En Progreso"}, "name")
		if not status_in_progress:
			# frappe.log_error("No se encontró el estado 'En Progreso'.", "update_finished_surveys")
			return

		status_finished = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")
		if not status_finished:
			# frappe.log_error("No se encontró el estado 'Finalizada'.", "update_finished_surveys")
			return

		surveys_to_check = frappe.get_all(
			"qp_IQ_Survey",
			filters={"su_status": status_in_progress},
			fields=["name", "su_end_date"]
		)

		today = get_datetime(now()).date()

		for survey in surveys_to_check:
			try:
				if survey.su_end_date:
					end_date = get_datetime(survey.su_end_date).date()
					if today > end_date:
						frappe.db.set_value("qp_IQ_Survey", survey.name, "su_status", status_finished)
						frappe.db.commit()
						# frappe.log_error(f"Encuesta {survey.name} finalizada por fecha.", "update_finished_surveys")
						continue

				total_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey.name})
				if total_recipients > 0:
					responded_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey.name, "sr_status": "Responded"})
					if total_recipients == responded_recipients:
						frappe.db.set_value("qp_IQ_Survey", survey.name, "su_status", status_finished)
						frappe.db.commit()
						# frappe.log_error(f"Encuesta {survey.name} finalizada por completitud (100%).", "update_finished_surveys")

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
            # frappe.log_error(f"No se encontró la encuesta de IQ: {survey_name}", "delete_iq_survey_fully")
            return f"Error: No se encontró la encuesta de IQ: {survey_name}"

        recipient_names = frappe.get_all("qp_IQ_SurveyRecipient", filters={"sr_survey": survey_name}, pluck="name")
        for recipient_name in recipient_names:
            frappe.delete_doc("qp_IQ_SurveyRecipient", recipient_name, force=1, ignore_permissions=True)
        # frappe.log_error(f"Eliminados {len(recipient_names)} destinatarios para {survey_name}", "delete_iq_survey_fully")

        web_form_name = frappe.db.get_value("Web Form", {"title": web_form_title}, "name")
        if web_form_name:
            survey_doc_name = frappe.db.get_value("Survey", {"title": web_form_title}, "name")
            if survey_doc_name:
                response_names = frappe.get_all("Survey Response", filters={"survey": survey_doc_name}, pluck="name")
                for response_name in response_names:
                    frappe.delete_doc("Survey Response", response_name, force=1, ignore_permissions=True)
                # frappe.log_error(f"Eliminadas {len(response_names)} respuestas para la encuesta {survey_doc_name}", "delete_iq_survey_fully")
                
                frappe.delete_doc("Survey", survey_doc_name, force=1, ignore_permissions=True)
                # frappe.log_error(f"Eliminado el doctype Survey: {survey_doc_name}", "delete_iq_survey_fully")

            frappe.delete_doc("Web Form", web_form_name, force=1, ignore_permissions=True)
            # frappe.log_error(f"Eliminado Web Form: {web_form_name}", "delete_iq_survey_fully")

        frappe.delete_doc("qp_IQ_Survey", survey_name, force=1, ignore_permissions=True)
        # frappe.log_error(f"Eliminada encuesta de IQ: {survey_name}", "delete_iq_survey_fully")

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
            # frappe.log_error(message, "delete_all_iq_surveys")
            return message

        total_surveys = len(all_surveys)
        # frappe.log_error(f"Se encontraron {total_surveys} encuestas de IQ para eliminar. Iniciando proceso...", "delete_all_iq_surveys")

        for i, survey_name in enumerate(all_surveys):
            delete_iq_survey_fully(survey_name)
        
        success_message = f"Proceso completado. Se eliminaron {total_surveys} encuestas de IQ."
        # frappe.log_error(success_message, "delete_all_iq_surveys")
        return success_message

    except Exception as e:
        frappe.db.rollback()
        error_message = f"Ocurrió un error durante la eliminación masiva: {frappe.get_traceback()}"
        # frappe.log_error(error_message, "delete_all_iq_surveys")
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

		# Buscar destinatarios pendientes
		recipients_docs = frappe.get_all(
			"qp_IQ_SurveyRecipient",
			filters={"sr_survey": survey.name, "sr_status": "Not Sent"},
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
    <p>Hola,</p>
    <p>Te damos la bienvenida al <strong>proceso de Medición - {survey.su_name}</strong>, una iniciativa clave que nos permitirá obtener información valiosa acerca de nuestra compañía y avanzar en nuestro propósito de mejora continua.</p>

    <div class="info">
      <p><strong>Información importante sobre la encuesta:</strong></p>
      <ul>
        <li>Completarla tomará menos de <strong>20 minutos</strong>.</li>
        <li>Tus respuestas serán manejadas de forma <strong>confidencial</strong> y con fines estadísticos.</li>
        <li>Usa <strong>Google Chrome</strong> y asegúrate de estar conectado a internet.</li>
        <li>Este enlace es <strong>personal e intransferible</strong>.</li>
      </ul>
    </div>

    <p style="text-align:center;">
      <a href="{unique_url}" class="btn">Iniciar encuesta</a>
    </p>

    <p>Agradecemos de antemano tu tiempo y tus valiosos aportes en este importante proceso.</p>

    <div class="footer">
      Si tienes dudas o problemas con la encuesta, escríbenos a <a href="mailto:info@occsolutions.org">info@occsolutions.org</a>
    </div>
  </div>
</body>
</html>
				"""

				recipients = [contact_email]
				if frappe.conf.get("send_emails_for_debug"):
					debug_recipient = frappe.conf.get("debug_email_recipient")
					if debug_recipient:
						recipients = [debug_recipient]
					else:
						omitidos += 1
						continue

				sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id") or frappe.conf.get("debug_email_recipient")
				if not sender_email:
					omitidos += 1
					continue

				frappe.sendmail(
					recipients=recipients,
					sender=sender_email,
					subject=subject,
					message=message,
					now=True
				)

				frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, {
					"sr_status": "Sent",
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