import frappe

@frappe.whitelist()
def get_user_company_name(user=None):
    user = user or frappe.session.user
    contact_info = frappe.db.get_value("Contact", {"user": user, "custom_is_liseniq_contact": 0}, ["custom_company"], as_dict=True)
    if contact_info and contact_info.custom_company:
        company_name = frappe.db.get_value("qp_IQ_Company", contact_info.custom_company, "co_name")
        return company_name or ""
    return ""

