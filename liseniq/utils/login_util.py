import frappe
from frappe import _


# Función para obtener el nombre de la compañía del usuario y cachearlo en sesión
@frappe.whitelist()
def get_user_company_name(user=None):

	session_key = "liseniq_company_name"
	user = user or frappe.session.user
	if not user or user == "Guest":
		return ""

	cached_name = (getattr(frappe.session, "data", {}) or {}).get(session_key)
	if cached_name:
		return cached_name

	contact_info = frappe.db.get_value(
		"Contact",
		{"user": user, "custom_is_liseniq_contact": 0},
		["custom_company"],
		as_dict=True,
	)
	if contact_info and contact_info.custom_company:
		company_name = frappe.db.get_value("qp_IQ_Company", contact_info.custom_company, "co_name") or ""
	else:
		company_name = ""

	try:
		session_obj = getattr(frappe.local, "session_obj", None)
		if session_obj:
			session_obj.data[session_key] = company_name
			if hasattr(session_obj, "update"):
				session_obj.update()
		else:
			if hasattr(frappe, "session") and hasattr(frappe.session, "data"):
				frappe.session.data[session_key] = company_name
	except Exception:
		pass

	return company_name

def set_company_name_on_session_creation(login_manager):
	try:
		user = getattr(login_manager, "user", None) or frappe.session.user
		if user and user != "Guest":
			get_user_company_name(user=user)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "liseniq: set_company_name_on_session_creation")

# Función para inyectar contexto global en páginas del portal
# Valida que el usuario no sea Guest, que tenga una compañía asignada y que sea un contacto administrativo (custom_is_liseniq_contact=0).
def global_website_context(context):

    if context is None:
        context = frappe._dict()

    user = frappe.session.user
    
    # Valores por defecto
    context.has_portal_access = False
    context.access_error_message = ""
    context.liseniq_company_name = ""

    # Validación de Invitado
    if user == "Guest":
        context.access_error_message = _("Debe iniciar sesión para acceder.")
        return context

    # Obtener datos del Contacto
    contact = frappe.db.get_value(
        "Contact", 
        {"user": user}, 
        ["name", "custom_company", "custom_is_liseniq_contact"], 
        as_dict=True
    )
    
    if not contact:
        context.access_error_message = _("El usuario no se encuentra registrado o no tiene permisos de acceso (Contacto no encontrado).")
        frappe.log_error(title="Portal Access Fail", message=f"User {user} has no Contact linked.")
        return context

    if not contact.custom_company:
        context.access_error_message = _("El usuario no tiene una compañía asignada. Contacte al administrador.")
        return context

    if contact.custom_is_liseniq_contact:
        context.access_error_message = _("Su usuario no tiene perfil administrativo para acceder a este portal.")
        return context

    context.has_portal_access = True
    context.liseniq_company_name = contact.custom_company
    
    return context

def check_access_and_redirect():
    context = frappe._dict()
    global_website_context(context)
    if not context.has_portal_access:
        frappe.throw(context.access_error_message, frappe.PermissionError)