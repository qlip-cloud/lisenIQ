import frappe

def safe_add_index(doctype, fields):
    """
    Verifica si la tabla y las columnas existen antes de intentar crear el índice
    para evitar errores durante el bench migrate.
    """
    if not frappe.db.table_exists(doctype):
        frappe.logger().warning(f"La tabla para el DocType '{doctype}' no existe. Omitiendo índices.")
        return

    # Validar que todos los campos del índice existan (excepto 'parent' que es nativo en tablas hijo)
    for field in fields:
        if field != 'parent' and not frappe.db.has_column(doctype, field):
            frappe.logger().warning(f"El campo '{field}' no existe en '{doctype}'. Omitiendo índice: {fields}.")
            return

    try:
        frappe.db.add_index(doctype, fields)
        frappe.logger().info(f"Índice asegurado en '{doctype}' para las columnas: {fields}")
    except Exception as e:
        frappe.log_error(f"Excepción controlada al crear índice en '{doctype}' para {fields}: {str(e)}")


def execute():
    """
    Parche maestro para crear índices de base de datos en las tablas del módulo Liseniq.
    Se priorizan campos de tipo Link, Select (estados) y tokens de búsqueda.
    """
    frappe.logger().info("Iniciando creación de índices de rendimiento para Liseniq...")

    try:
        # 1. qp_IQ_Survey (Encuestas)
        safe_add_index("qp_IQ_Survey", ["su_name"])
        safe_add_index("qp_IQ_Survey", ["su_owner"])
        safe_add_index("qp_IQ_Survey", ["su_template"])
        safe_add_index("qp_IQ_Survey", ["su_status"])
        safe_add_index("qp_IQ_Survey", ["su_in_history"]) # Muy usado en tus filtros booleanos

        # 2. qp_IQ_SurveyHistoricData (Histórico masivo)
        safe_add_index("qp_IQ_SurveyHistoricData", ["shd_survey_id"])
        safe_add_index("qp_IQ_SurveyHistoricData", ["shd_document_number"])
        safe_add_index("qp_IQ_SurveyHistoricData", ["shd_company"])

        # 3. Tablas Hijo de Demográficos
        # Índice compuesto: Vital para buscar los demográficos de un contacto específico
        safe_add_index("qp_IQ_ContactAdditionalDetail", ["parent", "cad_demographic_type"])
        safe_add_index("qp_IQ_ContactDetailHistoric", ["parent"])

        # 4. qp_IQ_DemographicType
        safe_add_index("qp_IQ_DemographicType", ["dt_object_type"]) # Usado en report.py para filtrar 'Contacto' o 'Pregunta'
        safe_add_index("qp_IQ_DemographicType", ["dt_creator_company"])

        # 5. qp_IQ_Question (Banco de preguntas)
        safe_add_index("qp_IQ_Question", ["qn_owner"])
        safe_add_index("qp_IQ_Question", ["qn_category"])
        safe_add_index("qp_IQ_Question", ["qn_type"])
        safe_add_index("qp_IQ_Question", ["qn_demographic"])
        safe_add_index("qp_IQ_Question", ["qn_status"])

        # 6. qp_IQ_SurveyRecipient (Destinatarios y accesos)
        safe_add_index("qp_IQ_SurveyRecipient", ["sr_survey"])
        safe_add_index("qp_IQ_SurveyRecipient", ["sr_contact"])
        safe_add_index("qp_IQ_SurveyRecipient", ["sr_status"])
        safe_add_index("qp_IQ_SurveyRecipient", ["sr_evaluating_to"])
        safe_add_index("qp_IQ_SurveyRecipient", ["sr_token"]) # Crítico para el acceso web rápido por URL
        safe_add_index("qp_IQ_SurveyRecipient", ["sr_survey", "sr_contact"]) # Índice compuesto para validar cruces

        # 7. qp_IQ_Template (Plantillas)
        safe_add_index("qp_IQ_Template", ["custom_company"])
        safe_add_index("qp_IQ_Template", ["tp_category"])
        safe_add_index("qp_IQ_Template", ["tp_status"])

        # Confirmar todos los cambios en MariaDB
        frappe.db.commit()
        frappe.logger().info("Todos los índices de Liseniq fueron aplicados correctamente.")

    except Exception as e:
        frappe.log_error(f"Error crítico aplicando índices en Liseniq: {str(e)}")
        raise