import json
import frappe
from collections import defaultdict


class BatchProcessor:
    
    def __init__(self, survey_id, report_type, batch_size=None, async_mode=False):
      
        self.survey_id = survey_id
        self.report_type = report_type
        self.async_mode = async_mode
        self.batch_size = batch_size or self._get_default_batch_size()
        self.logger = frappe.logger(f'batch_processor_{report_type}', allow_site=True)
    
    def _get_default_batch_size(self):
        defaults = {'iqCultura': 1000, 'iq360': 500}
        return defaults.get(self.report_type, 1000)
    
    def start_batch_processing(self, total_responses, callback_method, **callback_kwargs):
        
        existing_progress = frappe.db.get_value(
            'qp_IQ_Report_Progress',
            {'survey_id': self.survey_id, 'report_type': self.report_type, 'status': 'in_progress'},
            'name'
        )
        if existing_progress:
            self.logger.warn(f'Batch processing already in progress: {existing_progress}')
            return None
        
    
        progress_doc = frappe.new_doc('qp_IQ_Report_Progress')
        progress_doc.survey_id = self.survey_id
        progress_doc.report_type = self.report_type
        progress_doc.total_responses = total_responses
        progress_doc.batch_size = self.batch_size
        progress_doc.current_batch = 0
        progress_doc.processed_responses = 0
        progress_doc.status = 'in_progress'
        progress_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        progress_name = progress_doc.name
        self.logger.info(f'Batch processing started: {progress_name} | total={total_responses} batch_size={self.batch_size}')
        
        num_batches = (total_responses + self.batch_size - 1) // self.batch_size
        for batch_num in range(num_batches):
            if self.async_mode:
                frappe.enqueue(
                    callback_method,
                    survey_id=self.survey_id,
                    progress_name=progress_name,
                    batch_num=batch_num,
                    batch_size=self.batch_size,
                    **callback_kwargs,
                    queue='long',
                    timeout=600,
                )
            else:
                callback_method(
                    survey_id=self.survey_id,
                    progress_name=progress_name,
                    batch_num=batch_num,
                    batch_size=self.batch_size,
                    **callback_kwargs,
                )
        
        return progress_name
    
    def get_batch_slice(self, all_items, batch_num):
        start = batch_num * self.batch_size
        end = start + self.batch_size
        return all_items[start:end]
    
    @staticmethod
    def update_batch_progress(progress_name, batch_num, processed_count, status='in_progress', error=None):
        
        frappe.db.sql("""
            UPDATE `tabqp_IQ_Report_Progress` 
            SET current_batch = %s, 
                processed_responses = processed_responses + %s, 
                status = %s 
            WHERE name = %s
        """, (batch_num + 1, processed_count, status, progress_name))
        
        if error:
            frappe.db.set_value('qp_IQ_Report_Progress', progress_name, 'error_message', error, update_modified=False)
            
        frappe.db.commit()
    
    @staticmethod
    def finalize_batch_processing(progress_name, finalize_callback):
        progress = frappe.get_doc('qp_IQ_Report_Progress', progress_name)
        if progress.processed_responses < progress.total_responses:
            frappe.logger('batch_processor').warn(
                f'Not all batches processed yet: {progress.processed_responses}/{progress.total_responses}'
            )
            return
        
        try:
            finalize_callback(progress.survey_id, progress_name)
            
            frappe.db.set_value(
                'qp_IQ_Report_Progress',
                progress_name,
                {'status': 'completed'},
                update_modified=False
            )
            frappe.db.commit()
        except Exception as e:
            frappe.logger('batch_processor').error(f'Finalization failed: {str(e)}')
            frappe.db.set_value(
                'qp_IQ_Report_Progress',
                progress_name,
                {'status': 'failed', 'error_message': str(e)},
                update_modified=False
            )
            frappe.db.commit()
            raise

def deserialize_accumulated_data(json_str):
    """Deserialize organizational accumulated data from JSON."""
    if not json_str:
        return {}
    try:
        return json.loads(json_str) if isinstance(json_str, str) else json_str
    except Exception as e:
        frappe.logger('batch_processor').error(f'Error deserializing accumulated data: {str(e)}')
        return {}


def serialize_accumulated_data(data):
    """Serialize accumulated data back to a clean JSON string."""
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        frappe.logger('batch_processor').error(f'Error serializing accumulated data: {str(e)}')
        return "{}"