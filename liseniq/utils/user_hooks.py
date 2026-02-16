import frappe

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

    # Enlazar contacto si existe
    contact_name = frappe.db.get_value(
        "Contact",
        {"email_id": doc.email},
        "name"
    )

    if contact_name:
        contact_doc = frappe.get_doc("Contact", contact_name)
        contact_doc.custom_is_liseniq_contact = 1
        contact_doc.custom_company = company_doc.name
        contact_doc.save(ignore_permissions=True)

    frappe.db.commit()