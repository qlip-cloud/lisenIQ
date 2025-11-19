import frappe
from frappe.utils import getdate, formatdate
from frappe import _
from liseniq.utils import power_bi_util
from typing import Optional

def get_context(context):

    if frappe.session.user == "Guest":
        frappe.throw(_("Cliente aún no ha sido registrado. Por favor comunique al Administrador."), frappe.PermissionError)

    context.no_cache = 1
    context.page_title = "Resultados"
    context.no_breadcrumbs = True
    context.is_navbar_custom = True

    # Datos iniciales (mediciones finalizadas + plantillas)
    items, templates = _get_finalized_surveys()
    context.finished_surveys_json = frappe.as_json(items)
    context.survey_templates_json = frappe.as_json(templates)
    context.power_bi_embed_json = None

    return context


def _get_status_name_finalizada() -> Optional[str]:
    """Obtiene el name del DocType qp_IQ_SurveyStatus cuyo se_status = 'Finalizada'."""
    return frappe.db.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")


def _build_base_sql(status_name: str) -> str:
    return """
SELECT
  s.name,
  s.su_name,
  s.su_status,
  s.su_template,
  t.tp_name,
  s.su_start_date,
  s.su_end_date
FROM `tabqp_IQ_Survey` s
LEFT JOIN `tabqp_IQ_Template` t ON t.name = s.su_template
LEFT JOIN `tabqp_IQ_SurveyStatus` st ON st.name = s.su_status
WHERE st.name = %s
"""


def _format_period_text(start, end) -> str:
    try:
        start_txt = formatdate(start) if start else ""
        end_txt = formatdate(end) if end else ""
        if start_txt and end_txt:
            return f"{start_txt} al {end_txt}"
        if start_txt:
            return f"{start_txt} sin fecha límite"
        return "-"
    except Exception:
        return "-"


def _get_finalized_surveys(name_filtro: Optional[str] = None,
                           template_filtro: Optional[str] = None,
                           limite: int = 100):
    status_name = _get_status_name_finalizada()
    if not status_name:
        return [], []

    sql = _build_base_sql(status_name)
    params = [status_name]

    if name_filtro:
        sql += " AND s.su_name LIKE %s"
        params.append(f"%{name_filtro}%")
    if template_filtro:
        sql += " AND t.tp_name LIKE %s"
        params.append(f"%{template_filtro}%")

    sql += " ORDER BY s.modified DESC LIMIT %s"
    params.append(limite)

    rows = frappe.db.sql(sql, params, as_dict=True)

    items = []
    templates = set()
    for r in rows:
        items.append({
            "docname": r.get("name"),
            "name": r.get("su_name") or r.get("name"),
            "template": r.get("tp_name") or "",
            "status": "Finalizada",
            "start_date": r.get("su_start_date"),
            "end_date": r.get("su_end_date"),
            "period": _format_period_text(r.get("su_start_date"), r.get("su_end_date")),
        })
        if r.get("tp_name"):
            templates.add(r.get("tp_name"))

    return items, sorted(list(templates))


@frappe.whitelist()
def get_finalized_surveys(name: Optional[str] = None, template: Optional[str] = None):
    items, templates = _get_finalized_surveys(name_filtro=name, template_filtro=template)
    return {"items": items, "templates": templates}

@frappe.whitelist()
def get_power_bi_embed_config(report_id: Optional[str] = None,
                              workspace_id: Optional[str] = None,
                              access_level: str = "View",
                              survey_docname: Optional[str] = None):
    
    if frappe.session.user == "Guest":
        frappe.throw(_("No autorizado"), frappe.PermissionError)
    try:
        # Paso 2: Obtener configuración (survey_docname reservado para lógica futura).
        cfg = power_bi_util.get_embed_config(report_id=report_id,
                                             workspace_id=workspace_id,
                                             access_level=access_level)
        if survey_docname:
            cfg["survey_docname"] = survey_docname
        return cfg
    except Exception as ex:
        frappe.log_error(f"get_power_bi_embed_config error: {ex}", "iq-results")
        frappe.throw(_("No fue posible obtener el token de Power BI."))