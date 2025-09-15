# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import now

def launch_pending_surveys():
	"""
	Busca encuestas de IQ cuya fecha de inicio ha pasado y su estado es 'Programada'.
	Actualiza el estado de estas encuestas a 'En Progreso'.
	"""
	try:
		# Obtener el 'name' del estado 'En Progreso' desde el Doctype qp_IQ_SurveyStatus
		status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"status_name": "En Progreso"}, "name")
		if not status_in_progress:
			frappe.log_error("No se encontró el estado 'En Progreso' en qp_IQ_SurveyStatus.", "launch_pending_surveys")
			return

		# Obtener el 'name' del estado 'Programada'
		status_scheduled = frappe.get_value("qp_IQ_SurveyStatus", {"status_name": "Programada"}, "name")
		if not status_scheduled:
			frappe.log_error("No se encontró el estado 'Programada' en qp_IQ_SurveyStatus.", "launch_pending_surveys")
			return

		# Buscar encuestas programadas cuya fecha de inicio ya pasó
		pending_surveys = frappe.get_all(
			"qp_IQ_Survey",
			filters={
				"su_start_date": ["<", now()],
				"status": status_scheduled
			},
			fields=["name", "su_name"]
		)

		for survey in pending_surveys:
			try:
				# Actualizar el estado de la encuesta a 'En Progreso'
				frappe.db.set_value("qp_IQ_Survey", survey.name, "status", status_in_progress)

				# Obtener el documento completo de la encuesta
				survey_doc = frappe.get_doc("qp_IQ_Survey", survey.name)
				
				# Obtener los contactos destinatarios
				recipient_contacts = [d.sr_contact for d in survey_doc.get("su_recipients")]
				if not recipient_contacts:
					continue

				# Obtener los correos electrónicos de los contactos
				contact_emails = frappe.get_all(
					"Contact",
					filters={"name": ["in", recipient_contacts], "email_id": ["is", "set"]},
					fields=["email_id"]
				)
				recipients = [d.email_id for d in contact_emails]

				if not recipients:
					continue

				# Obtener la ruta del Web Form
				web_form_route = frappe.db.get_value("Web Form", {"title": survey.su_name}, "route")
				if not web_form_route:
					frappe.log_error(f"No se encontró Web Form para la encuesta {survey.su_name}", "launch_pending_surveys")
					continue
				
				survey_url = frappe.utils.get_url(web_form_route)

				# Preparar y enviar el correo
				subject = f"Invitación para completar la medición: {survey.su_name}"
				message = f"""
					<p>Hola,</p>
					<p>Has sido invitado a participar en la siguiente medición: <strong>{survey.su_name}</strong>.</p>
					<p>Por favor, haz clic en el siguiente enlace para comenzar:</p>
					<p><a href="{survey_url}">{survey_url}</a></p>
					<p>Gracias.</p>
				"""
				
				frappe.sendmail(
					recipients=recipients,
					subject=subject,
					message=message,
					now=True
				)

				frappe.db.commit()
			except Exception as e:
				frappe.db.rollback()
				frappe.log_error(f"Error procesando encuesta {survey.name}: {frappe.get_traceback()}", "launch_pending_surveys")

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Error en launch_pending_surveys")

