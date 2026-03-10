import frappe
from io import BytesIO
from openpyxl import Workbook

@frappe.whitelist()
def export_survey_results(survey_name):
    current_user = frappe.session.user
    frappe.session.user = "Administrator"
    try:
        frappe.flags.ignore_permissions = True
        survey = frappe.get_doc("qp_IQ_Survey", survey_name)
        survey_name = survey.su_name
        
        REPORT_NAME = "Survey Response Custom Report Front"
        filters = {"survey": survey_name}

        report = frappe.get_doc("Report", REPORT_NAME)
        columns, data = report.get_data(filters)

        # Separar preguntas abiertas sin modificar el array original mientras se itera
        data_open_questions = []
        data_closed = []

        for row in data:
            variable = row.get('variable', '').lower()
            if "abierta" in variable or "abiertas" in variable:
                data_open_questions.append(row)
            else:
                data_closed.append(row)

        # Extraer headers de columnas
        col_labels = [col.get('label', col.get('fieldname', '')) for col in columns]
        col_fields = [col.get('fieldname', '') for col in columns]

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Resultados de la encuesta"
        sheet.append(col_labels)

        for row in data_closed:
            sheet.append([row.get(field, '') for field in col_fields])

        if data_open_questions:
            open_sheet = workbook.create_sheet(title="Preguntas Abiertas")
            open_sheet.append(col_labels)
            for row in data_open_questions:
                open_sheet.append([row.get(field, '') for field in col_fields])

        excel_file = BytesIO()
        workbook.save(excel_file)
        excel_file.seek(0)

        filename = f"{survey_name}_results.xlsx"
        
        frappe.local.response.filename = filename
        frappe.local.response.filecontent = excel_file.read()
        frappe.local.response.type = "download"
        frappe.local.response.display_content_as = "attachment"
    finally:
        frappe.flags.ignore_permissions = False
        frappe.session.user = current_user

@frappe.whitelist()
def get_demographics():
    """Obtiene la lista de demográficos de tipo Contacto"""
    demographics = frappe.get_all(
        'qp_IQ_DemographicType',
        filters={'dt_object_type': 'Contacto'},
        fields=['name', 'dt_title'],
        order_by='dt_title'
    )
    return demographics

@frappe.whitelist()
def export_follow_up_report(survey_name, demographic1=None, demographic2=None):
    current_user = frappe.session.user
    frappe.session.user = "Administrator"
    try:
        frappe.flags.ignore_permissions = True
        survey = frappe.get_doc("qp_IQ_Survey", survey_name)
        survey_id = survey.name
        survey_display_name = survey.su_name
        
        REPORT_NAME = "Survey Status"
        filters = {"survey": survey_id}

        if demographic1:
            filters["demographic1"] = demographic1
        if demographic2:
            filters["demographic2"] = demographic2

        report = frappe.get_doc("Report", REPORT_NAME)
        columns, data = report.get_data(filters)

        col_labels = [col.get('label', col.get('fieldname', '')) for col in columns]
        col_fields = [col.get('fieldname', '') for col in columns]

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Reporte de Seguimiento"
        sheet.append(col_labels)

        for row in data:
            sheet.append([row.get(field, '') for field in col_fields])

        excel_file = BytesIO()
        workbook.save(excel_file)
        excel_file.seek(0)

        filename = f"{survey_display_name}_seguimiento.xlsx"
        
        frappe.local.response.filename = filename
        frappe.local.response.filecontent = excel_file.read()
        frappe.local.response.type = "download"
        frappe.local.response.display_content_as = "attachment"
    finally:
        frappe.flags.ignore_permissions = False
        frappe.session.user = current_user
