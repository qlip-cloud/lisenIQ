import frappe

def get_home_page(user):
    cache = frappe.cache()
    redirect_to = "/"

    if "Administrator" in frappe.get_roles(user):
        redirect_to = "/app"
    elif user != "Guest":
        contact_name = frappe.db.get_value("Contact", {"user": user}, "name")
        if contact_name:
            companies = frappe.db.get_all(
                "qp_IQ_ContactCompany",
                filters={"parent": contact_name, "parenttype": "Contact"},
                fields=["cc_company"]
            )
            
            if len(companies) > 1:
                redirect_to = "/iq-home/select_company"
            else:
                redirect_to = "/iq-home"

    if cache.get_value('b2c_login') == user:
        cache.delete_value('b2c_login')

    return redirect_to

def handle_login_redirect():
    user = frappe.session.user
    
    if "Administrator" not in frappe.get_roles(user):
        contact_name = frappe.db.get_value("Contact", {"user": user}, "name")
        
        if contact_name:
            companies = frappe.db.get_all(
                "qp_IQ_ContactCompany",
                filters={"parent": contact_name, "parenttype": "Contact"},
                fields=["cc_company"]
            )
            
            if len(companies) > 1:
                frappe.local.response["home_page"] = "/iq-home/select_company"
            else:
                frappe.local.response["home_page"] = "/iq-home"
        else:
            frappe.local.response["home_page"] = "/iq-home"