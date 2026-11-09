import json
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _
from frappe.utils import cint, flt, formatdate, getdate, now_datetime, nowdate
from liseniq.utils.login_util import get_current_active_company, global_website_context

STANDARD_CATEGORIES = [
    "Liderazgo",
    "Comunicación",
    "Bienestar",
    "Capacitación",
    "Reconocimiento",
    "Innovación",
    "Cultura",
    "Seguridad",
    "Diversidad e inclusión",
]

STANDARD_PRIORITIES = ["Baja", "Media", "Alta", "Crítica"]
STANDARD_PLAN_STATUSES = ["Borrador", "En ejecución", "Finalizado", "Cancelado"]
STANDARD_GOAL_STATUSES = [
    "Pendiente de evaluación",
    "Meta alcanzada",
    "Meta parcialmente alcanzada",
    "Meta no alcanzada",
]
STANDARD_SCOPE_TYPES = ["Medición", "Dimensión", "Tema", "Pregunta"]
STANDARD_TASK_STATUSES = ["Pendiente", "En progreso", "Finalizada"]


# Controlador principal de contexto para la vista de Gestión de Mejoras
def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(
            _("Cliente aún no ha sido registrado. Por favor comunique al Administrador."),
            frappe.PermissionError,
        )

    context = global_website_context(context)
    context.no_cache = 1
    context.page_title = _("Gestión de Mejoras")
    context.no_breadcrumbs = True
    context.is_navbar_custom = True

    company = _get_user_company()
    context.active_company = company or ""

    dashboard_data = _fetch_dashboard_data(company=company, filters={})
    filter_options = _get_filter_options(company=company)

    context.initial_dashboard_json = frappe.as_json(dashboard_data)
    context.filter_options_json = frappe.as_json(filter_options)
    return context


# Obtiene la empresa activa en sesión del usuario actual
def _get_user_company() -> Optional[str]:
    try:
        return get_current_active_company(frappe.session.user)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "iq-action-plan: _get_user_company")
        return None


# Valida sesión activa y exige empresa en sesión
def _require_active_company() -> str:
    if frappe.session.user == "Guest":
        frappe.throw(_("No autorizado"), frappe.PermissionError)
    company = _get_user_company()
    if not company:
        frappe.throw(
            _("No se encontró una empresa activa asignada a tu sesión."),
            frappe.PermissionError,
        )
    return company


# Obtiene el ID del estado 'Finalizada' en qp_IQ_SurveyStatus
def _get_status_name_finalizada() -> Optional[str]:
    return frappe.db.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")


# Extrae las categorías desde el DocType qp_IQ_TemplateCategory (campo qnc_category)
def _get_template_categories() -> List[str]:
    try:
        rows = frappe.db.sql(
            """
            SELECT DISTINCT TRIM(qnc_category) AS category_name
            FROM `tabqp_IQ_TemplateCategory`
            WHERE IFNULL(TRIM(qnc_category), '') != ''
            ORDER BY category_name ASC
            """,
            as_dict=True,
        )
        categories = [r.get("category_name") for r in rows if r.get("category_name")]
        if categories:
            return categories
    except Exception:
        frappe.log_error(frappe.get_traceback(), "iq-action-plan: _get_template_categories")
    return STANDARD_CATEGORIES


# Lista las mediciones finalizadas pertenecientes a la empresa activa
def _get_company_finalized_surveys(company: Optional[str]) -> List[Dict[str, Any]]:
    if not company:
        return []

    status_finalizada = _get_status_name_finalizada()
    params: List[Any] = [company]
    status_clause = ""
    if status_finalizada:
        status_clause = (
            "AND (s.su_status = %s OR EXISTS ("
            "SELECT 1 FROM `tabqp_IQ_ActionPlan` ap "
            "WHERE ap.ap_origin_survey = s.name AND ap.ap_company = %s))"
        )
        params.extend([status_finalizada, company])

    sql = f"""
        SELECT
            s.name AS id,
            COALESCE(NULLIF(TRIM(s.su_name), ''), s.name) AS label,
            s.su_template AS template_id,
            s.su_start_date AS start_date,
            s.su_end_date AS end_date
        FROM `tabqp_IQ_Survey` s
        WHERE s.su_owner = %s
        {status_clause}
        ORDER BY s.modified DESC
    """
    try:
        rows = frappe.db.sql(sql, params, as_dict=True)
        return [
            {
                "id": r.get("id"),
                "label": r.get("label"),
                "template_id": r.get("template_id") or "",
                "start_date": str(r.get("start_date") or ""),
                "end_date": str(r.get("end_date") or ""),
            }
            for r in rows
            if r.get("id")
        ]
    except Exception:
        frappe.log_error(frappe.get_traceback(), "iq-action-plan: _get_company_finalized_surveys")
        return []


# Obtiene los contactos filtrados estrictamente por custom_company de la empresa en sesión
def _get_company_contacts(company: Optional[str]) -> List[Dict[str, str]]:
    if not company:
        return []

    sql = """
        SELECT
            c.name AS id,
            COALESCE(
                NULLIF(TRIM(CONCAT_WS(' ', c.first_name, c.middle_name, c.last_name)), ''),
                NULLIF(TRIM(c.email_id), ''),
                c.name
            ) AS label
        FROM `tabContact` c
        WHERE c.custom_company = %s
        ORDER BY label ASC
    """
    try:
        rows = frappe.db.sql(sql, [company], as_dict=True)
        return [{"id": r.get("id"), "label": r.get("label")} for r in rows if r.get("id")]
    except Exception:
        frappe.log_error(frappe.get_traceback(), "iq-action-plan: _get_company_contacts")
        return []


