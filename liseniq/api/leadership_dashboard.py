# -*- coding: utf-8 -*-
"""
API del dashboard Liderazgo 360° (ERPNext / Frappe v13).
Ruta: liseniq.api.leadership_dashboard.get_dashboard_data

>>> AJUSTAR (pendientes de confirmar) <<<
"""
import frappe
from frappe import _

from liseniq.api.leadership_dashboard_core import build_payload

# 1) Reporte (Script/Query Report) que devuelve la "sábana" 360 en formato largo
#    (una fila por evaluador x comportamiento). Confirmado.
REPORT_NAME = "Engagement Responses"

# 2) Nombre del filtro del reporte que recibe la medición/encuesta
REPORT_FILTER = "survey"

# 3) DocType de la medición (para validar que exista y sacar el nombre visible)
SURVEY_DOCTYPE = "Survey"
IQ_SURVEY_DOCTYPE = "qp_IQ_Survey"
SURVEY_TITLE_FIELD = None      # p. ej. "title"; None => se usa el name

# 4) Nombre del cliente que se imprime en el informe
#    (None => se toma del título de la medición)
CLIENTE = None

# 5) Columnas demográficas. None => autodetecta todas las columnas no estándar;
#    o una lista explícita, p. ej. ["Género", "Departamento/Área", "Nivel de Cargo"]
DEMOGRAPHIC_COLUMNS = None

# 6) ACCESO. False (recomendado): solo usuarios con sesión y permiso sobre el reporte.
#    True: cualquiera con el enlace y el nombre de la medición puede ver los resultados
#    (riesgo de privacidad: son datos de evaluación de personas).
ALLOW_GUEST = False


@frappe.whitelist(allow_guest=ALLOW_GUEST, methods=["GET"])
def get_dashboard_data(survey):
    if not survey or not frappe.db.exists(IQ_SURVEY_DOCTYPE, survey):
        frappe.throw(_("Medición no encontrada: {0}").format(survey), frappe.DoesNotExistError)

    from frappe.desk.query_report import run

    previous_user = frappe.session.user
    frappe.session.user = "Administrator"
    survey_title = frappe.db.get_value(IQ_SURVEY_DOCTYPE, survey, "su_name") or survey
    try:
        report = run(REPORT_NAME, filters={REPORT_FILTER: survey_title})
    except Exception as e:
        frappe.session.user = previous_user
        raise e
    finally:
        frappe.session.user = previous_user

    rows = report.get("result") or []
    columns = report.get("columns") or []
    # Los reportes pueden agregar una fila de totales (lista vacía o con 'Total'); build_payload
    # descarta lo que no tenga respuesta numérica y líder.

    title = survey
    if SURVEY_TITLE_FIELD:
        title = frappe.db.get_value(SURVEY_DOCTYPE, survey, SURVEY_TITLE_FIELD) or survey
    cliente = CLIENTE or title

    try:
        return build_payload(rows, columns, cliente, title, DEMOGRAPHIC_COLUMNS)
    except ValueError as e:
        frappe.throw(str(e), frappe.ValidationError)
