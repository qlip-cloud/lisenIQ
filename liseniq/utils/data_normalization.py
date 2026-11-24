import frappe

@frappe.whitelist()
def obtener_reporte_normalizacion():
    """Genera un reporte de las inconsistencias y duplicados a normalizar."""
    reporte = {
        "tipos_incorrectos": {"dimensiones": 0, "temas": 0},
        "duplicados_a_fusionar": {"Dimension": [], "Tema": []}
    }

    # 1. Identificar registros con dt_object_type = 'Pregunta'
    dimensiones_erroneas = frappe.db.sql("""
        SELECT COUNT(DISTINCT d.name) as total
        FROM `tabqp_IQ_DemographicType` d
        JOIN `tabqp_IQ_Question` q ON q.qn_demographic = d.name
        WHERE d.dt_object_type = 'Pregunta'
    """, as_dict=True)[0].total

    temas_erroneos = frappe.db.sql("""
        SELECT COUNT(DISTINCT d.name) as total
        FROM `tabqp_IQ_DemographicType` d
        JOIN `tabqp_IQ_Question` q ON q.qp_topic = d.name
        WHERE d.dt_object_type = 'Pregunta'
    """, as_dict=True)[0].total

    reporte["tipos_incorrectos"]["dimensiones"] = dimensiones_erroneas
    reporte["tipos_incorrectos"]["temas"] = temas_erroneos

    # 2. Identificar duplicados simulando la conversión a MAYÚSCULAS
    duplicados = frappe.db.sql("""
        SELECT UPPER(dt_title) as titulo_mayus, dt_object_type, COUNT(name) as cantidad
        FROM `tabqp_IQ_DemographicType`
        WHERE dt_object_type IN ('Tema', 'Dimension')
        GROUP BY UPPER(dt_title), dt_object_type
        HAVING cantidad > 1
    """, as_dict=True)

    for dup in duplicados:
        reporte["duplicados_a_fusionar"][dup.dt_object_type].append({
            "titulo": dup.titulo_mayus,
            "registros_afectados": dup.cantidad
        })

    return reporte


@frappe.whitelist()
def ejecutar_normalizacion():
    """Ejecuta la actualización de tipos, estandariza a mayúsculas y consolida duplicados."""
    
    # PASO 1: Corregir dt_object_type masivamente mediante SQL
    frappe.db.sql("""
        UPDATE `tabqp_IQ_DemographicType` d
        JOIN `tabqp_IQ_Question` q ON q.qn_demographic = d.name
        SET d.dt_object_type = 'Dimension'
        WHERE d.dt_object_type = 'Pregunta'
    """)
    
    frappe.db.sql("""
        UPDATE `tabqp_IQ_DemographicType` d
        JOIN `tabqp_IQ_Question` q ON q.qp_topic = d.name
        SET d.dt_object_type = 'Tema'
        WHERE d.dt_object_type = 'Pregunta'
    """)

    # PASO 2: Estandarizar a MAYÚSCULAS todos los enunciados de Temas y Dimensiones
    frappe.db.sql("""
        UPDATE `tabqp_IQ_DemographicType`
        SET dt_title = UPPER(dt_title)
        WHERE dt_object_type IN ('Tema', 'Dimension')
    """)

    # PASO 3: Agrupar por dt_title (ya estandarizado) y dt_object_type para eliminar duplicados
    duplicados = frappe.db.sql("""
        SELECT dt_title, dt_object_type, COUNT(name) as cantidad
        FROM `tabqp_IQ_DemographicType`
        WHERE dt_object_type IN ('Tema', 'Dimension')
        GROUP BY dt_title, dt_object_type
        HAVING cantidad > 1
    """, as_dict=True)

    for dup in duplicados:
        titulo = dup.dt_title
        tipo_objeto = dup.dt_object_type

        # Obtener los IDs de los registros duplicados
        registros_viejos = frappe.get_all('qp_IQ_DemographicType', 
                                          filters={'dt_title': titulo, 'dt_object_type': tipo_objeto}, 
                                          pluck='name')

        if not registros_viejos:
            continue

        # Crear el nuevo registro maestro dejando dt_creator_company vacío
        nuevo_maestro = frappe.get_doc({
            'doctype': 'qp_IQ_DemographicType',
            'dt_title': titulo,
            'dt_object_type': tipo_objeto,
            'dt_creator_company': None 
        })
        nuevo_maestro.insert(ignore_permissions=True)

        # Actualizar las referencias en las preguntas masivamente
        if tipo_objeto == 'Dimension':
            frappe.db.sql("""
                UPDATE `tabqp_IQ_Question`
                SET qn_demographic = %s
                WHERE qn_demographic IN %s
            """, (nuevo_maestro.name, tuple(registros_viejos)))
        else:
            frappe.db.sql("""
                UPDATE `tabqp_IQ_Question`
                SET qp_topic = %s
                WHERE qp_topic IN %s
            """, (nuevo_maestro.name, tuple(registros_viejos)))

        # Eliminar los registros antiguos
        for viejo_id in registros_viejos:
            frappe.delete_doc('qp_IQ_DemographicType', viejo_id, force=1, ignore_missing=True)

    frappe.db.commit()
    return {"status": "success", "message": "Normalización completada. Enunciados convertidos a mayúsculas y duplicados consolidados."}