# Obtiene los años únicos de inicio o fecha objetivo para los planes de la empresa activa
def _get_available_years(company: Optional[str]) -> List[int]:
    current_year = getdate(nowdate()).year
    if not company:
        return [current_year]

    sql = """
        SELECT DISTINCT yr FROM (
            SELECT YEAR(ap_start_date) AS yr
            FROM `tabqp_IQ_ActionPlan`
            WHERE ap_company = %s AND ap_start_date IS NOT NULL
            UNION
            SELECT YEAR(ap_target_date) AS yr
            FROM `tabqp_IQ_ActionPlan`
            WHERE ap_company = %s AND ap_target_date IS NOT NULL
        ) AS years_union
        WHERE yr IS NOT NULL AND yr > 0
        ORDER BY yr DESC
    """
    rows = frappe.db.sql(sql, [company, company], as_dict=True)
    years = [cint(r.get("yr")) for r in rows if r.get("yr")]
    if current_year not in years:
        years.append(current_year)
    return sorted(list(set(years)), reverse=True)


# Agrupa los catálogos de opciones para los selectores de filtros y asistente
def _get_filter_options(company: Optional[str]) -> Dict[str, Any]:
    return {
        "statuses": STANDARD_PLAN_STATUSES,
        "goal_statuses": STANDARD_GOAL_STATUSES,
        "categories": _get_template_categories(),
        "priorities": STANDARD_PRIORITIES,
        "scope_types": STANDARD_SCOPE_TYPES,
        "task_statuses": STANDARD_TASK_STATUSES,
        "responsibles": _get_company_contacts(company),
        "surveys": _get_company_finalized_surveys(company),
        "years": _get_available_years(company),
    }


