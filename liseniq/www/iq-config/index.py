import frappe
from frappe import _
from liseniq.utils.login_util import global_website_context

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Debes iniciar sesión para acceder a esta página."), frappe.PermissionError)

    # Validación de Rol
    consultant_role = frappe.db.get_value("qp_IQ_PortalRole", {"pr_mnemonico": "consultant_user"}, "name")
    user_contact_role = frappe.db.get_value("Contact", {"user": frappe.session.user}, "custom_rol_aiq")

    if not consultant_role or user_contact_role != consultant_role:
        frappe.local.flags.redirect_location = '/iq-home'
        raise frappe.Redirect

    try:
        context = global_website_context(context)
    except Exception:
        pass

    # Configuración base de la página
    context.page_title = _("Configuración")
    context.no_breadcrumbs = True
    context.is_navbar_custom = True
    context.no_cache = 1

    return context