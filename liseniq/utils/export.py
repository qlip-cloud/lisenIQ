import frappe
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from frappe.utils.pdf import get_pdf
from openpyxl import Workbook
from openpyxl.styles import Alignment


def _sanitize_filename(value):
    value = (value or "").strip()
    safe_chars = []
    for char in value:
        if char.isalnum() or char in (" ", "-", "_", "."):
            safe_chars.append(char)
        else:
            safe_chars.append("_")
    sanitized = "".join(safe_chars).strip().replace(" ", "_")
    return sanitized or "reporte"


def _get_survey_doc(survey_identifier):
    try:
        return frappe.get_doc("qp_IQ_Survey", survey_identifier)
    except Exception:
        return frappe.get_doc("qp_IQ_Survey", {"su_name": survey_identifier})


def _leadership_pdf_options():
    return {
        "page-size": "A4",
        "margin-top": "0mm",
        "margin-bottom": "0mm",
        "margin-left": "0mm",
        "margin-right": "0mm",
        "zoom": "1.5",
        "header-spacing": "0",
        "disable-smart-shrinking": "",
    }


def _ensure_pdf_header_footer_placeholders(html):
    if "id=\"header-html\"" in html and "id=\"footer-html\"" in html:
        return html

    placeholders = "<div id=\"header-html\"></div><div id=\"footer-html\"></div>"
    if "</body>" in html:
        return html.replace("</body>", placeholders + "</body>", 1)
    return html + placeholders

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


@frappe.whitelist()
def export_seguimiento_360(survey_name):
    current_user = frappe.session.user
    frappe.session.user = "Administrator"
    try:
        frappe.flags.ignore_permissions = True
        survey = frappe.get_doc("qp_IQ_Survey", {"su_name": survey_name})
        survey_id = survey.name
        survey_display_name = survey.su_name
        
        REPORT_NAME = "Seguimiento Mediciones 360"
        filters = {"survey": survey_name}

        report = frappe.get_doc("Report", REPORT_NAME)
        columns, data = report.get_data(filters)

        col_labels = [col.get('label', col.get('fieldname', '')) for col in columns]
        col_fields = [col.get('fieldname', '') for col in columns]

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Seguimiento 360"
        sheet.append(col_labels)

        for row in data:
            sheet.append([row.get(field, '') for field in col_fields])

        # Combinar celdas para cada evaluado
        current_evaluated = None
        start_row = 2  # Empezamos en la fila 2 porque la fila 1 tiene los encabezados
        for idx, row in enumerate(data, start=2):
            evaluated = row.get('evaluated')
            if evaluated != current_evaluated:
                if current_evaluated is not None:
                    sheet.merge_cells(start_row=start_row, start_column=1, end_row=idx-1, end_column=1)
                    sheet.cell(row=start_row, column=1).alignment = Alignment(horizontal='left', vertical='center')
                current_evaluated = evaluated
                start_row = idx
        # Merge para el último evaluado
        if current_evaluated is not None:
            sheet.merge_cells(start_row=start_row, start_column=1, end_row=idx, end_column=1)
            sheet.cell(row=start_row, column=1).alignment = Alignment(horizontal='left', vertical='center')

        excel_file = BytesIO()
        workbook.save(excel_file)
        excel_file.seek(0)

        filename = f"{survey_display_name}_seguimiento_360.xlsx"
        
        frappe.local.response.filename = filename
        frappe.local.response.filecontent = excel_file.read()
        frappe.local.response.type = "download"
        frappe.local.response.display_content_as = "attachment"
    finally:
        frappe.flags.ignore_permissions = False
        frappe.session.user = current_user


@frappe.whitelist()
def export_leadership_reports_zip(survey_name):
    current_user = frappe.session.user
    frappe.session.user = "Administrator"
    try:
        frappe.flags.ignore_permissions = True
        survey = _get_survey_doc(survey_name)
        survey_display_name = survey.su_name

        reports = frappe.get_all(
            "qp_IQ_Leader_360_Report",
            filters={"survey_name": survey_display_name},
            fields=["name", "leader_name"],
            order_by="leader_name asc",
        )

        if not reports:
            frappe.throw("No se encontraron informes de liderazgo para esta medición.")

        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as zip_file:
            for report_row in reports:
                report_doc = frappe.get_doc("qp_IQ_Leader_360_Report", report_row.name)
                html = frappe.get_print(
                    "qp_IQ_Leader_360_Report",
                    report_doc.name,
                    print_format="Reporte Individual Liderazgo",
                    as_pdf=False,
                    no_letterhead=1,
                )
                html = _ensure_pdf_header_footer_placeholders(html)
                pdf_bytes = get_pdf(html, options=_leadership_pdf_options())
                leader_name = _sanitize_filename(report_row.leader_name or report_doc.leader_name or report_doc.name)
                zip_file.writestr(f"{leader_name}_{report_doc.name}.pdf", pdf_bytes)

        zip_buffer.seek(0)

        filename = f"{_sanitize_filename(survey_display_name)}_informes_liderazgo.zip"
        frappe.local.response.filename = filename
        frappe.local.response.filecontent = zip_buffer.read()
        frappe.local.response.type = "download"
        frappe.local.response.display_content_as = "attachment"
    finally:
        frappe.flags.ignore_permissions = False
        frappe.session.user = current_user