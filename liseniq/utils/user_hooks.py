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
    frappe.log_error(f"Linked {doc.name} to company {company_name}", "liseniq: link_company_after_b2c")
    frappe.enqueue(
        "liseniq.utils.user_hooks.link_contact_to_company",
        user_id=doc.name,
        queue="default",
        enqueue_after_commit=True,
        timeout=300
    )


def link_contact_to_company(user_id):
    contact_exists = frappe.db.exists("Contact", {"user": user_id})
    frappe.log_error(f"Contact exists for {user_id}: {contact_exists}", "liseniq: link_contact_to_company")
    if not contact_exists:
        user_doc = frappe.get_doc("User", user_id)
        create_contact(user_doc)


    doc = frappe.get_doc("Contact", {"user": user_id})
    if doc.get("custom_is_liseniq_contact") == 1:
        return
    
    company_name = frappe.db.get_value(
        "qp_IQ_Company",
        {"co_admin_email": doc.email_id},
        "name"
    )

    if not company_name:
        return
    
    # Enlazar contacto
    doc.custom_company = company_name
    doc.save(ignore_permissions=True)