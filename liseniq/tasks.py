# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import now

def launch_pending_surveys():
	"""
	Busca encuestas de IQ cuya fecha de inicio ha pasado y su estado es 'Programada'.
	Actualiza el estado de estas encuestas a 'En Progreso'.
	"""
	frappe.log_error("Iniciando tarea launch_pending_surveys", "DEBUG PING")
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

		frappe.log_error(f"Estados: En Progreso='{status_in_progress}', Programada='{status_scheduled}'", "DEBUG PING")

		# Buscar encuestas programadas cuya fecha de inicio ya pasó
		pending_surveys = frappe.get_all(
			"qp_IQ_Survey",
			filters={
				"su_start_date": ["<", now()],
				"su_status": status_scheduled
			},
			fields=["name", "su_name"]
		)

		frappe.log_error(f"Se encontraron {len(pending_surveys)} encuestas pendientes.", "DEBUG PING")

		if not pending_surveys:
			return

		for survey in pending_surveys:
			try:
				frappe.log_error(f"Procesando encuesta: {survey.name} ({survey.su_name})", "DEBUG PING")
				# Actualizar el estado de la encuesta a 'En Progreso'
				frappe.db.set_value("qp_IQ_Survey", survey.name, "su_status", status_in_progress)

				# Obtener la ruta del Web Form
				web_form_route = frappe.db.get_value("Web Form", {"title": survey.su_name}, "route")
				if not web_form_route:
					frappe.log_error(f"No se encontró Web Form para la encuesta {survey.su_name}", "launch_pending_surveys")
					continue

				# Obtener destinatarios desde el nuevo Doctype
				recipients_docs = frappe.get_all(
					"qp_IQ_Survey_Recipient",
					filters={"sr_survey": survey.name, "sr_status": "Not Sent"},
					fields=["name", "sr_contact"]
				)

				if not recipients_docs:
					frappe.log_error(f"Encuesta {survey.name} no tiene destinatarios pendientes. Saltando.", "DEBUG PING")
					continue
				
				# Obtener los correos electrónicos de los contactos
				contact_to_email_map = {
					c.name: c.email_id for c in frappe.get_all(
						"Contact",
						filters={"name": ["in", [d.sr_contact for d in recipients_docs]]},
						fields=["name", "email_id"]
					) if c.email_id
				}

				# Preparar y enviar el correo para cada destinatario
				subject = f"Invitación para completar la medición: {survey.su_name}"

				for recipient_doc in recipients_docs:
					contact_email = contact_to_email_map.get(recipient_doc.sr_contact)
					if not contact_email:
						continue

					# Generar y guardar el enlace único
					base_url = frappe.utils.get_url(web_form_route)
					unique_url = f"{base_url}?recipient_id={recipient_doc.name}"
					frappe.db.set_value("qp_IQ_Survey_Recipient", recipient_doc.name, "sr_unique_url", unique_url)

					message = f"""
						<p>Hola,</p>
						<p>Has sido invitado a participar en la siguiente medición: <strong>{survey.su_name}</strong>.</p>
						<p>Por favor, haz clic en el siguiente enlace para comenzar:</p>
						<p><a href="{unique_url}">{unique_url}</a></p>
						<p>Gracias.</p>
					"""
					
					recipients = [contact_email]
					# Debug de envío de correos
					if frappe.conf.get("send_emails_for_debug"):
						debug_recipient = frappe.conf.get("debug_email_recipient")
						if debug_recipient:
							recipients = [debug_recipient]
							frappe.log_error(f"Modo DEBUG activo. Redirigiendo correo a: {recipients}", "DEBUG PING")
						else:
							frappe.log_error("Modo debug de correo activo pero 'debug_email_recipient' no está configurado.", "launch_pending_surveys")
							continue

					# Obtener el remitente desde la configuración o usar un valor por defecto
					sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id") or frappe.conf.get("debug_email_recipient")

					if not sender_email:
						frappe.log_error("No se ha configurado un remitente de correo por defecto (default_outgoing=1).", "launch_pending_surveys")
						continue
					
					frappe.log_error(f"Intentando enviar correo. De: {sender_email}, Para: {recipients}", "DEBUG PING")

					frappe.sendmail(
						recipients=recipients,
						sender=sender_email,
						subject=subject,
						message=message,
						now=True
					)

					# Actualizar estado del destinatario
					frappe.db.set_value("qp_IQ_Survey_Recipient", recipient_doc.name, {
						"sr_status": "Sent",
						"sr_sent_on": now()
					})

					frappe.log_error(f"Correo para la encuesta {survey.name} enviado a {contact_email} (o encolado).", "DEBUG PING")

				frappe.db.commit()
			except Exception as e:
				frappe.db.rollback()
				frappe.log_error(f"Error procesando encuesta {survey.name}: {frappe.get_traceback()}", "launch_pending_surveys")

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Error en launch_pending_surveys")

