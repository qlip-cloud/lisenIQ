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

@frappe.whitelist()
def get_email_accounts():
    """
    Obtiene los correos electrónicos configurados para la empresa activa 
    del usuario en sesión o el correo configurado por defecto.
    """
    if frappe.session.user == "Guest":
        return {"status": "error", "message": "No autorizado."}

    user = frappe.session.user
    
    # Obtener la compañía activa del usuario (Contact)
    contact_name = frappe.db.get_value("Contact", {"user": user}, "name")
    if not contact_name:
        return {"status": "error", "message": "El usuario no tiene un contacto asociado."}
        
    contact_doc = frappe.get_doc("Contact", contact_name)
    default_company = None
    
    # Evaluar tabla hija de compañias del contacto buscando la default
    for row in contact_doc.get("custom_iq_companies", []):
        if row.cc_is_default:
            default_company = row.cc_company
            break
            
    # Fallback a la primera compañía si no hay ninguna marcada como default
    if not default_company:
        if contact_doc.get("custom_iq_companies"):
            default_company = contact_doc.custom_iq_companies[0].cc_company
        else:
            return {"status": "error", "message": "El usuario no pertenece a ninguna compañía registrada."}
            
    # Obtener el correo seleccionado actualmente
    company_doc = frappe.get_doc("qp_IQ_Company", default_company)
    current_email = company_doc.co_notification_email
    
    # Consultar si existen Email Account asociados a la compañía de la sesión
    emails_linked = frappe.db.sql("""
        SELECT parent FROM `tabqp_IQ_EmailAccountCompany`
        WHERE company = %s AND parenttype = 'Email Account'
    """, (default_company,), as_dict=True)
    
    email_accounts_dict = {}
    
    # Traer siempre los que tengan default_outgoing = 1
    default_email_accounts = frappe.get_all("Email Account",
        filters={"default_outgoing": 1},
        fields=["name", "email_account_name", "email_id"]
    )
    for acc in default_email_accounts:
        email_accounts_dict[acc["name"]] = acc
    
    if emails_linked:
        # Hay correos enlazados a la empresa, obtener sus detalles
        email_names = [e.parent for e in emails_linked]
        company_email_accounts = frappe.get_all("Email Account", 
            filters={"name": ("in", email_names)},
            fields=["name", "email_account_name", "email_id"]
        )
        for acc in company_email_accounts:
            email_accounts_dict[acc["name"]] = acc

    # Convertir a lista y ordenar por nombre
    email_accounts = list(email_accounts_dict.values())
    email_accounts.sort(key=lambda x: x.get("email_account_name") or "")
        
    return {
        "status": "success",
        "data": email_accounts,
        "current": current_email,
        "company": default_company
    }

@frappe.whitelist()
def save_notification_email(company, email_account):
    """
    Actualiza el campo co_notification_email del doctype qp_IQ_Company.
    """
    if frappe.session.user == "Guest":
        return {"status": "error", "message": "No autorizado"}
        
    if not company:
        return {"status": "error", "message": "No se determinó la compañía a actualizar."}
        
    if not email_account:
        return {"status": "error", "message": "No ha seleccionado un correo válido."}
        
    try:
        # Validamos que la compañía exista
        if not frappe.db.exists("qp_IQ_Company", company):
            return {"status": "error", "message": "La compañía no existe."}
            
        # Actualizamos el valor dinámicamente ignorando permisos de listview por si el rol lo limitara
        frappe.db.set_value("qp_IQ_Company", company, "co_notification_email", email_account)
        
        return {"status": "success", "message": "La selección del correo ha sido guardada exitosamente."}
        
    except Exception as e:
        frappe.log_error(f"Error actualizando notificación: {str(e)}", "Configuración Notificaciones")
        return {"status": "error", "message": f"Error del sistema: {str(e)}"}