import frappe
import json

def inject_contacts_demographics_data(context, survey_name):
    """
    Función para ser llamada desde el controlador principal (ej: aiq_reports.py o report_culture.py).
    Extrae los contactos que respondieron, busca sus demográficos en custom_additional_details,
    los agrupa y calcula el promedio de respuestas.
    Inyecta un string JSON en el context: 'contact_demographics_json'
    """

    chart_data = {}
    
    # Obtener tipo Likert y preguntas válidas
    likert_types = frappe.get_all("qp_IQ_QuestionType", 
                                  filters={"qnt_type_name": ["like", "%Likert%"]}, 
                                  pluck="name")
    if not likert_types:
        context.contact_demographics_json = json.dumps(chart_data)
        return context
        
    likert_questions = frappe.get_all("qp_IQ_Question", 
                                      filters={"qn_type": ["in", likert_types]}, 
                                      pluck="name")
    if not likert_questions:
        context.contact_demographics_json = json.dumps(chart_data)
        return context
        
    su_name = frappe.db.get_value("qp_IQ_Survey", survey_name, "su_name") or survey_name
    
    # Buscar primero las respuestas en el dt Survey Response para obtener los contactos
    responses = frappe.get_all("Survey Response",
        filters={"survey": ["in", [survey_name, su_name]]},
        fields=["name", "response_json", "user"]
    )

    contact_scores = {}
    contact_counts = {}
    
    for r in responses:
        if not r.response_json: 
            continue
            
        # Obtenemos el contacto directamente de la respuesta
        contact_id = r.user
            
        if not contact_id: 
            continue
            
        try:
            data = json.loads(r.response_json)
            resp_score = 0.0
            resp_count = 0
            
            for q_name, answer in data.items():
                if q_name in likert_questions:
                    try:
                        resp_score += float(answer)
                        resp_count += 1
                    except (ValueError, TypeError):
                        pass
            
            # Promedio de la encuesta para este contacto
            if resp_count > 0:
                avg_response_score = resp_score / resp_count
                contact_scores[contact_id] = contact_scores.get(contact_id, 0.0) + avg_response_score
                contact_counts[contact_id] = contact_counts.get(contact_id, 0) + 1
        except Exception:
            continue
            
    contacts_with_responses = list(contact_scores.keys())
    
    if not contacts_with_responses:
        context.contact_demographics_json = json.dumps(chart_data)
        return context
        
    # Buscar los demográficos de cada contacto en qp_IQ_ContactAdditionalDetail
    demographics = frappe.get_all("qp_IQ_ContactAdditionalDetail",
        filters={
            "parent": ["in", contacts_with_responses], 
            "parenttype": "Contact",
            "parentfield": "custom_additional_details"
        },
        fields=["parent", "cad_demographic_type", "cad_value"]
    )
    
    # Extraer nombre y color de los tipos demográficos para mostrar en el reporte
    demo_links = list(set([d.cad_demographic_type for d in demographics if d.cad_demographic_type]))
    demo_info_map = {}
    if demo_links:
        try:
            dt_types = frappe.get_all("qp_IQ_DemographicType", 
                                      filters={"name": ["in", demo_links]}, 
                                      fields=["name", "dt_title", "dt_tag_color"])
            # Guardamos el título y el color asignado en el DocType
            demo_info_map = {d.name: {"title": d.dt_title or d.name, "color": d.dt_tag_color} for d in dt_types}
        except Exception:
            pass 

    # Agrupar la data por Demográfico y su Valor
    grouped_data = {}
    
    for d in demographics:
        c_id = d.parent
        if c_id not in contact_scores: 
            continue
        
        demo_key = d.cad_demographic_type
        info = demo_info_map.get(demo_key, {})
        demo_title = info.get("title", demo_key)
        demo_color = info.get("color", "")
        
        demo_val = d.cad_value or "Sin Asignar"
        
        # Promedio global del contacto
        c_avg_score = contact_scores[c_id] / contact_counts[c_id]
        
        if demo_title not in grouped_data:
            grouped_data[demo_title] = {"color": demo_color, "values": {}}
            
        if demo_val not in grouped_data[demo_title]["values"]:
            grouped_data[demo_title]["values"][demo_val] = {"total_score": 0.0, "count": 0}
            
        # Sumamos para agrupar y evitar duplicados
        grouped_data[demo_title]["values"][demo_val]["total_score"] += c_avg_score
        grouped_data[demo_title]["values"][demo_val]["count"] += 1
        
    # Formatear la salida incluyendo el color
    for demo_title, payload in grouped_data.items():
        chart_data[demo_title] = {
            "color": payload["color"],
            "data": []
        }
        for val_name, stats in payload["values"].items():
            avg = round(stats["total_score"] / stats["count"], 2)
            chart_data[demo_title]["data"].append({
                "value": val_name,
                "score": avg
            })
        # Ordenar cada categoría de mayor a menor puntaje
        chart_data[demo_title]["data"].sort(key=lambda x: x["score"], reverse=True)
            
    context.contact_demographics_json = json.dumps(chart_data)
    return context