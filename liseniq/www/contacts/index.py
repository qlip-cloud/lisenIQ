import frappe
import json
import random
import re
from frappe import _
from liseniq.utils.login_util import global_website_context


def get_context(context):

    if frappe.session.user == "Guest":
        frappe.throw(_("Cliente aún no ha sido registrado. Por favor comunique al Administrador."), frappe.PermissionError)
    
    context = global_website_context(context)

    # Configuración base de la página
    context.page_title = _("Contactos")
    context.no_cache = 1
    context.no_breadcrumbs = True
    context.is_navbar_custom = True

    try:
        user_doc = frappe.get_doc("User", frappe.session.user)
        context.user = user_doc

        contact_info = frappe.db.get_value("Contact", {"user": frappe.session.user, "custom_is_liseniq_contact": 0}, ["name", "custom_company"], as_dict=True)

        if not contact_info or not contact_info.custom_company:
            frappe.throw(_("El usuario actual no tiene una compañía asignada. Por favor, contacte al administrador."), title=_("Error de Configuración"))

        user_company = contact_info.custom_company
        user_contact_name = contact_info.name

        context.user_company = frappe.get_doc("qp_IQ_Company", user_company)
        csrf_token = frappe.sessions.get_csrf_token()

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error en get_context de Contactos")
        if isinstance(e, frappe.exceptions.ValidationError) or isinstance(e, frappe.exceptions.PermissionError):
             frappe.throw(str(e))
        else:
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = "/login"
        return

    latam_countries_list = [
        "Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Costa Rica",
        "Cuba", "Dominican Republic", "Ecuador", "El Salvador", "Guatemala",
        "Honduras", "Mexico", "Nicaragua", "Panama", "Paraguay", "Peru",
        "Puerto Rico", "Uruguay", "Venezuela, Bolivarian Republic of"
    ]

    context.education_levels = frappe.get_all('qp_IQ_AcademicLevel', fields=['name', 'al_title'], order_by='al_title asc')
    context.document_types = frappe.get_all('qp_IQ_DocumentType', fields=['name', 'dt_name'], order_by='dt_name asc')
    context.gender = frappe.get_all('Gender', fields=['gender'], order_by='gender asc')
    context.language = frappe.get_all('qp_IQ_Language', fields=['name', 'la_name'], order_by='la_name asc')
    
    context.latam_countries = frappe.get_all(
        'Country',
        fields=['country_name'],
        filters={'country_name': ('in', latam_countries_list)},
        order_by='country_name asc',
        limit_page_length=30
    )

    # Filtrar tipos demográficos por la compañía del usuario
    demographic_types_list = frappe.get_all('qp_IQ_DemographicType', filters={'dt_object_type': 'Contacto', 'dt_creator_company': user_company}, fields=['name', 'dt_title'], order_by='dt_title asc')
    context.demographic_types_json = frappe.as_json(demographic_types_list or [])
    context.default_country = "Colombia"
    context.default_doctype = "822f13806f"
    context.default_language = "es-CO"

    contacts_from_db = frappe.get_all(
        'Contact',
        filters={
            'custom_company': user_company,
            'name': ['!=', user_contact_name],
            'custom_is_liseniq_contact': 1,
            'custom_is_deleted': 0
        },
        fields=[
            'name', 'custom_document_number', 'first_name', 'last_name',
            'custom_country', 'custom_language', 'custom_status'
        ],
        order_by='creation desc'
    )

    contact_names = [c.name for c in contacts_from_db]
    email_map = {}
    if contact_names:
        primary_emails = frappe.get_all(
            "Contact Email",
            filters={"parent": ["in", contact_names], "is_primary": 1, "parenttype": "Contact"},
            fields=["parent", "email_id"]
        )
        email_map = {email.parent: email.email_id for email in primary_emails}

    processed_contacts = []
    for contact in contacts_from_db:
        processed_contacts.append({
            'name': contact.get('name'),
            'dni': contact.get('custom_document_number', ''),
            'first_name': contact.get('first_name', ''),
            'last_name': contact.get('last_name', ''),
            'country': contact.get('custom_country', ''),
            'email': email_map.get(contact.name, ''),
            'language': contact.get('custom_language', ''),
            'status': contact.get('custom_status', 'Inactivo')
        })
    context.contacts = processed_contacts
    context.contacts_json = frappe.as_json(processed_contacts or [])

    context.update({
        "is_navbar_custom": True,
        "no_cache": 1,
        "csrf_token": csrf_token,
    })
    return context

