import frappe

def execute():
    """
    Script idempotente para migrar la empresa actual (custom_company)
    de un Contact a la nueva tabla hija Multicompañía (custom_iq_companies).
    """

    frappe.reload_doc("liseniq", "doctype", "qp_iq_contactcompany")

    # Obtenemos todos los contactos que tienen un custom_company asignado
    contacts = frappe.db.sql("""
        SELECT name, custom_company
        FROM `tabContact`
        WHERE custom_company IS NOT NULL AND custom_company != ''
    """, as_dict=True)

    for contact in contacts:
        exists = frappe.db.exists("qp_IQ_ContactCompany", {
            "parent": contact.name,
            "parenttype": "Contact",
            "cc_company": contact.custom_company
        })

        if not exists:
            child = frappe.new_doc("qp_IQ_ContactCompany")
            child.parent = contact.name
            child.parenttype = "Contact"
            child.parentfield = "custom_iq_companies"
            child.cc_company = contact.custom_company
            child.cc_is_default = 1 # Valor entero para campos Check
            
            # Forzamos la inserción directa en la base de datos
            child.db_insert()