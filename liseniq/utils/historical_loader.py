# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import pytz
from datetime import datetime, timedelta, timezone
from frappe.utils import get_datetime

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

def _get_max_days_to_historic() -> int:
	"""
	Obtiene el número de días a esperar antes de archivar desde los parámetros.
	Usa 7 días como fallback.
	"""
	try:
		cache_key = "liseniq_max_days_to_historic"
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			return int(cached)

		param = frappe.db.get_value(
			"qp_IQ_Parameters",
			{"pa_abbreviation": "max_days_to_historic"},
			["pa_data_type", "pa_data_numeric"],
			as_dict=True
		)
		if param:
			data_type = (param.get("pa_data_type") or "").strip().lower()
			if data_type.startswith("num") and param.get("pa_data_numeric") is not None:
				value = int(param.get("pa_data_numeric"))
				frappe.cache().set_value(cache_key, value)
				return value
	except Exception:
		frappe.log_error(frappe.get_traceback(), "_get_max_days_to_historic")
	
	return 7

def _is_ready_for_archiving(survey_doc) -> bool:
	if not getattr(survey_doc, "su_end_date", None):
		return False
	try:
		days_to_wait = _get_max_days_to_historic()
		end_dt = get_datetime(survey_doc.su_end_date)
		now_dt = _now_in_survey_tz(survey_doc).replace(tzinfo=None)
		return (now_dt - end_dt) >= timedelta(days=days_to_wait)
	except Exception:
		return False

def _find_survey_doc_name_by_title(title: str):
	return frappe.db.get_value("Survey", {"title": title}, "name")

def _resolve_contact_from_response(user_value: str, response_json: str):
	# Match directo por nombre: Survey Response.user -> Contact.name
	if user_value:
		if frappe.db.exists("Contact", {"name": user_value}):
			return user_value

	# Fallback por número de documento extraído de la respuesta
	doc_number = None
	try:
		payload = frappe.parse_json(response_json) if response_json else {}
		doc_number = payload.get("custom_document_number") or payload.get("document_number")
	except Exception:
		pass

	if doc_number:
		return frappe.db.get_value("Contact", {"custom_document_number": doc_number}, "name")

	return None

def _get_contact_fields(contact_name: str):
	return frappe.db.get_value(
		"Contact",
		contact_name,
		["first_name", "last_name", "custom_document_type", "custom_document_number", "custom_company"],
		as_dict=True,
	)

def _get_contact_demographics(contact_name: str) -> list:
	"""
	Obtiene los detalles demográficos de la tabla hija del contacto
	y los devuelve como una lista de diccionarios para la tabla histórica.
	"""
	try:
		details = frappe.get_all(
			"qp_IQ_ContactAdditionalDetail",
			filters={"parent": contact_name, "parenttype": "Contact"},
			fields=["cad_demographic_type", "cad_tag", "cad_value"]
		)
		if not details:
			return []
		
		historic_details = []
		for detail in details:
			historic_details.append({
				"doctype": "qp_IQ_ContactDetailHistoric",
				"cdh_demographic_type": detail.get("cad_demographic_type"),
				"cdh_tag": detail.get("cad_tag"),
				"cdh_value": detail.get("cad_value"),
			})
		return historic_details
	except Exception:
		frappe.log_error(frappe.get_traceback(), "historical_loader._get_contact_demographics")
		return []


def _already_archived(survey_id: str, document_number: str) -> bool:
	if not document_number:
		return False
	return bool(
		frappe.db.exists(
			"qp_IQ_SurveyHistoricData",
			{"shd_survey_id": survey_id, "shd_document_number": document_number},
		)
	)

def _insert_historic_row(survey_id: str, survey_name: str, contact_name: str, contact_data: dict, response_json: str):
	full_name_parts = [contact_data.get("first_name") or "", contact_data.get("last_name") or ""]
	full_name = " ".join([p for p in full_name_parts if p]).strip()
	demographics_list = _get_contact_demographics(contact_name)
	doc = frappe.get_doc({
		"doctype": "qp_IQ_SurveyHistoricData",
		"shd_survey_id": survey_id,
		"shd_survey_name": survey_name,
		"shd_contact_name": full_name,
		"shd_document_type": contact_data.get("custom_document_type"),
		"shd_document_number": contact_data.get("custom_document_number"),
		"shd_demographics": demographics_list,
		"shd_measurement_response": response_json,
		"shd_company": contact_data.get("custom_company"),
	})
	doc.insert(ignore_permissions=True)

def archive_finished_surveys_to_history():
	try:
		frappe.log_error("Inicio de pase a histórico", "archive_finished_surveys_to_history")
		status_finished = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")
		if not status_finished:
			frappe.log_error("Estado 'Finalizada' no encontrado en qp_IQ_SurveyStatus", "archive_finished_surveys_to_history")
			return

		surveys = frappe.get_all(
			"qp_IQ_Survey",
			filters={
				"su_status": status_finished, 
				"su_end_date": ["is", "set"],
				"su_in_history": 0
			},
			fields=["name", "su_name", "su_timezone", "su_end_date"],
		)
		# frappe.log_error(f"Encuestas candidatas: {len(surveys)}", "archive_finished_surveys_to_history")

		total_archived = 0
		total_responses_seen = 0

		for survey in surveys:
			survey_doc = frappe.get_doc("qp_IQ_Survey", survey.name)
			if not _is_ready_for_archiving(survey_doc):
				continue

			# frappe.log_error(f"Procesando encuesta {survey.name} - {survey.su_name}", "archive_finished_surveys_to_history")

			survey_doc_name = _find_survey_doc_name_by_title(survey.su_name)
			if not survey_doc_name:
				frappe.log_error(f"No se encontró Survey por título: {survey.su_name}", "archive_finished_surveys_to_history")
				continue

			responses = frappe.get_all(
				"Survey Response",
				filters={"survey": survey_doc_name},
				fields=["name", "user", "response_json"],
			)
			# frappe.log_error(f"Respuestas encontradas: {len(responses)} para {survey.name}", "archive_finished_surveys_to_history")

			for response in responses:
				total_responses_seen += 1
				try:
					contact_name = _resolve_contact_from_response(response.user, response.response_json)
					if not contact_name:
						continue

					contact_data = _get_contact_fields(contact_name)
					if not contact_data:
						continue

					if _already_archived(survey.name, contact_data.get("custom_document_number")):
						continue

					_insert_historic_row(survey.name, survey.su_name, contact_name, contact_data, response.response_json)
					total_archived += 1
				except Exception:
					frappe.log_error(frappe.get_traceback(), "archive_finished_surveys_to_history_item")
					continue
			
			# Marcar la encuesta como procesada para que no se vuelva a incluir
			frappe.db.set_value("qp_IQ_Survey", survey.name, "su_in_history", 1)

		frappe.db.commit()
		frappe.log_error(f"Fin pase a histórico. Respuestas revisadas: {total_responses_seen}, registros creados: {total_archived}", "archive_finished_surveys_to_history")
	except Exception:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "archive_finished_surveys_to_history")

@frappe.whitelist()
def scheduled_archive_finished_surveys():
	# frappe.log_error("Ejecutando vía scheduler/whitelist", "scheduled_archive_finished_surveys")
	return archive_finished_surveys_to_history()