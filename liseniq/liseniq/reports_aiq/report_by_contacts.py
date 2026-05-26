import frappe
import json
from frappe.utils import getdate, date_diff, nowdate

def inject_contacts_demographics_data(context, survey_name):
    """
    Función para ser llamada desde el controlador principal.
    Agrega primero los gráficos fijos (Rango de Edad y Antigüedad),
    luego extrae los demográficos en custom_additional_details,
    y calcula el promedio de respuestas.
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
    
    # Buscar respuestas para obtener los contactos
    responses = frappe.get_all("Survey Response",
        filters={"survey": ["in", [survey_name, su_name]]},
        fields=["name", "response_json", "user"]
    )

    contact_scores = {}
    contact_counts = {}
    
    for r in responses:
        if not r.response_json: 
            continue
            
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

    # Seección 1: Gráficos Demográficos Fijos (Edad, Antigüedad, Género)
    today = getdate(nowdate())

    # Obtener data base de contactos para Edad, Antigüedad y Género
    contacts_info = frappe.get_all("Contact",
        filters={"name": ["in", contacts_with_responses]},
        fields=["name", "custom_dob", "custom_entry_date", "gender"]
    )

    # Diccionarios pre-inicializados para mantener el orden exacto deseado
    age_ranges = {
        "< 25 años": {"score": 0.0, "count": 0},
        "25-35 años": {"score": 0.0, "count": 0},
        "35-45 años": {"score": 0.0, "count": 0},
        "45-55 años": {"score": 0.0, "count": 0},
        "> 55 años": {"score": 0.0, "count": 0}
    }

    seniority_ranges = {
        "< 6 meses": {"score": 0.0, "count": 0},
        "6m - 1 año": {"score": 0.0, "count": 0},
        "1 - 3 años": {"score": 0.0, "count": 0},
        "3 - 5 años": {"score": 0.0, "count": 0},
        "5 - 10 años": {"score": 0.0, "count": 0},
        "10 - 20 años": {"score": 0.0, "count": 0}
    }
    
    gender_ranges = {}

    for c in contacts_info:
        c_id = c.name
        if c_id not in contact_scores: continue
        avg_score = contact_scores[c_id] / contact_counts[c_id]

        # Cálculo de Rango de Edad
        if c.custom_dob:
            dob = getdate(c.custom_dob)
            days = date_diff(today, dob)
            years = days / 365.25
            
            if years < 25: k = "< 25 años"
            elif 25 <= years < 35: k = "25-35 años"
            elif 35 <= years < 45: k = "35-45 años"
            elif 45 <= years <= 55: k = "45-55 años"
            else: k = "> 55 años"

            age_ranges[k]["score"] += avg_score
            age_ranges[k]["count"] += 1

        # Cálculo de Antigüedad
        if c.custom_entry_date:
            entry = getdate(c.custom_entry_date)
            days = date_diff(today, entry)
            months = days / 30.44
            years = days / 365.25

            if months < 6: k = "< 6 meses"
            elif 6 <= months < 12: k = "6m - 1 año"
            elif 1 <= years < 3: k = "1 - 3 años"
            elif 3 <= years < 5: k = "3 - 5 años"
            elif 5 <= years < 10: k = "5 - 10 años"
            else: k = "10 - 20 años"

            seniority_ranges[k]["score"] += avg_score
            seniority_ranges[k]["count"] += 1

        # Cálculo de Género
        g = c.gender or "Sin Especificar"
        if g not in gender_ranges:
            gender_ranges[g] = {"score": 0.0, "count": 0}
            
        gender_ranges[g]["score"] += avg_score
        gender_ranges[g]["count"] += 1

    def build_fixed_data(title, ranges_dict, fixed_color="DYNAMIC"):
        data_list = []
        for k, v in ranges_dict.items():
            if v["count"] > 0:
                data_list.append({
                    "value": k,
                    "score": round(v["score"] / v["count"], 2)
                })
        if data_list:
            chart_data[title] = {
                "color": fixed_color,
                "is_fixed": True,
                "data": data_list
            }

    # Insertamos primero los fijos en el objeto final
    build_fixed_data("Rango de Edad", age_ranges)
    build_fixed_data("Antigüedad", seniority_ranges)
    build_fixed_data("Género", gender_ranges, "#3b82f6")
   

    # Segunda parte: Demográficos dinámicos definidos en custom_additional_details
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
            "is_fixed": False,
            "data": []
        }
        for val_name, stats in payload["values"].items():
            avg = round(stats["total_score"] / stats["count"], 2)
            chart_data[demo_title]["data"].append({
                "value": val_name,
                "score": avg
            })
        # Ordenar categoría dinámica de mayor a menor puntaje
        chart_data[demo_title]["data"].sort(key=lambda x: x["score"], reverse=True)
            
    context.contact_demographics_json = json.dumps(chart_data)
    return context