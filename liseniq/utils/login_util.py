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
    context.first_login = False

    # Validación de Invitado
    if user == "Guest":
        context.access_error_message = _("Debe iniciar sesión para acceder.")
        # frappe.log_error(title="Acceso al portal fallido", message="Usuario Guest intentó acceder al portal.")
        return context

    # Obtener datos del Contacto
    contact = frappe.db.get_value(
        "Contact", 
        {"user": user}, 
        ["name", "custom_company", "custom_is_liseniq_contact", "custom_first_login"], 
        as_dict=True
    )
    
    if not contact:
        context.access_error_message = _("El usuario no se encuentra registrado o no tiene permisos de acceso (Contacto no encontrado).")
        frappe.log_error(title="Acceso al portal fallido", message=f"Usuario {user} sin contacto asociado.")
        return context

    if not contact.custom_company:
        context.access_error_message = _("El usuario no tiene una compañía asignada. Contacte al administrador.")
        frappe.log_error(title="Acceso al portal fallido", message=f"Usuario {user} sin compañía asignada.")
        return context

    if contact.custom_is_liseniq_contact:
        context.access_error_message = _("Su usuario no tiene perfil administrativo para acceder a este portal.")
        frappe.log_error(title="Acceso al portal fallido", message=f"Usuario {user} sin perfil administrativo.")
        return context

    context.has_portal_access = True
    context.liseniq_company_name = contact.custom_company
		
    context.first_login = contact.custom_first_login
    
    return context

def check_access_and_redirect():
    context = frappe._dict()
    global_website_context(context)
    if not context.has_portal_access:
        frappe.throw(context.access_error_message, frappe.PermissionError)

@frappe.whitelist()
def set_first_login_false():
    user = frappe.session.user
    if user and user != "Guest":
        contact_name = frappe.db.get_value("Contact", {"user": user}, "name")
        if contact_name:
            try:
                contact_doc = frappe.get_doc("Contact", contact_name)
                contact_doc.custom_first_login = False
                contact_doc.save()
                frappe.db.commit()
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), "liseniq: set_first_login_false")
                frappe.throw(_("Error al actualizar el estado de primer inicio: {0}").format(str(e)))