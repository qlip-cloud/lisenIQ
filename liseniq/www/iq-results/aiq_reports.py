import frappe
import json
from frappe import _
from liseniq.utils.login_util import global_website_context

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Debe iniciar sesión para acceder."), frappe.PermissionError)

    # Inyectar el contexto global (Suscripciones, Features, Usuario, Compañía, etc.)
    context = global_website_context(context)

    # Validar si tiene la funcionalidad para entrar directamente por URL
    if not context.get('app_features') or 'aiq_reports' not in context.get('app_features'):
        frappe.throw(_("Su plan no incluye acceso a Reportes Avanzados AIQ."), frappe.PermissionError)

    # Configuración base de la página para Frappe
    context.no_cache = 1
    context.page_title = _("Reporte de Resultados")
    context.no_breadcrumbs = True
    context.is_navbar_custom = True
    
    # Obtener el nombre de la encuesta desde la URL para inyectarlo en el HTML
    survey_name = frappe.form_dict.get('survey_name', '')
    context.survey_name = survey_name
    context.survey_title = frappe.form_dict.get('survey_title', _("Reporte de Resultados"))

    # Calculo de metricas globales y datos para gráficos solo si hay una encuesta seleccionada
    if survey_name:
        # Total de Participantes (Contactos enviados) y % de Respuesta
        total_recipients = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey_name})
        
        # Obtener el estado 'Responded' de manera optimizada
        rs_responded = frappe.db.get_value("qp_IQ_RecipientStatus", {"rs_status": "Responded"}, "name") or "Responded"
        total_responses = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey_name, "sr_status": rs_responded})

        response_percentage = 0
        if total_recipients > 0:
            response_percentage = round((total_responses / total_recipients) * 100)

        context.total_recipients = total_recipients
        context.total_responses = total_responses
        context.response_percentage = response_percentage

        # Puntaje Global y Datos para Gráficos
        likert_types = frappe.get_all("qp_IQ_QuestionType", 
                                      filters={"qnt_type_name": ["like", "%Likert%"]}, 
                                      pluck="name")
        
        global_score = 0.0
        culture_chart_data = []
        dimension_chart_data = []

        if likert_types:
            # Traemos las preguntas Likert incluyendo el enunciado y el topic
            likert_questions_data = frappe.get_all("qp_IQ_Question", 
                                              filters={"qn_type": ["in", likert_types]}, 
                                              fields=["name", "qn_demographic", "qn_statement", "qp_topic"])
            
            likert_questions = [q.name for q in likert_questions_data]
            
            # Mapeos
            q_to_culture = {q.name: q.qn_demographic for q in likert_questions_data if q.qn_demographic}
            q_to_statement = {q.name: q.qn_statement for q in likert_questions_data}
            q_to_topic = {q.name: q.qp_topic for q in likert_questions_data if q.qp_topic}
            
            if likert_questions:
                # Mapeo de demograficos
                demo_types = frappe.get_all("qp_IQ_DemographicType", 
                                            filters={"dt_object_type": "Pregunta"}, 
                                            fields=["name", "dt_title"])
                valid_demographics = [d.name for d in demo_types]
                demo_title_map = {d.name: (d.dt_title or d.name) for d in demo_types}

                # Mapeo de Topics/Temas
                topic_title_map = {}
                try:
                    topic_field = frappe.get_meta("qp_IQ_Question").get_field("qp_topic")
                    if topic_field and topic_field.fieldtype == "Link" and topic_field.options:
                        t_doctype = topic_field.options
                        t_title_field = frappe.get_meta(t_doctype).title_field or "name"
                        td_list = frappe.get_all(t_doctype, fields=["name", t_title_field])
                        # Asignamos el texto (title/nombre) para mostrar en el Eje X en lugar del ID
                        topic_title_map = {d["name"]: (d.get(t_title_field) or d["name"]) for d in td_list}
                except Exception as e:
                    frappe.log_error(f"Error extrayendo metadata de qp_topic: {e}", "AIQ Reports")

                su_name = frappe.db.get_value("qp_IQ_Survey", survey_name, "su_name") or survey_name
                
                survey_responses = frappe.get_all("Survey Response", 
                                                  filters={"survey": ["in", [survey_name, su_name]]}, 
                                                  pluck="response_json")
                
                total_score = 0.0
                total_answers = 0
                
                dimension_totals = {}
                dimension_counts = {}

                topic_totals = {}
                topic_counts = {}

                for resp_json in survey_responses:
                    if not resp_json:
                        continue
                    try:
                        data = json.loads(resp_json)
                        for q_name, answer in data.items():
                            if q_name in likert_questions:
                                try:
                                    val = float(answer)
                                    
                                    # Acumular para el Promedio Global
                                    total_score += val
                                    total_answers += 1
                                    
                                    # Acumular para el Gráfico de Dimensiones (por pregunta)
                                    if q_name in q_to_culture:
                                        demo_id = q_to_culture[q_name]
                                        if not valid_demographics or demo_id in valid_demographics:
                                            dimension_totals[q_name] = dimension_totals.get(q_name, 0.0) + val
                                            dimension_counts[q_name] = dimension_counts.get(q_name, 0) + 1

                                    # Acumular para el Gráfico de Tipo Cultura (por qp_topic)
                                    if q_name in q_to_topic:
                                        t_id = q_to_topic[q_name]
                                        topic_totals[t_id] = topic_totals.get(t_id, 0.0) + val
                                        topic_counts[t_id] = topic_counts.get(t_id, 0) + 1
                                        
                                except (ValueError, TypeError):
                                    pass
                    except Exception:
                        continue
                
                if total_answers > 0:
                    global_score = round(total_score / total_answers, 2)
                    
                # Construir Data: Gráfico de Dimensiones
                for q_name, t_score in dimension_totals.items():
                    avg = round(t_score / dimension_counts[q_name], 2)
                    statement_text = q_to_statement.get(q_name, q_name)
                    demo_id = q_to_culture.get(q_name, "N/A")
                    demo_title = demo_title_map.get(demo_id, demo_id)
                    
                    # Añadir el tema para mostrar en Top 10 y Bottom 10
                    t_id = q_to_topic.get(q_name)
                    t_title = topic_title_map.get(t_id, "N/A") if t_id else "N/A"
                    
                    dimension_chart_data.append({
                        "culture": demo_title, 
                        "question": statement_text,
                        "topic": t_title,
                        "score": avg
                    })
                dimension_chart_data.sort(key=lambda x: x["score"])

                # Construir Data: Gráfico de Tipo de Cultura
                for t_id, t_score in topic_totals.items():
                    avg = round(t_score / topic_counts[t_id], 2)
                    t_title = topic_title_map.get(t_id, t_id)
                    
                    culture_chart_data.append({
                        "topic": t_title,
                        "score": avg
                    })
                culture_chart_data.sort(key=lambda x: x["score"])
        
        context.global_score = global_score
        context.culture_chart_data = json.dumps(culture_chart_data)
        context.dimension_chart_data = json.dumps(dimension_chart_data)
    else:
        # Valores por defecto de seguridad si no hay medición seleccionada
        context.total_recipients = 0
        context.total_responses = 0
        context.response_percentage = 0
        context.global_score = 0.0
        context.culture_chart_data = "[]"
        context.dimension_chart_data = "[]"

    return context