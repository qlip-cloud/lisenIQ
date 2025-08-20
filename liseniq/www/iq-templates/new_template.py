# -*- coding: utf-8 -*-
# Copyright (c) 2024, Mentum Group. All rights reserved.
# For license information, please see license.txt

import frappe

def get_context(context):
    """
    Prepara y pasa el contexto a la plantilla
    para la página de creación de nuevas plantillas.
    """
    context.page_title = "Crear Plantilla"

    # Asegurarse de que el usuario está logueado
    if frappe.session.user == "Guest":
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/login"
        return

    # Obtener la compañía del usuario y pasarla al contexto
    try:
        user_company = frappe.db.get_value("User", frappe.session.user, "custom_company")
        if not user_company:
            frappe.throw("El usuario actual no tiene una compañía asignada. Por favor, contacte al administrador.")
        context.user_company = user_company
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error obteniendo la compañía del usuario")
        frappe.throw(str(e))


    # Cargar categorías y tipos de preguntas
    try:
        question_categories = frappe.get_all(
            "qp_IQ_QuestionCategory",
            fields=["name", "qnc_category"],
            order_by="qnc_category"
        )
        context.question_categories = question_categories
    except frappe.DoesNotExistError:
        context.question_categories = []

    try:
        question_types = frappe.get_all(
            "qp_IQ_QuestionType",
            fields=["name", "qnt_type_name"],
            order_by="qnt_type_name"
        )
        context.question_types = question_types
    except frappe.DoesNotExistError:
        context.question_types = []


    context.update({
        "is_navbar_custom": True,
        "no_cache": 1
    })
            
    return context
