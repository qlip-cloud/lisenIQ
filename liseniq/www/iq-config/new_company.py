import frappe
import json
from frappe import _
from liseniq.utils.login_util import global_website_context

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Cliente aún no ha sido registrado. Por favor comunique al Administrador."), frappe.PermissionError)

    # Validación de Rol: consultant_user para evitar acceso por URL
    consultant_role = frappe.db.get_value("qp_IQ_PortalRole", {"pr_mnemonico": "consultant_user"}, "name")
    user_contact_role = frappe.db.get_value("Contact", {"user": frappe.session.user}, "custom_rol_aiq")

    if not consultant_role or user_contact_role != consultant_role:
        frappe.local.flags.redirect_location = '/iq-home'
        raise frappe.Redirect

    try:
        context = global_website_context(context)
    except Exception:
        pass  # Manejo por si global_website_context no existe o falla

    # Configuración base de la página
    context.page_title = _("Crear Compañía")
    context.no_breadcrumbs = True
    context.is_navbar_custom = True
    context.no_cache = 1

    # Cargar datos para llenar los dropdowns del formulario
    try:
        # Filtro de países solo LATAM
        latam_countries_list = [
            "Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Costa Rica",
            "Cuba", "Dominican Republic", "Ecuador", "El Salvador", "Guatemala",
            "Honduras", "Mexico", "Nicaragua", "Panama", "Paraguay", "Peru",
            "Puerto Rico", "Uruguay", "Venezuela, Bolivarian Republic of"
        ]
        context.countries = frappe.get_all(
            "Country", 
            filters={"name": ("in", latam_countries_list)}, 
            fields=["name"], 
            order_by="name asc"
        )
    except frappe.DoesNotExistError:
        context.countries = []

    try:
        context.sectors = frappe.get_all("qp_IQ_Sector", fields=["name"], order_by="name asc")
    except frappe.DoesNotExistError:
        context.sectors = []

    try:
        # Recuperamos nuevamente los tipos de documento para la vista
        context.doc_types = frappe.get_all(
            "qp_IQ_DocumentType", 
            fields=["name", "dt_name"], 
            order_by="dt_name asc"
        )
    except frappe.DoesNotExistError:
        context.doc_types = []

    return context

