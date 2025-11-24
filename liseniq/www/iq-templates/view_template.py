import frappe
from frappe import _


def get_context(context):

    if frappe.session.user == "Guest":
        frappe.throw(_("Cliente aún no ha sido registrado. Por favor comunique al Administrador."), frappe.PermissionError)

    template_name = frappe.request.args.get('name')
    if not template_name:
        frappe.throw("No se especificó el nombre de la plantilla.", frappe.DoesNotExistError)

    try:
        template_doc = frappe.get_doc("qp_IQ_Template", template_name)
        template_doc.has_permission("read")

        if template_doc.tp_category:
            category_name = frappe.db.get_value("qp_IQ_QuestionCategory", template_doc.tp_category, "qnc_category")
        else:
            category_name = "Sin categoría"

        template_info = {
            "tp_name": template_doc.tp_name,
            "tp_description": template_doc.tp_description,
            "category_name": category_name
        }
        context.template_data = template_info

        questions = []
        if template_doc.tp_questions:
            for tq in template_doc.tp_questions:
                q_doc = frappe.get_doc("qp_IQ_Question", tq.tq_question)
                
                type_name = frappe.db.get_value("qp_IQ_QuestionType", q_doc.qn_type, "qnt_type_name") if q_doc.qn_type else "No definido"
                q_category_name = frappe.db.get_value("qp_IQ_QuestionCategory", q_doc.qn_category, "qnc_category") if q_doc.qn_category else "General"
                demographic_name = frappe.db.get_value("qp_IQ_DemographicType", q_doc.qn_demographic, "dt_title") if q_doc.qn_demographic else "General"

                question_data = {
                    "text": q_doc.qn_statement,
                    "type_name": type_name,
                    "category_name": q_category_name,
                    "demographic_name": demographic_name,
                    "demographic": demographic_name,
                    "options": []
                }

                if type_name in ['Opción Múltiple', 'Selección Única'] and q_doc.qn_response_options:
                    options = [opt.qo_option_text for opt in q_doc.qn_response_options]
                    question_data["options"] = options
                
                questions.append(question_data)
        
        context.questions = questions
        context.questions_count = len(questions)

    except frappe.DoesNotExistError:
        frappe.throw(f"La plantilla {template_name} no fue encontrada.", title="Error")

    context.page_title = f"Ver Modelo: {template_doc.tp_name}"
    context.no_cache = 1
    context.is_navbar_custom = True

    return context
