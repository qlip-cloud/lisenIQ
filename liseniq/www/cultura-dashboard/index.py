# listenaiq/www/cultura_dashboard.py
#
# Controlador de la Website Page /cultura-dashboard.
#
# IMPORTANTE (ver Gotcha de nomenclatura de Frappe): el archivo HTML
# conserva el guion (www/cultura-dashboard.html) porque así se ve en la
# URL, pero este controlador Python usa guion bajo (www/cultura_dashboard.py)
# porque Frappe lo importa como módulo de Python y los guiones no son
# válidos en nombres de módulo. Si los renombras de forma distinta,
# get_context() deja de ejecutarse silenciosamente y verás errores
# DebugUndefined en el HTML.
#
# Acceso: requiere sesión iniciada (confirmado con el usuario). No se
# marca allow_guest=True. Si un usuario anónimo visita la URL, Frappe lo
# redirige automáticamente a /login?redirect-to=/cultura-dashboard...

import frappe

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        # Redirige a /login y, tras iniciar sesión, Frappe debería volver a esta
        # misma URL (con ?survey=... incluido). Este es el patrón estándar de
        # Frappe para páginas www/ que exigen sesión — pero verifícalo en tu
        # instancia v13 exacta; si no redirige como esperas, la alternativa
        # más simple y 100% segura es reemplazar este bloque por:
        #     frappe.throw("Debes iniciar sesión para ver este dashboard.",
        #                  frappe.PermissionError)
        # que sí está garantizado: bloquea a Guest y muestra una página de error 403.
        frappe.local.flags.redirect_location = (
            "/login?redirect-to=" + frappe.utils.quote(frappe.request.path + "?" + frappe.request.query_string.decode())
        )
        raise frappe.Redirect

    survey = frappe.form_dict.get("survey")
    if not survey:
        frappe.throw("Falta el parámetro 'survey' en la URL", frappe.ValidationError)
    if not frappe.db.exists("Survey", survey):
        frappe.throw(f"Encuesta no encontrada: {survey}", frappe.DoesNotExistError)

    context.survey = survey
    context.title = f"Cultura Organizacional — {survey}"
    context.no_cache = 1
    context.no_breadcrumbs = True
    context.is_navbar_custom = True
    context.show_summary_section = False
        
    # No pasamos los datos aquí: el HTML los pide vía fetch() al cargar,
    # para no incrustar un payload pesado (y potencialmente ya obsoleto
    # si el usuario deja la pestaña abierta) directamente en el HTML.
