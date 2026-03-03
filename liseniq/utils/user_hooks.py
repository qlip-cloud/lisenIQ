import frappe

def link_company_after_b2c(doc, method):
    """Hook ejecutado después de crear un User en el registro B2C."""
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

    # Enlazar usuario a la compañía
    company_doc.co_admin_name = doc.full_name
    company_doc.save(ignore_permissions=True)


def link_contact_after_create(doc, method):
    """Hook ejecutado después de que ERPNext crea automáticamente un Contact.
    Este se ejecuta cuando ERPNext crea el Contact asociado al User.
    """
    # Verificar que no sea un contacto de liseniq (para evitar duplicados)
    if doc.get("custom_is_liseniq_contact") == 1:
        return
    
    # Verificar que tenga email
    if not doc.email_id:
        return
    
    # Buscar si este email corresponde a una compañía B2C
    company_name = frappe.db.get_value(
        "qp_IQ_Company",
        {"co_admin_email": doc.email_id},
        "name"
    )

    if not company_name:
        return
    

    # Enlazar contacto a la compañía (solo si no está ya enlazado)
    if not doc.custom_company:
        doc.custom_company = company_name
        doc.save(ignore_permissions=True)

    # Crear un nuevo cliente en ERPNext para esta compañía 

    company_doc = frappe.get_doc("qp_IQ_Company", company_name)
    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": company_doc.co_name,
        "customer_type": "Company",
        "customer_group": "Todas las categorías de clientes",
        "territory": "Todos los Territorios",
        "tax_id": company_doc.co_tax_id
    })
    customer.insert(ignore_permissions=True)

    # Enlazar el cliente al contacto
    doc.append("links", {
        "link_doctype": "Customer",
        "link_name": customer.name
    })
    doc.save(ignore_permissions=True)