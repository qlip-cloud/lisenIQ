# -*- coding: utf-8 -*-
"""
Patch idempotente para crear y sincronizar los catálogos de Planes de Acción
usando los DocTypes existentes `qp_IQ_Catalog` y `qp_IQ_CatalogOptions`
en cualquier ambiente (dev, qa, prod).

Uso recomendado:
1. Registrar en `liseniq/patches.txt`:
   liseniq.patches.v13_0.setup_action_plan_catalogs
2. Ejecutar `bench --site <sitio> migrate`
"""

import frappe

CATALOG_DEFINITIONS = [
    {
        "ca_mnemonico": "AP_STATUS",
        "ca_catalog_name": "Estados de Plan de Acción",
        "ca_description": "Estados operativos del ciclo de vida de un plan de mejora.",
        "options": [
            {"co_label": "Borrador", "co_sort_order": 1, "co_description": "Plan recién creado pendiente de iniciar."},
            {"co_label": "En ejecución", "co_sort_order": 2, "co_description": "Plan activo con acciones en curso."},
            {"co_label": "Finalizado", "co_sort_order": 3, "co_description": "Plan completado."},
            {"co_label": "Cancelado", "co_sort_order": 4, "co_description": "Plan cancelado."},
        ],
    },
    {
        "ca_mnemonico": "AP_GOAL_STATUS",
        "ca_catalog_name": "Estados de Meta de Plan de Acción",
        "ca_description": "Estados de evaluación de impacto frente a la meta definida.",
        "options": [
            {"co_label": "Pendiente de evaluación", "co_sort_order": 1, "co_description": "Aún no se ha comparado con una medición posterior."},
            {"co_label": "Meta alcanzada", "co_sort_order": 2, "co_description": "El puntaje posterior alcanzó o superó la meta."},
            {"co_label": "Meta parcialmente alcanzada", "co_sort_order": 3, "co_description": "Hubo mejora respecto al puntaje inicial sin alcanzar la meta."},
            {"co_label": "Meta no alcanzada", "co_sort_order": 4, "co_description": "No hubo mejora frente al puntaje inicial."},
        ],
    },
    {
        "ca_mnemonico": "AP_PRIORITY",
        "ca_catalog_name": "Prioridades de Plan de Acción",
        "ca_description": "Niveles de prioridad para planes de mejora.",
        "options": [
            {"co_label": "Baja", "co_sort_order": 1, "co_description": "Prioridad baja."},
            {"co_label": "Media", "co_sort_order": 2, "co_description": "Prioridad media."},
            {"co_label": "Alta", "co_sort_order": 3, "co_description": "Prioridad alta."},
            {"co_label": "Crítica", "co_sort_order": 4, "co_description": "Prioridad crítica."},
        ],
    },
    {
        "ca_mnemonico": "AP_SCOPE_TYPE",
        "ca_catalog_name": "Tipos de Alcance de Plan de Acción",
        "ca_description": "Niveles de granularidad sobre los que aplica un plan de mejora.",
        "options": [
            {"co_label": "Medición", "co_sort_order": 1, "co_description": "Alcance general de toda la medición."},
            {"co_label": "Dimensión", "co_sort_order": 2, "co_description": "Alcance enfocado en una dimensión."},
            {"co_label": "Tema", "co_sort_order": 3, "co_description": "Alcance enfocado en un tema."},
            {"co_label": "Pregunta", "co_sort_order": 4, "co_description": "Alcance enfocado en una pregunta específica."},
        ],
    },
    {
        "ca_mnemonico": "AP_TASK_STATUS",
        "ca_catalog_name": "Estados de Acción del Plan",
        "ca_description": "Estados operativos de las tareas o acciones dentro de un plan.",
        "options": [
            {"co_label": "Pendiente", "co_sort_order": 1, "co_description": "Acción aún no iniciada."},
            {"co_label": "En progreso", "co_sort_order": 2, "co_description": "Acción actualmente en ejecución."},
            {"co_label": "Finalizada", "co_sort_order": 3, "co_description": "Acción completada."},
        ],
    },
]


def execute():
    if not frappe.db.exists("DocType", "qp_IQ_Catalog") or not frappe.db.exists(
        "DocType", "qp_IQ_CatalogOptions"
    ):
        return

    for cat_def in CATALOG_DEFINITIONS:
        mnemonic = cat_def["ca_mnemonico"]
        catalog_name = frappe.db.get_value("qp_IQ_Catalog", {"ca_mnemonico": mnemonic}, "name")

        if not catalog_name:
            cat_doc = frappe.get_doc(
                {
                    "doctype": "qp_IQ_Catalog",
                    "ca_catalog_name": cat_def["ca_catalog_name"],
                    "ca_mnemonico": mnemonic,
                    "ca_description": cat_def["ca_description"],
                }
            )
            cat_doc.insert(ignore_permissions=True)
            catalog_name = cat_doc.name
        else:
            frappe.db.set_value(
                "qp_IQ_Catalog",
                catalog_name,
                {
                    "ca_catalog_name": cat_def["ca_catalog_name"],
                    "ca_description": cat_def["ca_description"],
                },
                update_modified=False,
            )

        for opt in cat_def["options"]:
            existing_opt = frappe.db.get_value(
                "qp_IQ_CatalogOptions",
                {"co_catalog": catalog_name, "co_label": opt["co_label"]},
                "name",
            )
            if existing_opt:
                frappe.db.set_value(
                    "qp_IQ_CatalogOptions",
                    existing_opt,
                    {
                        "co_sort_order": opt["co_sort_order"],
                        "co_is_active": 1,
                        "co_description": opt["co_description"],
                    },
                    update_modified=False,
                )
            else:
                opt_doc = frappe.get_doc(
                    {
                        "doctype": "qp_IQ_CatalogOptions",
                        "co_catalog": catalog_name,
                        "co_label": opt["co_label"],
                        "co_sort_order": opt["co_sort_order"],
                        "co_is_active": 1,
                        "co_description": opt["co_description"],
                    }
                )
                opt_doc.insert(ignore_permissions=True)

    frappe.db.commit()