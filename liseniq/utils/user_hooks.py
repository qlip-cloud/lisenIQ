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

    frappe.enqueue(
        "liseniq.utils.user_hooks.link_contact_to_company",
        email=doc.email,
        queue="default",
        enqueue_after_commit=True,
        timeout=300,
        at_front=False,
        now=False
    )


def link_contact_to_company(email, retry_count=0):
    # Obtener el contacto, si aun no existe, se esperará a que se cree en el proceso de registro de ERPNext
    max_retries = 5
    
    contact_exists = frappe.db.exists("Contact", {"email_id": email})
    if not contact_exists:
        # Si el contacto aún no existe y no hemos excedido los reintentos, volver a encolar
        if retry_count < max_retries:
            frappe.enqueue(
                "liseniq.utils.user_hooks.link_contact_to_company",
                email=email,
                retry_count=retry_count + 1,
                queue="default",
                enqueue_after_commit=True,
                timeout=300,
                at_front=False,
                now=False
            )
        return
    
    doc = frappe.get_doc("Contact", {"email_id": email})
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