@frappe.whitelist()
def get_contact_details(contact_name):
    if not frappe.db.exists("Contact", contact_name):
        frappe.throw(_("Contacto no encontrado"))

    contact = frappe.get_doc("Contact", contact_name)
    
    user_contact_info = frappe.db.get_value("Contact", {"user": frappe.session.user}, "custom_company")
    if not user_contact_info:
        frappe.throw(_("No se pudo determinar la compañía del usuario."))
    user_company = user_contact_info

    if contact.custom_company != user_company:
        frappe.throw(_("No tienes permiso para ver este contacto"))

    primary_email = frappe.db.get_value("Contact Email", {"parent": contact_name, "is_primary": 1}, "email_id")

    demographics = frappe.get_all(
        "qp_IQ_ContactAdditionalDetail",
        filters={"parent": contact_name},
        fields=["cad_demographic_type", "cad_value"]
    )
    
    processed_demographics = []
    for demo in demographics:
        dt_title = frappe.db.get_value("qp_IQ_DemographicType", demo.cad_demographic_type, "dt_title")
        processed_demographics.append({"type": dt_title, "value": demo.cad_value})

    return {
        "name": contact.name,
        "firstName": contact.first_name,
        "lastName": contact.last_name,
        "docType": contact.custom_document_type,
        "docNumber": contact.custom_document_number,
        "country": contact.custom_country,
        "language": contact.custom_language,
        "email": primary_email or "",
        "gender": contact.gender,
        "birthdate": contact.custom_dob,
        "education": contact.custom_academic_level,
        "entryDate": contact.custom_entry_date,
        "status": contact.custom_status,
        "demographics": processed_demographics
    }

def find_or_create_demographic_type(demographic_title, user_company=None):
    normalized_title = " ".join(demographic_title.strip().split()).title()
    object_type = "Contacto"

    if not normalized_title:
        return None

    try:
        filters = {"dt_title": normalized_title, "dt_object_type": object_type}
        if user_company:
            filters["dt_creator_company"] = user_company

        existing_doc_name = frappe.db.get_value(
            "qp_IQ_DemographicType",
            filters,
            "name"
        )

        if existing_doc_name:
            return existing_doc_name
        else:
            doc = frappe.new_doc("qp_IQ_DemographicType")
            doc.dt_title = normalized_title
            doc.dt_object_type = object_type
            doc.dt_tag_color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
            doc.dt_description = _("Demográfico '{0}' creado automáticamente para {1}.").format(normalized_title, object_type)
            if user_company:
                doc.dt_creator_company = user_company
            doc.insert(ignore_permissions=True)
            return doc.name

    except frappe.exceptions.UniqueValidationError:
        frappe.db.rollback()
        filters = {"dt_title": normalized_title, "dt_object_type": object_type}
        if user_company:
            filters["dt_creator_company"] = user_company
        return frappe.db.get_value(
            "qp_IQ_DemographicType",
            filters,
            "name"
        )

def _map_contact_data(contact_doc, data):
    first_name = data.get("firstName")
    last_name = data.get("lastName")
    email = data.get("email")

    name_regex = re.compile(r"^[a-zA-Z\sñÑÁÉÍÓÚüÜ]+$")

    if first_name and not name_regex.match(first_name):
        frappe.throw(_("El campo 'Nombres' solo debe contener letras y espacios."))
    
    if last_name and not name_regex.match(last_name):
        frappe.throw(_("El campo 'Apellidos' solo debe contener letras y espacios."))

    contact_doc.first_name = first_name
    contact_doc.last_name = last_name
    contact_doc.gender = data.get("gender") if data.get("gender") != "Seleccionar..." else None
    
    user_contact_info = frappe.db.get_value("Contact", {"user": frappe.session.user}, "custom_company")
    if not user_contact_info:
        frappe.throw(_("No se pudo determinar la compañía del usuario."))
    contact_doc.custom_company = user_contact_info

    contact_doc.custom_dob = data.get("birthdate") or None
    contact_doc.custom_language = data.get("language")
    contact_doc.custom_country = data.get("country")
    contact_doc.custom_document_type = data.get("docType")
    contact_doc.custom_document_number = data.get("docNumber")
    contact_doc.custom_academic_level = data.get("education") or None
    contact_doc.custom_entry_date = data.get("entryDate") or None
    contact_doc.custom_is_liseniq_contact = data.get("custom_is_liseniq_contact")

    email = data.get("email")
    contact_doc.email_ids = []
    if email:
        email_regex = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
        if not email_regex.match(email):
            frappe.throw(_("El formato del correo electrónico no es válido."))
        contact_doc.append("email_ids", {"email_id": email, "is_primary": 1})

    contact_doc.custom_additional_details = []
    demographics = data.get("demographics", [])
    if demographics:
        for item in demographics:
            demographic_type_title = item.get("type")
            if demographic_type_title:
                demographic_doc_name = find_or_create_demographic_type(demographic_type_title, user_company=user_contact_info)
                if demographic_doc_name:
                    contact_doc.append("custom_additional_details", {
                        "cad_demographic_type": demographic_doc_name,
                        "cad_tag": item.get("type"),
                        "cad_value": item.get("value")
                    })

