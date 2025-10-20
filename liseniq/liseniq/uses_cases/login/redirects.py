import frappe

def get_home_page(user):

    cache = frappe.cache()
    redirect_to = "/"

    if "Administrator" in frappe.get_roles(user):
        redirect_to = "/app"
    
    if user != "Guest" and user != "Administrator":
        redirect_to = "/iq-home"

    if cache.get_value('b2c_login') == frappe.session.user:
        cache.delete_value('b2c_login')

    return redirect_to

def handle_login_redirect():
    if "Administrator" not in frappe.get_roles():
        frappe.local.response["home_page"] = "/iq-home"