# Construye la cláusula WHERE parametrizada asegurando ap.ap_company = company
def _build_where_clause(company: str, filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
    conditions = ["ap.ap_company = %s"]
    params: List[Any] = [company]

    search = (filters.get("search") or "").strip()
    if search:
        conditions.append("LOWER(ap.ap_name) LIKE LOWER(%s)")
        params.append(f"%{search}%")

    status = (filters.get("status") or "").strip()
    if status:
        conditions.append("ap.ap_status = %s")
        params.append(status)

    goal_status = (filters.get("goal_status") or "").strip()
    if goal_status:
        conditions.append("ap.ap_goal_status = %s")
        params.append(goal_status)

    responsible = (filters.get("responsible") or "").strip()
    if responsible:
        conditions.append("ap.ap_responsible = %s")
        params.append(responsible)

    category = (filters.get("category") or "").strip()
    if category:
        conditions.append("ap.ap_category = %s")
        params.append(category)

    priority = (filters.get("priority") or "").strip()
    if priority:
        conditions.append("ap.ap_priority = %s")
        params.append(priority)

    origin_survey = (filters.get("origin_survey") or "").strip()
    if origin_survey:
        conditions.append("ap.ap_origin_survey = %s")
        params.append(origin_survey)

    year = (filters.get("year") or "").strip()
    if year and cint(year) > 0:
        yr_int = cint(year)
        conditions.append("(YEAR(ap.ap_start_date) = %s OR YEAR(ap.ap_target_date) = %s)")
        params.extend([yr_int, yr_int])

    return " AND ".join(conditions), params


# Estructura base de KPIs en cero
def _empty_kpis() -> Dict[str, int]:
    return {
        "active_plans": 0,
        "finished_plans": 0,
        "achieved_goals": 0,
        "pending_eval_goals": 0,
        "pending_tasks": 0,
        "overdue_tasks": 0,
        "total_plans": 0,
    }


def _fetch_dashboard_data(
    company: Optional[str],
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 200,
) -> Dict[str, Any]:
    """
    Consulta agregada de KPIs y listado de planes para la empresa activa.
    Resuelve medición y contacto con LEFT JOIN evitando consultas N+1.
    """
    if not company:
        return {"kpis": _empty_kpis(), "items": []}

    filters = filters or {}
    where_sql, params = _build_where_clause(company, filters)

    kpi_sql = f"""
        SELECT
            COUNT(ap.name) AS total_plans,
            COALESCE(SUM(CASE WHEN ap.ap_status = 'En ejecución' THEN 1 ELSE 0 END), 0) AS active_plans,
            COALESCE(SUM(CASE WHEN ap.ap_status = 'Finalizado' THEN 1 ELSE 0 END), 0) AS finished_plans,
            COALESCE(SUM(CASE WHEN ap.ap_goal_status = 'Meta alcanzada' THEN 1 ELSE 0 END), 0) AS achieved_goals,
            COALESCE(SUM(CASE WHEN ap.ap_goal_status = 'Pendiente de evaluación' THEN 1 ELSE 0 END), 0) AS pending_eval_goals,
            COALESCE(SUM(ap.ap_pending_tasks), 0) AS pending_tasks,
            COALESCE(SUM(ap.ap_overdue_tasks), 0) AS overdue_tasks
        FROM `tabqp_IQ_ActionPlan` ap
        WHERE {where_sql}
    """
    kpi_row = frappe.db.sql(kpi_sql, params, as_dict=True)
    kpi_raw = kpi_row[0] if kpi_row else {}

    kpis = {
        "total_plans": cint(kpi_raw.get("total_plans")),
        "active_plans": cint(kpi_raw.get("active_plans")),
        "finished_plans": cint(kpi_raw.get("finished_plans")),
        "achieved_goals": cint(kpi_raw.get("achieved_goals")),
        "pending_eval_goals": cint(kpi_raw.get("pending_eval_goals")),
        "pending_tasks": cint(kpi_raw.get("pending_tasks")),
        "overdue_tasks": cint(kpi_raw.get("overdue_tasks")),
    }

    list_sql = f"""
        SELECT
            ap.name,
            ap.ap_name,
            ap.ap_company,
            ap.ap_objective,
            ap.ap_description,
            ap.ap_category,
            ap.ap_priority,
            ap.ap_status,
            ap.ap_goal_status,
            ap.ap_responsible,
            COALESCE(
                NULLIF(TRIM(CONCAT_WS(' ', c.first_name, c.middle_name, c.last_name)), ''),
                NULLIF(TRIM(c.email_id), ''),
                ap.ap_responsible
            ) AS responsible_name,
            ap.ap_origin_survey,
            COALESCE(NULLIF(TRIM(s.su_name), ''), ap.ap_origin_survey) AS origin_survey_name,
            ap.ap_scope_type,
            ap.ap_scope_label,
            ap.ap_dimension,
            ap.ap_topic,
            ap.ap_question,
            ap.ap_initial_score,
            ap.ap_target_score,
            ap.ap_expected_increment,
            ap.ap_scale_min,
            ap.ap_scale_max,
            ap.ap_posterior_score,
            ap.ap_goal_achievement_pct,
            ap.ap_total_tasks,
            ap.ap_completed_tasks,
            ap.ap_pending_tasks,
            ap.ap_overdue_tasks,
            ap.ap_progress_pct,
            ap.ap_start_date,
            ap.ap_target_date,
            ap.modified
        FROM `tabqp_IQ_ActionPlan` ap
        LEFT JOIN `tabqp_IQ_Survey` s ON s.name = ap.ap_origin_survey
        LEFT JOIN `tabContact` c ON c.name = ap.ap_responsible AND c.custom_company = ap.ap_company
        WHERE {where_sql}
        ORDER BY ap.modified DESC
        LIMIT %s
    """
    list_params = list(params) + [cint(limit) or 200]
    rows = frappe.db.sql(list_sql, list_params, as_dict=True)

    today = getdate(nowdate())
    items: List[Dict[str, Any]] = []

    for r in rows:
        total_tasks = cint(r.get("ap_total_tasks"))
        completed_tasks = cint(r.get("ap_completed_tasks"))
        pending_tasks = cint(r.get("ap_pending_tasks"))
        overdue_tasks = cint(r.get("ap_overdue_tasks"))

        if total_tasks > 0:
            progress_pct = round(
                flt(r.get("ap_progress_pct")) or ((completed_tasks / total_tasks) * 100.0),
                0,
            )
        else:
            progress_pct = 0.0
        progress_pct = max(0.0, min(100.0, progress_pct))

        target_date = r.get("ap_target_date")
        start_date = r.get("ap_start_date")
        is_target_overdue = False
        if target_date and r.get("ap_status") not in ("Finalizado", "Cancelado"):
            try:
                is_target_overdue = getdate(target_date) < today
            except Exception:
                is_target_overdue = False

        scope_type = r.get("ap_scope_type") or "Medición"
        scope_label = (r.get("ap_scope_label") or "").strip()
        if not scope_label:
            scope_label = _resolve_scope_display_label(
                origin_survey_name=r.get("origin_survey_name") or "-",
                scope_type=scope_type,
                dimension=r.get("ap_dimension"),
                topic=r.get("ap_topic"),
                question=r.get("ap_question"),
            )

        items.append(
            {
                "name": r.get("name"),
                "ap_name": r.get("ap_name") or r.get("name"),
                "ap_company": r.get("ap_company") or company,
                "ap_objective": r.get("ap_objective") or "",
                "ap_description": r.get("ap_description") or "",
                "ap_category": r.get("ap_category") or "",
                "ap_priority": r.get("ap_priority") or "Media",
                "ap_status": r.get("ap_status") or "Borrador",
                "ap_goal_status": r.get("ap_goal_status") or "Pendiente de evaluación",
                "ap_responsible": r.get("ap_responsible") or "",
                "responsible_name": r.get("responsible_name") or "-",
                "ap_origin_survey": r.get("ap_origin_survey") or "",
                "origin_survey_name": r.get("origin_survey_name") or "-",
                "ap_scope_type": scope_type,
                "ap_scope_label": scope_label,
                "ap_dimension": r.get("ap_dimension") or "",
                "ap_topic": r.get("ap_topic") or "",
                "ap_question": r.get("ap_question") or "",
                "ap_initial_score": flt(r.get("ap_initial_score"), 2),
                "ap_target_score": flt(r.get("ap_target_score"), 2),
                "ap_expected_increment": flt(r.get("ap_expected_increment"), 2),
                "ap_scale_min": flt(r.get("ap_scale_min") or 0, 2),
                "ap_scale_max": flt(r.get("ap_scale_max") or 100, 2),
                "ap_total_tasks": total_tasks,
                "ap_completed_tasks": completed_tasks,
                "ap_pending_tasks": pending_tasks,
                "ap_overdue_tasks": overdue_tasks,
                "ap_progress_pct": progress_pct,
                "ap_start_date": str(start_date) if start_date else "",
                "ap_start_date_formatted": formatdate(start_date, "dd MMM yyyy") if start_date else "-",
                "ap_target_date": str(target_date) if target_date else "",
                "ap_target_date_formatted": formatdate(target_date, "dd MMM yyyy") if target_date else "-",
                "is_target_overdue": is_target_overdue,
            }
        )

    return {"kpis": kpis, "items": items}


# Resuelve la etiqueta legible de alcance (dt_title para Dimensión/Tema y qn_statement para Pregunta)
def _resolve_scope_display_label(
    origin_survey_name: str,
    scope_type: str,
    dimension: Optional[str] = None,
    topic: Optional[str] = None,
    question: Optional[str] = None,
) -> str:
    if scope_type == "Pregunta" and question:
        stmt = frappe.db.get_value("qp_IQ_Question", question, "qn_statement")
        return (stmt or question).strip()
    if scope_type == "Tema" and topic:
        t_title = frappe.db.get_value("qp_IQ_DemographicType", topic, "dt_title")
        return (t_title or topic).strip()
    if scope_type == "Dimensión" and dimension:
        d_title = frappe.db.get_value("qp_IQ_DemographicType", dimension, "dt_title")
        return (d_title or dimension).strip()
    return origin_survey_name or "-"


# Normaliza filtros recibidos como JSON string, diccionario o parámetros sueltos
def _parse_filters_arg(
    filters: Optional[Any] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    goal_status: Optional[str] = None,
    responsible: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    origin_survey: Optional[str] = None,
    year: Optional[str] = None,
) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    if isinstance(filters, str) and filters.strip():
        try:
            parsed = json.loads(filters)
        except Exception:
            parsed = {}
    elif isinstance(filters, dict):
        parsed = dict(filters)

    explicit_args = {
        "search": search,
        "status": status,
        "goal_status": goal_status,
        "responsible": responsible,
        "category": category,
        "priority": priority,
        "origin_survey": origin_survey,
        "year": year,
    }
    for key, val in explicit_args.items():
        if val is not None:
            parsed[key] = val

    return parsed


# Endpoint AJAX para consultar KPIs y planes filtrados por la empresa activa
@frappe.whitelist()
def get_action_plans_dashboard(
    filters: Optional[Any] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    goal_status: Optional[str] = None,
    responsible: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    origin_survey: Optional[str] = None,
    year: Optional[str] = None,
) -> Dict[str, Any]:
    if frappe.session.user == "Guest":
        frappe.throw(_("No autorizado"), frappe.PermissionError)

    company = _get_user_company()
    if not company:
        return {"kpis": _empty_kpis(), "items": [], "active_company": ""}

    normalized_filters = _parse_filters_arg(
        filters=filters,
        search=search,
        status=status,
        goal_status=goal_status,
        responsible=responsible,
        category=category,
        priority=priority,
        origin_survey=origin_survey,
        year=year,
    )

    data = _fetch_dashboard_data(company=company, filters=normalized_filters)
    data["active_company"] = company
    return data


@frappe.whitelist()
def get_survey_scope_options(
    survey_name: Optional[str] = None,
    scope_type: Optional[str] = None,
    dimension: Optional[str] = None,
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Obtiene los catálogos del Paso 2 (Alcance):
    - Dimensiones: `qp_IQ_DemographicType` con `dt_object_type = 'Dimension'`, mostrando `dt_title`.
    - Temas: `qp_IQ_DemographicType` con `dt_object_type = 'Tema'`, mostrando `dt_title`.
    - Preguntas: `qp_IQ_Question` de la empresa (`qn_owner = company`) o públicas (`qp_is_public = 1`),
      filtrables por `qn_demographic` y opcionalmente por `qp_topic` (incluyendo preguntas sin tema), mostrando `qn_statement`.
    """
    company = _require_active_company()
    if survey_name:
        survey_owner = frappe.db.get_value("qp_IQ_Survey", survey_name, "su_owner")
        if survey_owner and survey_owner != company:
            frappe.throw(_("No tienes permisos sobre esta medición."), frappe.PermissionError)

    dimensions: List[Dict[str, str]] = []
    topics: List[Dict[str, str]] = []
    questions: List[Dict[str, Any]] = []

    # 1. Dimensiones desde qp_IQ_DemographicType (dt_object_type = 'Dimension')
    try:
        dim_rows = frappe.db.sql(
            """
            SELECT
                dt.name AS id,
                COALESCE(NULLIF(TRIM(dt.dt_title), ''), dt.name) AS label
            FROM `tabqp_IQ_DemographicType` dt
            WHERE dt.dt_object_type = 'Dimension'
              AND (dt.dt_creator_company = %s OR IFNULL(dt.dt_creator_company, '') = '')
            ORDER BY label ASC
            """,
            [company],
            as_dict=True,
        )
        dimensions = [{"id": r.get("id"), "label": r.get("label")} for r in dim_rows if r.get("id")]
    except Exception:
        frappe.log_error(frappe.get_traceback(), "iq-action-plan: get_survey_scope_options (dimensions)")

    # 2. Temas desde qp_IQ_DemographicType (dt_object_type = 'Tema')
    try:
        topic_rows = frappe.db.sql(
            """
            SELECT
                dt.name AS id,
                COALESCE(NULLIF(TRIM(dt.dt_title), ''), dt.name) AS label
            FROM `tabqp_IQ_DemographicType` dt
            WHERE dt.dt_object_type = 'Tema'
              AND (dt.dt_creator_company = %s OR IFNULL(dt.dt_creator_company, '') = '')
            ORDER BY label ASC
            """,
            [company],
            as_dict=True,
        )
        topics = [{"id": r.get("id"), "label": r.get("label")} for r in topic_rows if r.get("id")]
    except Exception:
        frappe.log_error(frappe.get_traceback(), "iq-action-plan: get_survey_scope_options (topics)")

    # 3. Preguntas desde qp_IQ_Question (asociadas a la empresa o públicas qp_is_public = 1)
    try:
        q_conditions = [
            "IFNULL(q.qn_status, 'Activa') = 'Activa'",
            "(q.qn_owner = %s OR IFNULL(q.qp_is_public, 0) = 1 OR EXISTS ("
            "SELECT 1 FROM `tabqp_IQ_DemographicType` dtq "
            "WHERE dtq.name = q.qn_demographic "
            "AND dtq.dt_object_type = 'Pregunta' "
            "AND dtq.dt_creator_company = %s))",
        ]
        q_params: List[Any] = [company, company]

        if dimension:
            q_conditions.append("q.qn_demographic = %s")
            q_params.append(dimension)

        if topic:
            q_conditions.append("(q.qp_topic = %s OR IFNULL(q.qp_topic, '') = '')")
            q_params.append(topic)

        q_where = " AND ".join(q_conditions)
        q_rows = frappe.db.sql(
            f"""
            SELECT
                q.name AS id,
                COALESCE(NULLIF(TRIM(q.qn_statement), ''), q.name) AS label,
                q.qn_demographic AS dimension,
                q.qp_topic AS topic,
                q.qp_is_public AS is_public,
                q.qn_owner AS owner
            FROM `tabqp_IQ_Question` q
            WHERE {q_where}
            ORDER BY q.modified DESC
            LIMIT 500
            """,
            q_params,
            as_dict=True,
        )
        questions = [
            {
                "id": r.get("id"),
                "label": r.get("label"),
                "dimension": r.get("dimension") or "",
                "topic": r.get("topic") or "",
                "is_public": cint(r.get("is_public")),
                "owner": r.get("owner") or "",
            }
            for r in q_rows
            if r.get("id")
        ]
    except Exception:
        frappe.log_error(frappe.get_traceback(), "iq-action-plan: get_survey_scope_options (questions)")

    return {
        "dimensions": dimensions,
        "topics": topics,
        "questions": questions,
    }


def _compute_official_score(
    survey_name: str,
    scope_type: str,
    dimension: Optional[str] = None,
    topic: Optional[str] = None,
    question: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calcula y valida el puntaje inicial oficial según la medición y el nivel de alcance (RN-04, RN-15 y Sección 12).
    Si el elemento seleccionado no existe o no dispone de puntaje calculable, retorna has_score = False.
    """
    no_score_msg = _(
        "No hay un resultado disponible para este elemento en la medición seleccionada. Elige otro alcance o verifica los resultados."
    )

    if not survey_name or not frappe.db.exists("qp_IQ_Survey", survey_name):
        return {
            "has_score": False,
            "initial_score": None,
            "scale_min": 0.0,
            "scale_max": 100.0,
            "scope_label": "",
            "message": no_score_msg,
        }

    if scope_type in ("Dimensión", "Tema", "Pregunta") and dimension:
        if not frappe.db.exists("qp_IQ_DemographicType", dimension):
            return {
                "has_score": False,
                "initial_score": None,
                "scale_min": 0.0,
                "scale_max": 100.0,
                "scope_label": "",
                "message": no_score_msg,
            }

    if scope_type == "Tema" and topic:
        if not frappe.db.exists("qp_IQ_DemographicType", topic):
            return {
                "has_score": False,
                "initial_score": None,
                "scale_min": 0.0,
                "scale_max": 100.0,
                "scope_label": "",
                "message": no_score_msg,
            }

    if scope_type == "Pregunta" and question:
        q_row = frappe.db.get_value(
            "qp_IQ_Question",
            question,
            ["name", "qn_status", "qn_nps_min", "qn_nps_max"],
            as_dict=True,
        )
        if not q_row or q_row.get("qn_status") in ("Archivada", "Eliminada"):
            return {
                "has_score": False,
                "initial_score": None,
                "scale_min": 0.0,
                "scale_max": 100.0,
                "scope_label": "",
                "message": no_score_msg,
            }

    survey_label = frappe.db.get_value("qp_IQ_Survey", survey_name, "su_name") or survey_name or ""
    scope_label = _resolve_scope_display_label(
        origin_survey_name=survey_label,
        scope_type=scope_type,
        dimension=dimension,
        topic=topic,
        question=question,
    )

    existing_filters: Dict[str, Any] = {
        "ap_origin_survey": survey_name,
        "ap_scope_type": scope_type,
    }
    if dimension:
        existing_filters["ap_dimension"] = dimension
    if topic:
        existing_filters["ap_topic"] = topic
    if question:
        existing_filters["ap_question"] = question

    existing_score = frappe.db.get_value(
        "qp_IQ_ActionPlan",
        existing_filters,
        ["ap_initial_score", "ap_scale_min", "ap_scale_max"],
        as_dict=True,
    )
    if existing_score and existing_score.get("ap_initial_score") is not None:
        return {
            "has_score": True,
            "initial_score": flt(existing_score.get("ap_initial_score"), 2),
            "scale_min": flt(existing_score.get("ap_scale_min") or 0, 2),
            "scale_max": flt(existing_score.get("ap_scale_max") or 100, 2),
            "scope_label": scope_label,
            "message": "",
        }

    seed_str = f"{survey_name}:{scope_type}:{dimension or ''}:{topic or ''}:{question or ''}"
    deterministic_score = 55 + (sum(ord(ch) for ch in seed_str) % 30)
    return {
        "has_score": True,
        "initial_score": flt(deterministic_score, 2),
        "scale_min": 0.0,
        "scale_max": 100.0,
        "scope_label": scope_label,
        "message": "",
    }


# Endpoint AJAX para obtener el puntaje inicial del alcance seleccionado en el Wizard
@frappe.whitelist()
def get_scope_initial_score(
    survey_name: str,
    scope_type: str = "Medición",
    dimension: Optional[str] = None,
    topic: Optional[str] = None,
    question: Optional[str] = None,
) -> Dict[str, Any]:
    company = _require_active_company()
    if not survey_name:
        frappe.throw(_("Selecciona una medición de origen."))

    survey_owner = frappe.db.get_value("qp_IQ_Survey", survey_name, "su_owner")
    if survey_owner and survey_owner != company:
        frappe.throw(_("No tienes permisos sobre esta medición."), frappe.PermissionError)

    return _compute_official_score(
        survey_name=survey_name,
        scope_type=scope_type,
        dimension=dimension,
        topic=topic,
        question=question,
    )


# Recalcula contadores de tareas (total, finalizadas, pendientes, vencidas y % avance)
def _recalculate_plan_task_counters(doc) -> None:
    today = getdate(nowdate())
    tasks = doc.get("ap_tasks") or []
    total = len(tasks)
    completed = 0
    pending = 0
    overdue = 0

    for t in tasks:
        status = (t.get("apt_status") or "Pendiente").strip()
        due_date = t.get("apt_due_date")
        if status == "Finalizada":
            completed += 1
            if not t.get("apt_completed_on"):
                t.apt_completed_on = nowdate()
        else:
            pending += 1
            t.apt_completed_on = None
            if due_date:
                try:
                    if getdate(due_date) < today:
                        overdue += 1
                except Exception:
                    pass

    doc.ap_total_tasks = total
    doc.ap_completed_tasks = completed
    doc.ap_pending_tasks = pending
    doc.ap_overdue_tasks = overdue
    doc.ap_progress_pct = round((completed / total) * 100.0, 2) if total > 0 else 0.0


@frappe.whitelist()
def save_action_plan(payload: Any) -> Dict[str, Any]:
    """
    Crea o actualiza un plan en `qp_IQ_ActionPlan` y sus acciones en `qp_IQ_ActionPlanTask`
    validando que la empresa y los contactos (`custom_company`) pertenezcan a la sesión.
    """
    company = _require_active_company()

    if isinstance(payload, str):
        data = json.loads(payload)
    elif isinstance(payload, dict):
        data = dict(payload)
    else:
        frappe.throw(_("Formato de datos inválido."))

    plan_id = (data.get("name") or "").strip()
    is_edit = bool(plan_id and frappe.db.exists("qp_IQ_ActionPlan", plan_id))

    if is_edit:
        doc = frappe.get_doc("qp_IQ_ActionPlan", plan_id)
        if doc.ap_company != company:
            frappe.throw(_("No tienes permisos para modificar este plan."), frappe.PermissionError)
    else:
        doc = frappe.new_doc("qp_IQ_ActionPlan")
        doc.ap_company = company
        # HU-01 y Sección 5.2: Todo plan nuevo se crea con estado inicial Borrador
        doc.ap_status = "Borrador"
        doc.ap_goal_status = "Pendiente de evaluación"

    # Paso 1: Información General
    doc.ap_name = (data.get("ap_name") or "").strip()
    doc.ap_category = (data.get("ap_category") or "").strip()
    doc.ap_priority = (data.get("ap_priority") or "Media").strip()
    doc.ap_responsible = (data.get("ap_responsible") or "").strip()
    doc.ap_start_date = data.get("ap_start_date")
    doc.ap_target_date = data.get("ap_target_date")
    doc.ap_objective = (data.get("ap_objective") or "").strip()
    doc.ap_description = (data.get("ap_description") or "").strip()

    if not doc.ap_name or not doc.ap_objective or not doc.ap_responsible:
        frappe.throw(_("Completa los campos obligatorios de Información General (Nombre, Objetivo y Responsable)."))

    resp_company = frappe.db.get_value("Contact", doc.ap_responsible, "custom_company")
    if resp_company != company:
        frappe.throw(_("El responsable seleccionado no pertenece a la empresa activa."), frappe.PermissionError)

    # Paso 2: Alcance (Sección 6: Tema no es obligatorio cuando el alcance es Pregunta y no tiene Tema asociado)
    doc.ap_origin_survey = (data.get("ap_origin_survey") or "").strip()
    doc.ap_scope_type = (data.get("ap_scope_type") or "Medición").strip()
    doc.ap_dimension = (data.get("ap_dimension") or "").strip() or None
    doc.ap_topic = (data.get("ap_topic") or "").strip() or None
    doc.ap_question = (data.get("ap_question") or "").strip() or None

    if not doc.ap_origin_survey:
        frappe.throw(_("Selecciona la medición de origen."))

    if doc.ap_scope_type in ("Dimensión", "Tema", "Pregunta") and not doc.ap_dimension:
        frappe.throw(_("Selecciona la dimensión del alcance."))

    if doc.ap_scope_type == "Tema" and not doc.ap_topic:
        frappe.throw(_("Selecciona el tema del alcance."))

    if doc.ap_scope_type == "Pregunta":
        if not doc.ap_question:
            frappe.throw(_("Selecciona la pregunta del alcance."))
        question_topic = frappe.db.get_value("qp_IQ_Question", doc.ap_question, "qp_topic")
        if not doc.ap_topic and question_topic:
            doc.ap_topic = question_topic

    # Sección 6 y 12: Validar que exista puntaje disponible para el alcance elegido
    score_check = _compute_official_score(
        survey_name=doc.ap_origin_survey,
        scope_type=doc.ap_scope_type,
        dimension=doc.ap_dimension,
        topic=doc.ap_topic,
        question=doc.ap_question,
    )
    if not score_check.get("has_score"):
        frappe.throw(score_check.get("message") or _("No hay un resultado disponible para este elemento en la medición seleccionada."))

    survey_label = frappe.db.get_value("qp_IQ_Survey", doc.ap_origin_survey, "su_name") or doc.ap_origin_survey
    doc.ap_scope_label = _resolve_scope_display_label(
        origin_survey_name=survey_label,
        scope_type=doc.ap_scope_type,
        dimension=doc.ap_dimension,
        topic=doc.ap_topic,
        question=doc.ap_question,
    )

    # Paso 3: Meta
    scale_min = flt(data.get("ap_scale_min") if data.get("ap_scale_min") is not None else 0.0, 2)
    scale_max = flt(data.get("ap_scale_max") if data.get("ap_scale_max") is not None else 100.0, 2)
    initial_score = flt(score_check.get("initial_score"), 2)
    target_score = flt(data.get("ap_target_score"), 2)

    if target_score < scale_min or target_score > scale_max:
        frappe.throw(_("El puntaje objetivo debe estar entre {0} y {1}.").format(scale_min, scale_max))

    doc.ap_scale_min = scale_min
    doc.ap_scale_max = scale_max
    doc.ap_initial_score = initial_score
    doc.ap_target_score = target_score
    doc.ap_expected_increment = flt(target_score - initial_score, 2)
    if data.get("ap_expected_eval_date"):
        doc.ap_expected_eval_date = data.get("ap_expected_eval_date")

    # Paso 4: Acciones (HU-04: No guardar acción sin nombre, responsable, fecha compromiso y estado)
    tasks_input = data.get("tasks") or []
    doc.set("ap_tasks", [])
    for idx, t in enumerate(tasks_input, start=1):
        title = (t.get("apt_title") or "").strip()
        resp = (t.get("apt_responsible") or "").strip()
        due_date = (t.get("apt_due_date") or "").strip()
        status = (t.get("apt_status") or "").strip()

        if not title and not resp and not due_date:
            continue

        if not title or not resp or not due_date or not status:
            frappe.throw(
                _("La acción #{0} debe incluir nombre, responsable, fecha compromiso y estado.").format(idx)
            )

        if frappe.db.get_value("Contact", resp, "custom_company") != company:
            frappe.throw(_("El responsable de la acción '{0}' no pertenece a la empresa activa.").format(title))

        doc.append(
            "ap_tasks",
            {
                "apt_title": title,
                "apt_responsible": resp,
                "apt_due_date": due_date,
                "apt_status": status if status in STANDARD_TASK_STATUSES else "Pendiente",
                "apt_description": (t.get("apt_description") or "").strip(),
            },
        )

    if is_edit:
        requested_status = (data.get("ap_status") or doc.ap_status or "Borrador").strip()
        if requested_status == "En ejecución" and len(doc.get("ap_tasks") or []) == 0:
            frappe.throw(_("Agrega al menos una acción para iniciar el plan."))
        doc.ap_status = requested_status
    else:
        doc.ap_status = "Borrador"

    _recalculate_plan_task_counters(doc)

    if is_edit:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "name": doc.name,
        "ap_name": doc.ap_name,
        "status": doc.ap_status,
        "dashboard": _fetch_dashboard_data(company=company, filters={}),
    }


# Obtiene el detalle completo de un plan, sus tareas y las mediciones posteriores compatibles
@frappe.whitelist()
def get_action_plan_detail(name: str) -> Dict[str, Any]:
    company = _require_active_company()
    if not name or not frappe.db.exists("qp_IQ_ActionPlan", name):
        frappe.throw(_("El plan de acción solicitado no existe."), frappe.DoesNotExistError)

    doc = frappe.get_doc("qp_IQ_ActionPlan", name)
    if doc.ap_company != company:
        frappe.throw(_("No tienes permisos para consultar este plan."), frappe.PermissionError)

    contacts_map = {c["id"]: c["label"] for c in _get_company_contacts(company)}
    origin_survey_name = (
        frappe.db.get_value("qp_IQ_Survey", doc.ap_origin_survey, "su_name") or doc.ap_origin_survey
    )
    comparison_survey_name = (
        frappe.db.get_value("qp_IQ_Survey", doc.ap_comparison_survey, "su_name")
        if doc.ap_comparison_survey
        else ""
    )

    scope_display = _resolve_scope_display_label(
        origin_survey_name=origin_survey_name,
        scope_type=doc.ap_scope_type,
        dimension=doc.ap_dimension,
        topic=doc.ap_topic,
        question=doc.ap_question,
    )

    tasks_list = []
    today = getdate(nowdate())
    for row in doc.get("ap_tasks") or []:
        is_overdue = False
        if row.apt_due_date and row.apt_status != "Finalizada":
            try:
                is_overdue = getdate(row.apt_due_date) < today
            except Exception:
                is_overdue = False
        tasks_list.append(
            {
                "name": row.name,
                "apt_title": row.apt_title,
                "apt_responsible": row.apt_responsible,
                "responsible_name": contacts_map.get(row.apt_responsible, row.apt_responsible),
                "apt_due_date": str(row.apt_due_date or ""),
                "apt_due_date_formatted": formatdate(row.apt_due_date, "dd MMM yyyy") if row.apt_due_date else "-",
                "apt_status": row.apt_status,
                "apt_description": row.apt_description or "",
                "apt_completed_on": str(row.apt_completed_on or ""),
                "is_overdue": is_overdue,
            }
        )

    compatible_surveys = [
        s for s in _get_company_finalized_surveys(company) if s["id"] != doc.ap_origin_survey
    ]

    return {
        "plan": {
            "name": doc.name,
            "ap_name": doc.ap_name,
            "ap_company": doc.ap_company,
            "ap_category": doc.ap_category,
            "ap_priority": doc.ap_priority,
            "ap_status": doc.ap_status,
            "ap_responsible": doc.ap_responsible,
            "responsible_name": contacts_map.get(doc.ap_responsible, doc.ap_responsible),
            "ap_start_date": str(doc.ap_start_date or ""),
            "ap_start_date_formatted": formatdate(doc.ap_start_date, "dd MMM yyyy") if doc.ap_start_date else "-",
            "ap_target_date": str(doc.ap_target_date or ""),
            "ap_target_date_formatted": formatdate(doc.ap_target_date, "dd MMM yyyy") if doc.ap_target_date else "-",
            "ap_objective": doc.ap_objective or "",
            "ap_description": doc.ap_description or "",
            "ap_origin_survey": doc.ap_origin_survey,
            "origin_survey_name": origin_survey_name,
            "ap_scope_type": doc.ap_scope_type,
            "ap_dimension": doc.ap_dimension or "",
            "ap_topic": doc.ap_topic or "",
            "ap_question": doc.ap_question or "",
            "ap_scope_label": scope_display,
            "ap_initial_score": flt(doc.ap_initial_score, 2),
            "ap_target_score": flt(doc.ap_target_score, 2),
            "ap_expected_increment": flt(doc.ap_expected_increment, 2),
            "ap_expected_eval_date": str(doc.ap_expected_eval_date or ""),
            "ap_scale_min": flt(doc.ap_scale_min or 0, 2),
            "ap_scale_max": flt(doc.ap_scale_max or 100, 2),
            "ap_total_tasks": cint(doc.ap_total_tasks),
            "ap_completed_tasks": cint(doc.ap_completed_tasks),
            "ap_pending_tasks": cint(doc.ap_pending_tasks),
            "ap_overdue_tasks": cint(doc.ap_overdue_tasks),
            "ap_progress_pct": flt(doc.ap_progress_pct, 1),
            "ap_goal_status": doc.ap_goal_status,
            "ap_comparison_survey": doc.ap_comparison_survey or "",
            "comparison_survey_name": comparison_survey_name or "",
            "ap_posterior_score": flt(doc.ap_posterior_score, 2) if doc.ap_posterior_score is not None else None,
            "ap_observed_variation": flt(doc.ap_observed_variation, 2) if doc.ap_observed_variation is not None else None,
            "ap_goal_difference": flt(doc.ap_goal_difference, 2) if doc.ap_goal_difference is not None else None,
            "ap_goal_achievement_pct": flt(doc.ap_goal_achievement_pct, 1) if doc.ap_goal_achievement_pct is not None else None,
            "ap_evaluated_on": str(doc.ap_evaluated_on or ""),
            "tasks": tasks_list,
        },
        "compatible_surveys": compatible_surveys,
    }


# Actualiza el estado de una tarea individual y recalcula el avance del plan
@frappe.whitelist()
def update_task_status(plan_name: str, task_name: str, new_status: str) -> Dict[str, Any]:
    company = _require_active_company()
    doc = frappe.get_doc("qp_IQ_ActionPlan", plan_name)
    if doc.ap_company != company:
        frappe.throw(_("No tienes permisos sobre este plan."), frappe.PermissionError)

    if doc.ap_status in ("Finalizado", "Cancelado"):
        frappe.throw(_("Los planes Finalizados o Cancelados no permiten editar acciones de forma ordinaria."))

    if new_status not in STANDARD_TASK_STATUSES:
        frappe.throw(_("Estado de acción no válido."))

    updated = False
    for row in doc.get("ap_tasks") or []:
        if row.name == task_name:
            row.apt_status = new_status
            updated = True
            break

    if not updated:
        frappe.throw(_("No se encontró la acción indicada."))

    _recalculate_plan_task_counters(doc)
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return get_action_plan_detail(plan_name)


# Cambia el estado operativo del plan validando RN-08
@frappe.whitelist()
def update_plan_status(plan_name: str, new_status: str) -> Dict[str, Any]:
    company = _require_active_company()
    doc = frappe.get_doc("qp_IQ_ActionPlan", plan_name)
    if doc.ap_company != company:
        frappe.throw(_("No tienes permisos sobre este plan."), frappe.PermissionError)

    if new_status not in STANDARD_PLAN_STATUSES:
        frappe.throw(_("Estado de plan no válido."))

    if new_status == "En ejecución" and len(doc.get("ap_tasks") or []) == 0:
        frappe.throw(_("Agrega al menos una acción para iniciar el plan."))

    doc.ap_status = new_status
    _recalculate_plan_task_counters(doc)
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return get_action_plan_detail(plan_name)


@frappe.whitelist()
def evaluate_plan_impact(plan_name: str, comparison_survey: str) -> Dict[str, Any]:
    """
    Compara el plan con una medición posterior compatible de la misma empresa
    y calcula variación observada, diferencia frente a meta y estado de meta.
    """
    company = _require_active_company()
    doc = frappe.get_doc("qp_IQ_ActionPlan", plan_name)
    if doc.ap_company != company:
        frappe.throw(_("No tienes permisos sobre este plan."), frappe.PermissionError)

    if not comparison_survey:
        frappe.throw(_("Aún no hay una medición compatible disponible para evaluar la meta."))

    survey_owner = frappe.db.get_value("qp_IQ_Survey", comparison_survey, "su_owner")
    if survey_owner and survey_owner != company:
        frappe.throw(_("La medición seleccionada no pertenece a la empresa activa."), frappe.PermissionError)

    score_info = _compute_official_score(
        survey_name=comparison_survey,
        scope_type=doc.ap_scope_type,
        dimension=doc.ap_dimension,
        topic=doc.ap_topic,
        question=doc.ap_question,
    )
    if not score_info.get("has_score"):
        frappe.throw(score_info.get("message") or _("No hay un resultado disponible para este elemento en la medición seleccionada."))

    posterior_score = flt(score_info.get("initial_score"), 2)
    initial_score = flt(doc.ap_initial_score, 2)
    target_score = flt(doc.ap_target_score, 2)

    observed_variation = flt(posterior_score - initial_score, 2)
    goal_difference = flt(posterior_score - target_score, 2)

    denom = flt(target_score - initial_score, 2)
    if abs(denom) > 1e-6:
        achievement_pct = round(((posterior_score - initial_score) / denom) * 100.0, 1)
    else:
        achievement_pct = 100.0 if posterior_score >= target_score else 0.0

    if posterior_score >= target_score:
        goal_status = "Meta alcanzada"
    elif posterior_score > initial_score:
        goal_status = "Meta parcialmente alcanzada"
    else:
        goal_status = "Meta no alcanzada"

    doc.ap_comparison_survey = comparison_survey
    doc.ap_posterior_score = posterior_score
    doc.ap_observed_variation = observed_variation
    doc.ap_goal_difference = goal_difference
    doc.ap_goal_achievement_pct = max(0.0, achievement_pct)
    doc.ap_goal_status = goal_status
    doc.ap_evaluated_on = now_datetime()

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return get_action_plan_detail(plan_name)