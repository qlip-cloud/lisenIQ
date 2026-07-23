import frappe
from frappe import _
from liseniq.utils.login_util import global_website_context

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Debe iniciar sesión para acceder."), frappe.PermissionError)

    # Inyectar el contexto global
    context = global_website_context(context)

    # Validar acceso
    if not context.get('app_features') or 'aiq_reports' not in context.get('app_features'):
        frappe.throw(_("Su plan no incluye acceso a Reportes Avanzados AIQ."), frappe.PermissionError)

    # Configuración base de la página
    context.no_cache = 1
    context.page_title = _("Reporte de Resultados")
    context.no_breadcrumbs = True
    context.is_navbar_custom = True
    
    survey_name = frappe.form_dict.get('survey_name', '')
    context.survey_name = survey_name

    # Obtener el título de la encuesta
    if survey_name:
        db_title = frappe.db.get_value("qp_IQ_Survey", survey_name, "su_name")
        context.survey_title = db_title if db_title else survey_name
    else:
        context.survey_title = _("Reporte de Resultados")

    if survey_name:
        # Métricas Globales (Comunes para todas las categorías)
        context = calculate_global_metrics(context, survey_name)
        
        # Identificar el 'name' de la Categoría de la Encuesta, su mnemónico y su descripción
        category_name, category_mnemonic, category_desc = get_survey_category_data(survey_name)
        
        # Pasamos el name de la categoría, el mnemónico y la descripción al contexto para la UI (HTML/JS)
        context.report_category = category_name
        context.report_category_mnemonic = category_mnemonic
        context.report_category_desc = category_desc

        # Enrutar a la Estrategia Específica usando el mnemónico explícito
        if category_mnemonic == "template_culture":
            try:
                # Contexto específico para reportes de Cultura
                from liseniq.liseniq.reports_aiq.report_culture import build_culture_context
                context = build_culture_context(context, survey_name)
            except ImportError as e:
                frappe.log_error(f"Error cargando módulo de Cultura: {e}", "AIQ Reports")
                context.is_unsupported_report = True
        elif category_mnemonic == "template_engagement":
            try:
                # Contexto específico para reportes de Engagement
                from liseniq.liseniq.reports_aiq.report_by_engagement import build_engagement_context
                context = build_engagement_context(context, survey_name)
            except ImportError as e:
                frappe.log_error(f"Error cargando módulo de Engagement: {e}", "AIQ Reports")
                context.is_unsupported_report = True
        else:
            # Si no es Cultura, Engagement ni otra soportada, marcamos como no soportado
            context.is_unsupported_report = True
    else:
        # Valores por defecto de seguridad
        context.total_recipients = 0
        context.total_responses = 0
        context.response_percentage = 0
        context.global_score = 0.0
        context.report_specific_data_json = "{}"

    return context

def get_survey_category_data(survey_name):
    """Obtiene el 'name' de la categoría (qp_IQ_TemplateCategory), su mnemónico explícito y su descripción (qnc_category)."""
    template_id = frappe.db.get_value("qp_IQ_Survey", survey_name, "su_template")
    if not template_id: return "", "", ""
    
    category_link = frappe.db.get_value("qp_IQ_Template", template_id, "tp_category")
    if not category_link: return "", "", ""
    
    category_data = frappe.db.get_value("qp_IQ_TemplateCategory", category_link, ["name", "qnc_mnemonico", "qnc_category"], as_dict=True)
    
    if category_data:
        return category_data.get("name") or "", category_data.get("qnc_mnemonico") or "", category_data.get("qnc_category") or ""
        
    return "", "", ""

def calculate_global_metrics(context, survey_name):
    """Calcula las métricas de participación que aplican a todo tipo de medición."""
    total_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey_name})
    
    rs_responded = frappe.db.get_value("qp_IQ_RecipientStatus", {"rs_status": "Responded"}, "name") or "Responded"
    total_responses = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey_name, "sr_status": rs_responded})

    response_percentage = 0
    if total_recipients > 0:
        response_percentage = round((total_responses / total_recipients) * 100)

    context.total_recipients = total_recipients
    context.total_responses = total_responses
    context.response_percentage = response_percentage
    
    return context