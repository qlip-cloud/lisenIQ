import frappe
import json


@frappe.whitelist()
def start_cultura_report_generation(survey_id, demographic_field, batch_size=None, async_mode=True):
    async_mode = async_mode in [True, 'true', '1', 1]
    batch_size = int(batch_size) if batch_size else None
    
    try:
        from liseniq.liseniq.uses_cases.iqCultura.report_builder import build_cultura_report_batched
        
        progress_name = build_cultura_report_batched(
            survey_id,
            demographic_field,
            batch_size=batch_size,
            async_mode=async_mode
        )
        
        if progress_name:
            return {
                'status': 'success',
                'progress_name': progress_name,
                'async_mode': async_mode,
                'message': f'Report generation started. Progress: {progress_name}'
            }
        else:
            return {
                'status': 'skipped',
                'message': 'Report generation was skipped (possibly already generated)'
            }
    
    except Exception as e:
        frappe.logger('cultura_report_generation').error(f'Error: {str(e)}')
        return {
            'status': 'error',
            'message': str(e)
        }


@frappe.whitelist()
def start_iq360_report_generation(survey_id, batch_size=None, async_mode=True):
    async_mode = async_mode in [True, 'true', '1', 1]
    batch_size = int(batch_size) if batch_size else None
    
    try:
        from liseniq.liseniq.uses_cases.iq360.report_builder import build_leaders_report_batched
        
        progress_name = build_leaders_report_batched(
            survey_id,
            batch_size=batch_size,
            async_mode=async_mode
        )
        
        if progress_name:
            return {
                'status': 'success',
                'progress_name': progress_name,
                'async_mode': async_mode,
                'message': f'Report generation started. Progress: {progress_name}'
            }
        else:
            return {
                'status': 'skipped',
                'message': 'Report generation was skipped (possibly already generated)'
            }
    
    except Exception as e:
        frappe.logger('iq360_report_generation').error(f'Error: {str(e)}')
        return {
            'status': 'error',
            'message': str(e)
        }


@frappe.whitelist()
def get_progress_status(progress_name):
    try:
        progress_doc = frappe.get_doc('qp_IQ_Report_Progress', progress_name)
        
        percentage = 0
        if progress_doc.total_responses > 0:
            percentage = (progress_doc.processed_responses / progress_doc.total_responses) * 100
        
        return {
            'status': 'success',
            'report_type': progress_doc.report_type,
            'batch_status': progress_doc.status,
            'current_batch': progress_doc.current_batch,
            'processed_responses': progress_doc.processed_responses,
            'total_responses': progress_doc.total_responses,
            'percentage': round(percentage, 2),
            'error_message': progress_doc.error_message or '',
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }
