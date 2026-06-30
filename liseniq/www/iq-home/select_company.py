import frappe

def get_context(context):
    context.no_cache = 1
    context.page_title = "Seleccionar Compañía"
    context.no_breadcrumbs = True
    context.is_navbar_custom = True
    
    user = frappe.session.user

    if user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
    
    if "Administrator" in frappe.get_roles(user):
        frappe.local.flags.redirect_location = "/app"
        raise frappe.Redirect

    contact_name = frappe.db.get_value("Contact", {"user": user}, "name")
    if not contact_name:
        frappe.local.flags.redirect_location = "/"
        raise frappe.Redirect

    # Buscamos las relaciones en la tabla hija
    contact_companies = frappe.get_all(
        "qp_IQ_ContactCompany",
        filters={"parent": contact_name, "parenttype": "Contact"},
        fields=["cc_company"]
    )

    if len(contact_companies) == 0:
        frappe.local.flags.redirect_location = "/login" 
        raise frappe.Redirect
    elif len(contact_companies) == 1:
        # Guardamos solo en la sesión actual
        frappe.session.data["liseniq_active_company"] = contact_companies[0].cc_company
        if hasattr(frappe.local, "session_obj") and frappe.local.session_obj:
            frappe.local.session_obj.update()
        
        frappe.local.flags.redirect_location = "/iq-home"
        raise frappe.Redirect

    # Si hay múltiples empresas, buscamos los datos reales en qp_IQ_Company
    companies_data = []
    for cc in contact_companies:
        company_id = cc.cc_company

        company_info = frappe.db.get_value(
            "qp_IQ_Company", 
            company_id, 
            ["co_name", "co_logo"], 
            as_dict=True
        )
        
        if company_info:
            companies_data.append({
                "company_id": company_id,
                "company_name": company_info.co_name or company_id, # Fallback al ID si co_name está vacío
                "logo": company_info.co_logo
            })

    context.companies = companies_data
    return context