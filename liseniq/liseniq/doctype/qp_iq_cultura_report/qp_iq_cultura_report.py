# Copyright (c) 2026, Mentum Group and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from liseniq.liseniq.uses_cases.iqCultura.report_builder import build_cultura_report

class qp_IQ_Cultura_Report(Document):
	pass


@frappe.whitelist()
def generate_cultura_reports(survey_id, demographic_field):
	"""
	Generate culture survey reports by demographic cutoff.
	
	Args:
		survey_id: ID of the qp_IQ_Survey
		demographic_field: Field name to group by (e.g., 'custom_area', 'custom_department')
	
	Returns:
		String message with result
"""
	logger = frappe.logger('generate_cultura_reports', allow_site=True)
	logger.info(f'START generate_cultura_reports | survey_id={survey_id} demographic_field={demographic_field}')
	print(f'\n=== START generate_cultura_reports | survey_id={survey_id} demographic_field={demographic_field}')
	
	try:
		logger.info('Validando survey...')
		print('Validando survey...')
		survey = frappe.get_doc('qp_IQ_Survey', survey_id)
		if not survey:
			logger.error(f'Survey no encontrada: {survey_id}')
			return frappe.throw(frappe.DoesNotExistError(f'Survey {survey_id} not found'))
		
		logger.info(f'Survey encontrada: {survey.su_name}')
		print(f'Survey encontrada: {survey.su_name}')
		
		logger.info('Llamando build_cultura_report...')
		print('Llamando build_cultura_report...')
		result = build_cultura_report(survey_id, demographic_field)
		logger.info(f'build_cultura_report completado con resultado: {result}')
		print(f'build_cultura_report completado con resultado: {result}')
		
		if result:
			msg = f'Informes generados exitosamente para la medición {survey.su_name}'
			logger.info(f'ÉXITO: {msg}')
			print(f'ÉXITO: {msg}')
			return msg
		else:
			logger.error('build_cultura_report retornó False')
			print('build_cultura_report retornó False')
			return frappe.throw('No se pudieron generar los informes')
		
	except Exception as e:
		logger.error(f'EXCEPTION: {type(e).__name__}: {str(e)}')
		logger.exception('Stack trace:')
		print(f'\n!!! EXCEPTION: {type(e).__name__}: {str(e)}')
		import traceback
		print(traceback.format_exc())
		return frappe.throw(f'Error al generar informes: {str(e)}')


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_demographic_fields():
	"""Get list of demographic fields available for grouping in the survey"""
	fields = frappe.get_all(
		'qp_IQ_DemographicType',
		fields=['dt_field_name', 'dt_title'],
		filters={'dt_object_type': 'Contacto'}
	)
	return [{'field_name': f.dt_field_name, 'title': f.dt_title} for f in fields]