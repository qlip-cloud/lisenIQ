"""
Model for tracking batch processing progress of IQ reports (Cultura, Leadership 360).

This DocType stores the state of incremental report generation:
- survey_id, report_type (iqCultura, iq360)
- current_batch (which batch we're on)
- total_responses (total responses to process)
- processed_responses (count of responses processed so far)
- status (not_started, in_progress, completed, failed)
- error_message (if status=failed)
- last_update (for debugging)
"""

import frappe
from frappe.model.document import Document


class QpIqReportProgress(Document):
    """Track batch processing progress for IQ reports."""
    
    pass


def create_report_progress(survey_id, report_type, total_responses, batch_size=None):
    """
    Create a progress tracking document for a report generation.
    
    Args:
        survey_id: ID of qp_IQ_Survey
        report_type: 'iqCultura' or 'iq360'
        total_responses: Total number of responses to process
        batch_size: Optional batch size (uses defaults if not provided)
    
    Returns:
        Document name (progress record ID)
    """
    doc = frappe.new_doc('qp_IQ_Report_Progress')
    doc.survey_id = survey_id
    doc.report_type = report_type
    doc.total_responses = total_responses
    doc.batch_size = batch_size or _get_default_batch_size(report_type)
    doc.current_batch = 0
    doc.processed_responses = 0
    doc.status = 'not_started'
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


def get_report_progress(survey_id, report_type):
    """Get existing progress record for a survey/report type."""
    return frappe.db.get_value(
        'qp_IQ_Report_Progress',
        {'survey_id': survey_id, 'report_type': report_type},
        'name'
    )


def update_progress(progress_name, **kwargs):
    """Update progress tracking fields."""
    frappe.db.set_value('qp_IQ_Report_Progress', progress_name, kwargs, update_modified=False)
    frappe.db.commit()


def _get_default_batch_size(report_type):
    """Get default batch size by report type."""
    defaults = {
        'iqCultura': 1000,
        'iq360': 500,
    }
    return defaults.get(report_type, 1000)
