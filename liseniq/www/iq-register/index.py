import frappe
from frappe import _


def get_context(context):
    context.page_title = "Registro"
    context.no_breadcrumbs = True
    context.is_navbar_custom = True
    context.no_cache = 1

    return context