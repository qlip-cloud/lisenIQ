import frappe
from frappe.core.doctype.user.user import create_contact
def link_company_after_b2c(doc, method):

    company_name = frappe.db.get_value(
        "qp_IQ_Company",
        {"co_admin_email": doc.email},
        "name"
    )

    if not company_name:
        return

    company_doc = frappe.get_doc("qp_IQ_Company", company_name)


    if company_doc.co_admin_name:
        return

    # Enlazar usuario
    company_doc.co_admin_name = doc.full_name
    company_doc.save(ignore_permissions=True)

    frappe.enqueue(
        "liseniq.utils.user_hooks.link_contact_to_company",
        user_id=doc.name,
        queue="default",
        enqueue_after_commit=True,
        timeout=300
    )


def link_contact_to_company(user_id):
    # Primero buscar contacto vinculado al usuario
    contact_name = frappe.db.get_value("Contact", {"user": user_id}, "name")
    
    # Si no existe, buscar por email
    if not contact_name:
        contact_name = frappe.db.get_value("Contact", {"email_id": user_id}, "name")
    
    # Si aún no existe, intentar crearlo
    if not contact_name:
        try:
            user_doc = frappe.get_doc("User", user_id)
            contact = create_contact(user_doc, ignore_mandatory=True)
            if contact:
                contact_name = contact.name
        except Exception as e:
            frappe.log_error(f"Error creating contact for {user_id}: {str(e)}", "liseniq: link_contact_to_company")
            return
    
    if not contact_name:
        frappe.log_error(f"Could not find or create contact for {user_id}", "liseniq: link_contact_to_company")
        return
    
    doc = frappe.get_doc("Contact", contact_name)
    
    # Vincular el usuario al contacto si no está vinculado
    if not doc.user:
        doc.user = user_id
    
    if doc.get("custom_is_liseniq_contact") == 1:
        doc.save(ignore_permissions=True)
        return
    
    company_name = frappe.db.get_value(
        "qp_IQ_Company",
        {"co_admin_email": user_id},
        "name"
    )

    if not company_name:
        return
    
    # Enlazar contacto a la compañía
    doc.custom_company = company_name
    doc.save(ignore_permissions=True)