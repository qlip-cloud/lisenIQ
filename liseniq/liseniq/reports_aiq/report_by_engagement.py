import frappe
import json

# Importar el py que construye el contexto específico de demográficos por contacto para el reporte
from .report_by_contacts import inject_contacts_demographics_data

def build_engagement_context(context, survey_name):

    likert_types = frappe.get_all("qp_IQ_QuestionType", 
                                  filters={"qnt_type_name": ["like", "%Likert%"]}, 
                                  pluck="name")
    
    global_score = 0.0
    engagement_chart_data = []
    dimension_chart_data = []
    grouped_dimension_chart_data = []
    topic_questions_data = []

    if likert_types:
        likert_questions_data = frappe.get_all("qp_IQ_Question", 
                                          filters={"qn_type": ["in", likert_types]}, 
                                          fields=["name", "qn_demographic", "qn_statement", "qp_topic"])
        
        likert_questions = [q.name for q in likert_questions_data]
        
        q_to_engagement = {q.name: q.qn_demographic for q in likert_questions_data if q.qn_demographic}
        q_to_statement = {q.name: q.qn_statement for q in likert_questions_data}
        q_to_topic = {q.name: q.qp_topic for q in likert_questions_data if q.qp_topic}
        
        if likert_questions:
            demo_types = frappe.get_all("qp_IQ_DemographicType", 
                                        filters={"dt_object_type": "Pregunta"}, 
                                        fields=["name", "dt_title", "dt_tag_color"])
            valid_demographics = [d.name for d in demo_types]
            demo_title_map = {d.name: (d.dt_title or d.name) for d in demo_types}
            demo_color_map = {d.name: d.dt_tag_color for d in demo_types if d.dt_tag_color}

            topic_title_map = {}
            topic_color_map = {}
            try:
                topic_field = frappe.get_meta("qp_IQ_Question").get_field("qp_topic")
                if topic_field and topic_field.fieldtype == "Link" and topic_field.options:
                    t_doctype = topic_field.options
                    t_title_field = frappe.get_meta(t_doctype).title_field or "name"
                    
                    td_list = frappe.get_all(t_doctype, fields=["name", t_title_field])
                    topic_title_map = {d["name"]: (d.get(t_title_field) or d["name"]) for d in td_list}
            except Exception as e:
                frappe.log_error(f"Error extrayendo metadata de qp_topic: {e}", "AIQ Reports - Engagement")

            # Extraemos el color de los temas desde qp_IQ_DemographicType
            tema_types = frappe.get_all("qp_IQ_DemographicType", 
                                        filters={"dt_object_type": "Tema"}, 
                                        fields=["name", "dt_tag_color"])
            topic_color_map = {d.name: d.dt_tag_color for d in tema_types if d.dt_tag_color}

            su_name = frappe.db.get_value("qp_IQ_Survey", survey_name, "su_name") or survey_name
            
            survey_responses = frappe.get_all("Survey Response", 
                                              filters={"survey": ["in", [survey_name, su_name]]}, 
                                              pluck="response_json")
            
            total_score = 0.0
            total_answers = 0
            
            dimension_totals = {}
            dimension_counts = {}
            
            # Diccionarios para agrupar por demográfico
            grouped_dim_totals = {}
            grouped_dim_counts = {}

            topic_totals = {}
            topic_counts = {}

            # Diccionarios para guardar todas las preguntas sin importar si tienen demográfico
            question_totals = {}
            question_counts = {}

            for resp_json in survey_responses:
                if not resp_json:
                    continue
                try:
                    data = json.loads(resp_json)
                    for q_name, answer in data.items():
                        if q_name in likert_questions:
                            try:
                                val = float(answer)
                                
                                total_score += val
                                total_answers += 1

                                # Agrupación global de preguntas
                                question_totals[q_name] = question_totals.get(q_name, 0.0) + val
                                question_counts[q_name] = question_counts.get(q_name, 0) + 1
                                
                                if q_name in q_to_engagement:
                                    demo_id = q_to_engagement[q_name]
                                    if not valid_demographics or demo_id in valid_demographics:
                                        # Data por pregunta individual (para tablas Top/Bottom 10)
                                        dimension_totals[q_name] = dimension_totals.get(q_name, 0.0) + val
                                        dimension_counts[q_name] = dimension_counts.get(q_name, 0) + 1
                                        
                                        # Data agrupada por dimensión/demográfico (para el gráfico)
                                        grouped_dim_totals[demo_id] = grouped_dim_totals.get(demo_id, 0.0) + val
                                        grouped_dim_counts[demo_id] = grouped_dim_counts.get(demo_id, 0) + 1

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
                
            # Armamos data detallada para Top/Bottom 10
            for q_name, t_score in dimension_totals.items():
                avg = round(t_score / dimension_counts[q_name], 2)
                statement_text = q_to_statement.get(q_name, q_name)
                demo_id = q_to_engagement.get(q_name, "N/A")
                demo_title = demo_title_map.get(demo_id, demo_id)
                
                t_id = q_to_topic.get(q_name)
                t_title = topic_title_map.get(t_id, "N/A") if t_id else "N/A"
                
                dimension_chart_data.append({
                    "engagement": demo_title, 
                    "question": statement_text,
                    "topic": t_title,
                    "score": avg
                })
            dimension_chart_data.sort(key=lambda x: x["score"])

            # Armamos data para TODAS las preguntas, para las tablas por Tema
            for q_name, t_score in question_totals.items():
                if question_counts[q_name] > 0:
                    avg = round(t_score / question_counts[q_name], 2)
                    statement_text = q_to_statement.get(q_name, q_name)
                    
                    t_id = q_to_topic.get(q_name)
                    t_title = topic_title_map.get(t_id, "Sin Tema") if t_id else "Sin Tema"
                    t_color = topic_color_map.get(t_id, "") if t_id else ""

                    # Obtenemos la dimensión para agregarla a la tabla
                    demo_id = q_to_engagement.get(q_name)
                    demo_title = demo_title_map.get(demo_id, "Sin Dimensión") if demo_id else "Sin Dimensión"
                    
                    topic_questions_data.append({
                        "question": statement_text,
                        "topic": t_title,
                        "dimension": demo_title,
                        "score": avg,
                        "color": t_color
                    })

            # Armamos data agrupada para el Gráfico de Dimensiones
            for demo_id, t_score in grouped_dim_totals.items():
                avg = round(t_score / grouped_dim_counts[demo_id], 2)
                demo_title = demo_title_map.get(demo_id, demo_id)
                demo_color = demo_color_map.get(demo_id, "") 
                
                grouped_dimension_chart_data.append({
                    "engagement": demo_title,
                    "score": avg,
                    "color": demo_color
                })
            grouped_dimension_chart_data.sort(key=lambda x: x["score"])

            # Armamos data para el Gráfico de Engagement/Topics
            for t_id, t_score in topic_totals.items():
                avg = round(t_score / topic_counts[t_id], 2)
                t_title = topic_title_map.get(t_id, t_id)
                topic_color = topic_color_map.get(t_id, "")
                
                engagement_chart_data.append({
                    "topic": t_title,
                    "score": avg,
                    "color": topic_color
                })
            engagement_chart_data.sort(key=lambda x: x["score"])
    
    # Asignamos el score global calculado al contexto
    context.global_score = global_score
    
    # Empaquetamos toda la data específica de Engagement en el JSON del frontend
    context.report_specific_data_json = json.dumps({
        "engagement_chart_data": engagement_chart_data,
        "dimension_chart_data": dimension_chart_data,
        "grouped_dimension_chart_data": grouped_dimension_chart_data,
        "topic_questions_data": topic_questions_data
    })

    # Llamamos al controlador que inyecta la data de demográficos de contactos para el reporte
    context = inject_contacts_demographics_data(context, survey_name)

    return context