@frappe.whitelist()
def create_contact(contact_data):
    try:
        data = json.loads(contact_data)

        user_contact_info = frappe.db.get_value("Contact", {"user": frappe.session.user}, "custom_company")
        if not user_contact_info:
            return {"status": "error", "message": _("No se pudo determinar la compañía del usuario.")}
        user_company = user_contact_info

        doc_number = data.get("docNumber")
        if doc_number:
            existing_contact = frappe.db.exists("Contact", {
                "custom_document_number": doc_number,
                "custom_company": user_company
            })
            if existing_contact:
                return {"status": "error", "message": _("Ya existe un contacto con el número de documento {0} en su compañía.").format(doc_number)}

        email = data.get("email")
        if email:
            if frappe.db.exists("Contact", {
                "custom_company": user_company,
                "name": ("in", frappe.get_all("Contact Email", filters={"email_id": email}, pluck="parent"))
            }):
                return {"status": "error", "message": _("Ya existe un contacto con el correo electrónico {0} en su compañía.").format(email)}

        new_contact = frappe.new_doc("Contact")
        new_contact.custom_status = "Activo"
        _map_contact_data(new_contact, data)
        new_contact.insert(ignore_permissions=True)
        
        contact_details = get_contact_details(new_contact.name)
        return {"status": "success", "docname": new_contact.name, "new_contact": contact_details}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error en create_contact")
        frappe.response.http_status_code = 500
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def update_contact(contact_name, contact_data):
    try:
        contact_doc = frappe.get_doc("Contact", contact_name)
        
        user_contact_info = frappe.db.get_value("Contact", {"user": frappe.session.user}, "custom_company")
        if not user_contact_info:
            return {"status": "error", "message": _("No se pudo determinar la compañía del usuario.")}
        user_company = user_contact_info
        
        if contact_doc.custom_company != user_company:
            return {"status": "error", "message": _("No tienes permiso para editar este contacto")}

        data = json.loads(contact_data)

        email = data.get("email")
        if email:
            existing_contacts = frappe.get_all("Contact Email", filters={"email_id": email}, fields=["parent"])
            for c in existing_contacts:
                if c.parent != contact_name:
                    parent_contact_company = frappe.db.get_value("Contact", c.parent, "custom_company")
                    if parent_contact_company == user_company:
                        return {"status": "error", "message": _("Ya existe otro contacto con el correo electrónico {0} en su compañía.").format(email)}

        _map_contact_data(contact_doc, data)
        contact_doc.save(ignore_permissions=True)

        updated_details = get_contact_details(contact_doc.name)
        return {"status": "success", "docname": contact_doc.name, "updated_contact": updated_details}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error en update_contact")
        frappe.response.http_status_code = 500
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def delete_contact(contact_name):
    try:
        contact_doc = frappe.get_doc("Contact", contact_name)
        
        user_contact_info = frappe.db.get_value("Contact", {"user": frappe.session.user}, "custom_company")
        if not user_contact_info:
            frappe.throw(_("No se pudo determinar la compañía del usuario."))
        user_company = user_contact_info

        if contact_doc.custom_company != user_company:
            frappe.throw(_("No tienes permiso para eliminar este contacto"))

        contact_doc.custom_is_deleted = 1
        contact_doc.save(ignore_permissions=True)
        # frappe.delete_doc('Contact', contact_name, ignore_permissions=True, force=True)
        return {"status": "success"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error en delete_contact")
        frappe.response.http_status_code = 500
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_demographic_suggestions(search_term):
    if not search_term:
        return []
        
    user_contact_info = frappe.db.get_value("Contact", {"user": frappe.session.user}, "custom_company")
    
    filters = [
        ["dt_object_type", "=", "Contacto"],
        ["dt_title", "like", f"%{search_term}%"]
    ]
    
    if user_contact_info:
        filters.append(["dt_creator_company", "=", user_contact_info])

    return frappe.get_all(
        "qp_IQ_DemographicType",
        filters=filters,
        fields=["dt_title"],
        limit=10
    )