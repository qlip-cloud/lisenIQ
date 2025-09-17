# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import now
import base64

def launch_pending_surveys():
	"""
	Busca encuestas de IQ cuya fecha de inicio ha pasado y su estado es 'Programada'.
	Actualiza el estado de estas encuestas a 'En Progreso'.
	"""
	frappe.log_error("Iniciando tarea launch_pending_surveys", "Survey Task Start")
	try:
		# Obtener el 'name' del estado 'En Progreso' desde el Doctype qp_IQ_SurveyStatus
		status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "En Progreso"}, "name")
		if not status_in_progress:
			frappe.log_error("No se encontró el estado 'En Progreso' en qp_IQ_SurveyStatus.", "launch_pending_surveys")
			return

		# Obtener el 'name' del estado 'Programada'
		status_scheduled = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Programada"}, "name")
		if not status_scheduled:
			frappe.log_error("No se encontró el estado 'Programada' en qp_IQ_SurveyStatus.", "launch_pending_surveys")
			return

		frappe.log_error(f"Estados: En Progreso='{status_in_progress}', Programada='{status_scheduled}'", "Survey Task Status")

		# Buscar encuestas programadas cuya fecha de inicio ya pasó
		pending_surveys = frappe.get_all(
			"qp_IQ_Survey",
			filters={
				"su_start_date": ["<", now()],
				"su_status": status_scheduled
			},
			fields=["name", "su_name"]
		)

		frappe.log_error(f"Se encontraron {len(pending_surveys)} encuestas pendientes.", "Survey Task Found")

		if not pending_surveys:
			return

		for survey in pending_surveys:
			try:
				frappe.log_error(f"Procesando encuesta: {survey.name} ({survey.su_name})", "Survey Task Processing")
				# Actualizar el estado de la encuesta a 'En Progreso'
				frappe.db.set_value("qp_IQ_Survey", survey.name, "su_status", status_in_progress)

				# Obtener la ruta del Web Form
				web_form_route = frappe.db.get_value("Web Form", {"title": survey.su_name}, "route")
				if not web_form_route:
					frappe.log_error(f"No se encontró Web Form para la encuesta {survey.su_name}", "launch_pending_surveys")
					continue

				# Obtener destinatarios desde el nuevo Doctype
				recipients_docs = frappe.get_all(
					"qp_IQ_SurveyRecipient",
					filters={"sr_survey": survey.name, "sr_status": "Not Sent"},
					fields=["name", "sr_contact"]
				)

				if not recipients_docs:
					frappe.log_error(f"Encuesta {survey.name} no tiene destinatarios pendientes. Saltando.", "Survey Task Skip")
					continue
				
				# Obtener los correos electrónicos y DNI de los contactos
				contact_details_map = {
					c.name: {"email": c.email_id, "dni": c.custom_document_number}
					for c in frappe.get_all(
						"Contact",
						filters={"name": ["in", [d.sr_contact for d in recipients_docs]]},
						fields=["name", "email_id", "custom_document_number"]
					) if c.email_id and c.custom_document_number
				}

				# Preparar y enviar el correo para cada destinatario
				subject = f"Bienvenido(a) al proceso de Medición - {survey.su_name}"

				for recipient_doc in recipients_docs:
					contact_details = contact_details_map.get(recipient_doc.sr_contact)
					if not contact_details:
						frappe.log_error(f"Contacto {recipient_doc.sr_contact} no tiene email o DNI. Saltando.", "Survey Task Skip Contact")
						continue

					contact_email = contact_details["email"]
					contact_dni = contact_details["dni"]

					# Generar y guardar el enlace único
					timestamp = now()
					payload = f"{contact_dni}|{timestamp}".encode('utf-8')
					encoded_id = base64.b64encode(payload).decode('utf-8')
					
					base_url = frappe.utils.get_url(web_form_route)
					unique_url = f"{base_url}?new=1&id={encoded_id}"
					frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, "sr_link", unique_url)

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
					# Debug de envío de correos
					if frappe.conf.get("send_emails_for_debug"):
						debug_recipient = frappe.conf.get("debug_email_recipient")
						if debug_recipient:
							recipients = [debug_recipient]
							frappe.log_error(f"Modo DEBUG activo. Redirigiendo correo a: {recipients}", "Survey Task Debug Email")
						else:
							frappe.log_error("Modo debug de correo activo pero 'debug_email_recipient' no está configurado.", "launch_pending_surveys")
							continue

					# Obtener el remitente desde la configuración o usar un valor por defecto
					sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id") or frappe.conf.get("debug_email_recipient")

					if not sender_email:
						frappe.log_error("No se ha configurado un remitente de correo por defecto (default_outgoing=1).", "launch_pending_surveys")
						continue
					
					frappe.log_error(f"Intentando enviar correo. De: {sender_email}, Para: {recipients}", "Survey Task Sending Email")

					frappe.sendmail(
						recipients=recipients,
						sender=sender_email,
						subject=subject,
						message=message,
						now=True
					)

					# Actualizar estado del destinatario
					frappe.db.set_value("qp_IQ_SurveyRecipient", recipient_doc.name, {
						"sr_status": "Sent",
						"sr_sent_on": now()
					})

					frappe.log_error(f"Correo para la encuesta {survey.name} enviado a {contact_email} (o encolado).", "Survey Task Email Sent")

				frappe.db.commit()
			except Exception as e:
				frappe.db.rollback()
				frappe.log_error(f"Error procesando encuesta {survey.name}: {frappe.get_traceback()}", "launch_pending_surveys")

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Error en launch_pending_surveys")