@frappe.whitelist()
def create_new_company(data):
    """
    Recibe el string JSON desde el Frontend y crea el registro de la compañía,
    los clientes y los contactos.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("No tienes permisos suficientes para realizar esta acción."), frappe.PermissionError)

    try:
        payload = json.loads(data)

        # Validación obligatoria
        if not payload.get("co_name"):
            frappe.throw(_("El nombre de la compañía es obligatorio."))

        # 1. Crear nuevo DocType de Compañía
        doc = frappe.new_doc("qp_IQ_Company")

        for field, value in payload.items():
            if field not in ["co_logo_data", "co_logo_name", "co_accept_terms", "co_accept_privacy_policy"] and value is not None and value != "":
                if doc.meta.has_field(field):
                    df = doc.meta.get_field(field)
                    
                    # Validación dinámica de longitud para campos de texto
                    if isinstance(value, str):
                        max_chars = df.length or 0
                        if not max_chars:
                            if df.fieldtype == "Data": max_chars = 140
                            elif df.fieldtype == "Small Text": max_chars = 255
                            elif df.fieldtype == "Text": max_chars = 65535
                                
                        if max_chars and len(value) > max_chars:
                            frappe.throw(_("El campo '{0}' excede el límite permitido de {1} caracteres.").format(df.label, max_chars))

                    doc.set(field, value)

        doc.insert(ignore_permissions=True)

        # Procesar y guardar el logo si fue cargado
        if payload.get("co_logo_data") and payload.get("co_logo_name"):
            try:
                from frappe.core.doctype.file.file import save_file
                file_data = payload.get("co_logo_data")
                if "," in file_data:
                    file_data = file_data.split(",")[1]
                
                file_doc = save_file(
                    fname=payload.get("co_logo_name"),
                    content=file_data,
                    dt="qp_IQ_Company",
                    dn=doc.name,
                    folder="Home/Attachments",
                    decode_base64=True,
                    is_private=0
                )
                doc.db_set("co_logo", file_doc.file_url)
            except Exception as e:
                frappe.log_error(f"Error guardando logo de compañia: {str(e)}", "Frontend Company Creation")

        # Asignar compañía al Contact del usuario creador (Consultor)
        try:
            contact_name = frappe.db.get_value("Contact", {"user": frappe.session.user}, "name")
            if contact_name:
                contact_doc = frappe.get_doc("Contact", contact_name)
                
                existe = any(row.cc_company == doc.name for row in contact_doc.get("custom_iq_companies", []))
                
                if not existe:
                    es_principal = 1 if len(contact_doc.get("custom_iq_companies", [])) == 0 else 0
                    contact_doc.append("custom_iq_companies", {
                        "cc_company": doc.name,
                        "cc_company_name": payload.get("co_name"),
                        "cc_is_default": es_principal
                    })
                    contact_doc.save(ignore_permissions=True)
        except Exception as ce:
            frappe.log_error(f"Error al vincular compañía al Creador: {str(ce)}", "Frontend Contact Update")

        # Crear el Usuario (si no existe) y el Contacto para el Administrador de la Compañía
        try:
            admin_email = payload.get("co_admin_email")
            if admin_email:
                admin_name = payload.get("co_admin_name", "").strip()
                if " " in admin_name:
                    first_name, last_name = admin_name.split(" ", 1)
                else:
                    first_name = admin_name
                    last_name = ""

                # Crear Usuario primero
                if not frappe.db.exists("User", admin_email):
                    new_user = frappe.new_doc("User")
                    new_user.email = admin_email
                    new_user.first_name = first_name
                    new_user.last_name = last_name
                    new_user.send_welcome_email = 0
                    new_user.insert(ignore_permissions=True)
                    
                    # Asignar rol Customer
                    new_user.append("roles", {
                        "role": "Customer"
                    })
                    new_user.save(ignore_permissions=True)

                # Crear o Actualizar Contacto
                contact_exists = frappe.db.exists("Contact", {"email_id": admin_email})

                if not contact_exists:
                    new_admin = frappe.new_doc("Contact")
                    new_admin.first_name = first_name
                    new_admin.last_name = last_name
                    new_admin.email_id = admin_email
                    new_admin.user = admin_email
                    new_admin.custom_company = doc.name
                    
                    # Agregar a la tabla hija estándar de correos
                    new_admin.append("email_ids", {
                        "email_id": admin_email,
                        "is_primary": 1
                    })
                    
                    # Opcional: Agregar el teléfono si fue proporcionado
                    if payload.get("co_admin_phone"):
                        new_admin.append("phone_nos", {
                            "phone": payload.get("co_admin_phone"),
                            "is_primary_phone": 1,
                            "is_primary_mobile_no": 1
                        })

                    # Agregar también a la tabla custom_iq_companies como principal
                    new_admin.append("custom_iq_companies", {
                        "cc_company": doc.name,
                        "cc_company_name": payload.get("co_name"),
                        "cc_is_default": 1
                    })
                        
                    new_admin.insert(ignore_permissions=True)
                else:
                    # Si el administrador ya existe, actualizamos su información de compañía
                    existing_admin_name = frappe.db.get_value("Contact", {"email_id": admin_email}, "name")
                    existing_admin = frappe.get_doc("Contact", existing_admin_name)
                    
                    # Actualizar custom_company principal
                    existing_admin.custom_company = doc.name
                    
                    # Asegurar que el usuario esté enlazado si no lo estaba
                    if not existing_admin.user:
                        existing_admin.user = admin_email
                    
                    # Agregar a su tabla custom_iq_companies si no la tiene
                    existe_admin = any(row.cc_company == doc.name for row in existing_admin.get("custom_iq_companies", []))
                    if not existe_admin:
                        es_principal_admin = 1 if len(existing_admin.get("custom_iq_companies", [])) == 0 else 0
                        existing_admin.append("custom_iq_companies", {
                            "cc_company": doc.name,
                            "cc_company_name": payload.get("co_name"),
                            "cc_is_default": es_principal_admin
                        })
                    
                    existing_admin.save(ignore_permissions=True)
        except Exception as ce:
            frappe.log_error(f"Error al crear Usuario y Contact del Administrador: {str(ce)}", "Frontend Admin Contact Creation")

        return {
            "status": "success",
            "message": "Compañía, Cliente y Contactos creados de manera exitosa.",
            "company_name": doc.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error en create_new_company (Frontend)")
        frappe.throw(f"No fue posible guardar la compañía: {str(e)}")