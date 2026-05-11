import frappe
import json

def build_culture_context(context, survey_name):

    likert_types = frappe.get_all("qp_IQ_QuestionType", 
                                  filters={"qnt_type_name": ["like", "%Likert%"]}, 
                                  pluck="name")
    
    global_score = 0.0
    culture_chart_data = []
    dimension_chart_data = []

    if likert_types:
        likert_questions_data = frappe.get_all("qp_IQ_Question", 
                                          filters={"qn_type": ["in", likert_types]}, 
                                          fields=["name", "qn_demographic", "qn_statement", "qp_topic"])
        
        likert_questions = [q.name for q in likert_questions_data]
        
        q_to_culture = {q.name: q.qn_demographic for q in likert_questions_data if q.qn_demographic}
        q_to_statement = {q.name: q.qn_statement for q in likert_questions_data}
        q_to_topic = {q.name: q.qp_topic for q in likert_questions_data if q.qp_topic}
        
        if likert_questions:
            demo_types = frappe.get_all("qp_IQ_DemographicType", 
                                        filters={"dt_object_type": "Pregunta"}, 
                                        fields=["name", "dt_title"])
            valid_demographics = [d.name for d in demo_types]
            demo_title_map = {d.name: (d.dt_title or d.name) for d in demo_types}

            topic_title_map = {}
            try:
                topic_field = frappe.get_meta("qp_IQ_Question").get_field("qp_topic")
                if topic_field and topic_field.fieldtype == "Link" and topic_field.options:
                    t_doctype = topic_field.options
                    t_title_field = frappe.get_meta(t_doctype).title_field or "name"
                    td_list = frappe.get_all(t_doctype, fields=["name", t_title_field])
                    topic_title_map = {d["name"]: (d.get(t_title_field) or d["name"]) for d in td_list}
            except Exception as e:
                frappe.log_error(f"Error extrayendo metadata de qp_topic: {e}", "AIQ Reports - Cultura")

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
                                
                                total_score += val
                                total_answers += 1
                                
                                if q_name in q_to_culture:
                                    demo_id = q_to_culture[q_name]
                                    if not valid_demographics or demo_id in valid_demographics:
                                        dimension_totals[q_name] = dimension_totals.get(q_name, 0.0) + val
                                        dimension_counts[q_name] = dimension_counts.get(q_name, 0) + 1

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
                
            for q_name, t_score in dimension_totals.items():
                avg = round(t_score / dimension_counts[q_name], 2)
                statement_text = q_to_statement.get(q_name, q_name)
                demo_id = q_to_culture.get(q_name, "N/A")
                demo_title = demo_title_map.get(demo_id, demo_id)
                
                t_id = q_to_topic.get(q_name)
                t_title = topic_title_map.get(t_id, "N/A") if t_id else "N/A"
                
                dimension_chart_data.append({
                    "culture": demo_title, 
                    "question": statement_text,
                    "topic": t_title,
                    "score": avg
                })
            dimension_chart_data.sort(key=lambda x: x["score"])

            for t_id, t_score in topic_totals.items():
                avg = round(t_score / topic_counts[t_id], 2)
                t_title = topic_title_map.get(t_id, t_id)
                
                culture_chart_data.append({
                    "topic": t_title,
                    "score": avg
                })
            culture_chart_data.sort(key=lambda x: x["score"])
    
    # Asignamos el score global calculado al contexto
    context.global_score = global_score
    
    # Empaquetamos toda la data específica de Cultura en el JSON del frontend
    context.report_specific_data_json = json.dumps({
        "culture_chart_data": culture_chart_data,
        "dimension_chart_data": dimension_chart_data
    })

    return context