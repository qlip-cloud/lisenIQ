import frappe
import json

# Importar el py que construye el contexto específico de demográficos por contacto para el reporte
from .report_by_contacts import inject_contacts_demographics_data

def build_engagement_context(context, survey_name):

    all_q_types = frappe.get_all("qp_IQ_QuestionType", fields=["name", "qnt_mnemonico"], ignore_permissions=True)
    valid_types = []
    nps_types = []
    for qt in all_q_types:
        t_mnemonic = qt.qnt_mnemonico or ""
        if t_mnemonic in ["scale_likert", "score_nps"]:
            valid_types.append(qt.name)
        if t_mnemonic == "score_nps":
            nps_types.append(qt.name)
    
    global_score = 0.0
    engagement_index_score = 0.0
    engagement_chart_data = []
    dimension_chart_data = []
    grouped_dimension_chart_data = []
    topic_questions_data = []
    engagement_index_chart_data = []
    nps_score = 0

    if valid_types:
        valid_questions_data = frappe.get_all("qp_IQ_Question", 
                                          filters={"qn_type": ["in", valid_types]}, 
                                          fields=["name", "qn_demographic", "qn_statement", "qp_topic", "qn_type"],
                                          ignore_permissions=True)
        
        valid_questions = [q.name for q in valid_questions_data]
        nps_questions = [q.name for q in valid_questions_data if q.qn_type in nps_types]
        
        q_to_engagement = {q.name: q.qn_demographic for q in valid_questions_data if q.qn_demographic}
        q_to_statement = {q.name: (q.qn_statement or q.name).strip() for q in valid_questions_data}
        q_to_topic = {q.name: q.qp_topic for q in valid_questions_data if q.qp_topic}
        
        if valid_questions:
            # 1. Demográficos de Dimensión y Pregunta (para qn_demographic e Índice de Engagement)
            demo_types = frappe.get_all("qp_IQ_DemographicType", 
                                        filters={"dt_object_type": ["in", ["Dimension", "Pregunta"]]}, 
                                        fields=["name", "dt_title", "dt_tag_color", "dt_mnemonico", "dt_object_type"],
                                        ignore_permissions=True)
            
            # Dimensiones válidas (dt_object_type == "Dimension", con fallback a "Pregunta" si aplica)
            valid_demographics = [d.name for d in demo_types if d.dt_object_type in ["Dimension", "Pregunta"]]
            demo_title_map = {d.name: (d.dt_title or d.name) for d in demo_types}
            demo_color_map = {d.name: d.dt_tag_color for d in demo_types if d.dt_tag_color}
            demo_mnemonic_map = {d.name: d.dt_mnemonico for d in demo_types if d.dt_mnemonico}

            # 2. Demográficos de Tema (dt_object_type == "Tema" para qp_topic)
            tema_types = frappe.get_all("qp_IQ_DemographicType", 
                                        filters={"dt_object_type": "Tema"}, 
                                        fields=["name", "dt_title", "dt_tag_color"],
                                        ignore_permissions=True)
            topic_title_map = {d.name: (d.dt_title or d.name) for d in tema_types}
            topic_color_map = {d.name: d.dt_tag_color for d in tema_types if d.dt_tag_color}

            su_name = frappe.db.get_value("qp_IQ_Survey", survey_name, "su_name") or survey_name
            
            survey_responses = frappe.get_all("Survey Response", 
                                              filters={"survey": ["in", [survey_name, su_name]]}, 
                                              pluck="response_json",
                                              ignore_permissions=True)
            
            total_score = 0.0
            total_answers = 0
            
            dimension_totals = {}
            dimension_counts = {}
            
            topic_totals = {}
            topic_counts = {}

            # Diccionarios para el Índice de Engagement
            ei_question_totals = {}
            ei_question_counts = {}

            # Diccionarios para guardar todas las preguntas sin importar si tienen demográfico
            question_totals = {}
            question_counts = {}

            # Variables para el eNPS
            nps_promoters = 0
            nps_detractors = 0
            nps_total_answers = 0

            for resp_json in survey_responses:
                if not resp_json:
                    continue
                try:
                    data = json.loads(resp_json)
                    for q_name, answer in data.items():
                        if q_name in valid_questions:
                            try:
                                original_val = float(answer)
                                val = original_val
                                
                                # Lógica para eNPS (antes de convertirlo a escala Likert)
                                if q_name in nps_questions:
                                    if original_val <= 6.0:
                                        nps_detractors += 1
                                    elif original_val >= 9.0:
                                        nps_promoters += 1
                                    nps_total_answers += 1

                                    # Conversión de escala NPS a Likert (1 - 5) para el global de la encuesta
                                    if original_val <= 2:
                                        val = 1.0
                                    elif original_val <= 4:
                                        val = 2.0
                                    elif original_val <= 6:
                                        val = 3.0
                                    elif original_val <= 8:
                                        val = 4.0
                                    else:
                                        val = 5.0

                                total_score += val
                                total_answers += 1

                                # Agrupación global de preguntas
                                question_totals[q_name] = question_totals.get(q_name, 0.0) + val
                                question_counts[q_name] = question_counts.get(q_name, 0) + 1
                                
                                if q_name in q_to_engagement:
                                    demo_id = q_to_engagement[q_name]
                                    
                                    if not valid_demographics or demo_id in valid_demographics:
                                        dimension_totals[q_name] = dimension_totals.get(q_name, 0.0) + val
                                        dimension_counts[q_name] = dimension_counts.get(q_name, 0) + 1

                                    # Lógica de Índice de Engagement
                                    if demo_mnemonic_map.get(demo_id) == "question_engagement_index":
                                        ei_question_totals[q_name] = ei_question_totals.get(q_name, 0.0) + val
                                        ei_question_counts[q_name] = ei_question_counts.get(q_name, 0) + 1

                                if q_name in q_to_topic:
                                    t_id = q_to_topic[q_name]
                                    if not topic_title_map or t_id in topic_title_map:
                                        topic_totals[t_id] = topic_totals.get(t_id, 0.0) + val
                                        topic_counts[t_id] = topic_counts.get(t_id, 0) + 1
                                    
                            except (ValueError, TypeError):
                                pass
                except Exception:
                    continue
            
            if total_answers > 0:
                global_score = round(total_score / total_answers, 2)
                
            # Calculamos el puntaje global del Índice de Engagement
            ei_total_score = 0.0
            ei_total_answers = 0
            for q_name, count in ei_question_counts.items():
                ei_total_score += ei_question_totals.get(q_name, 0.0)
                ei_total_answers += count

            if ei_total_answers > 0:
                engagement_index_score = round(ei_total_score / ei_total_answers, 2)
            
            # Calculamos los porcentajes y el score de eNPS
            if nps_total_answers > 0:
                nps_promoters_perc = round((nps_promoters / nps_total_answers) * 100)
                nps_detractors_perc = round((nps_detractors / nps_total_answers) * 100)
                nps_score = nps_promoters_perc - nps_detractors_perc

            # Armamos data detallada por pregunta (usando qn_statement) para Top/Bottom 10 y el gráfico de Atributos
            source_totals = dimension_totals if dimension_totals else question_totals
            source_counts = dimension_counts if dimension_totals else question_counts

            for q_name, t_score in source_totals.items():
                if source_counts.get(q_name, 0) <= 0:
                    continue
                avg = round(t_score / source_counts[q_name], 2)
                statement_text = q_to_statement.get(q_name, q_name)
                demo_id = q_to_engagement.get(q_name)
                demo_title = demo_title_map.get(demo_id, "N/A") if demo_id else "N/A"
                demo_color = demo_color_map.get(demo_id, "") if demo_id else ""
                
                t_id = q_to_topic.get(q_name)
                t_title = topic_title_map.get(t_id, "N/A") if t_id else "N/A"
                
                dimension_chart_data.append({
                    "engagement": demo_title,
                    "dimension": demo_title,
                    "question": statement_text,
                    "topic": t_title,
                    "score": avg
                })

                # En el gráfico de Atributos (#dimension-card-container) mostramos el enunciado (qn_statement)
                grouped_dimension_chart_data.append({
                    "engagement": statement_text,
                    "question": statement_text,
                    "dimension": demo_title,
                    "score": avg,
                    "color": demo_color
                })

            dimension_chart_data.sort(key=lambda x: x["score"])
            grouped_dimension_chart_data.sort(key=lambda x: x["score"])

            # Armamos data para el Gráfico de Índice de Engagement
            for q_name, t_score in ei_question_totals.items():
                if ei_question_counts[q_name] > 0:
                    avg = round(t_score / ei_question_counts[q_name], 2)
                    statement_text = q_to_statement.get(q_name, q_name)
                    demo_id = q_to_engagement.get(q_name)
                    demo_color = demo_color_map.get(demo_id, "") 
                    
                    engagement_index_chart_data.append({
                        "question": statement_text,
                        "score": avg,
                        "color": demo_color
                    })
            engagement_index_chart_data.sort(key=lambda x: x["score"], reverse=True)

            # Armamos data para TODAS las preguntas, para las tablas por Tema
            for q_name, t_score in question_totals.items():
                if question_counts[q_name] > 0:
                    avg = round(t_score / question_counts[q_name], 2)
                    statement_text = q_to_statement.get(q_name, q_name)
                    
                    t_id = q_to_topic.get(q_name)
                    t_title = topic_title_map.get(t_id, "Sin Tema") if t_id else "Sin Tema"
                    t_color = topic_color_map.get(t_id, "") if t_id else ""

                    demo_id = q_to_engagement.get(q_name)
                    demo_title = demo_title_map.get(demo_id, "Sin Dimensión") if demo_id else "Sin Dimensión"
                    
                    topic_questions_data.append({
                        "question": statement_text,
                        "topic": t_title,
                        "dimension": demo_title,
                        "score": avg,
                        "color": t_color
                    })

            # Armamos data para el Gráfico de Engagement/Topics (Agrupado por TÍTULO de Tema para evitar duplicados)
            topic_title_agg_totals = {}
            topic_title_agg_counts = {}
            topic_title_agg_colors = {}

            for t_id, t_score in topic_totals.items():
                t_title = topic_title_map.get(t_id, t_id)
                topic_title_agg_totals[t_title] = topic_title_agg_totals.get(t_title, 0.0) + t_score
                topic_title_agg_counts[t_title] = topic_title_agg_counts.get(t_title, 0) + topic_counts[t_id]
                if t_title not in topic_title_agg_colors:
                    topic_title_agg_colors[t_title] = topic_color_map.get(t_id, "")

            for t_title, t_score in topic_title_agg_totals.items():
                avg = round(t_score / topic_title_agg_counts[t_title], 2)
                engagement_chart_data.append({
                    "topic": t_title,
                    "score": avg,
                    "color": topic_title_agg_colors.get(t_title, "")
                })
            engagement_chart_data.sort(key=lambda x: x["score"])
    
    # Asignamos los scores calculados al contexto
    context.global_score = global_score
    context.engagement_index_score = engagement_index_score
    
    # Empaquetamos toda la data específica de Engagement en el JSON del frontend
    context.report_specific_data_json = json.dumps({
        "engagement_chart_data": engagement_chart_data,
        "dimension_chart_data": dimension_chart_data,
        "grouped_dimension_chart_data": grouped_dimension_chart_data,
        "topic_questions_data": topic_questions_data,
        "engagement_index_chart_data": engagement_index_chart_data,
        "nps_data": {
            "score": nps_score
        }
    })

    # Llamamos al controlador que inyecta la data de demográficos de contactos para el reporte
    context = inject_contacts_demographics_data(context, survey_name)

    return context