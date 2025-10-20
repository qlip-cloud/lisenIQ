import frappe

@frappe.whitelist()
def get_user_company_name(user=None):

	session_key = "liseniq_company_name"
	user = user or frappe.session.user
	if not user or user == "Guest":
		return ""

	cached_name = (getattr(frappe.session, "data", {}) or {}).get(session_key)
	if cached_name:
		return cached_name

	contact_info = frappe.db.get_value(
		"Contact",
		{"user": user, "custom_is_liseniq_contact": 0},
		["custom_company"],
		as_dict=True,
	)
	if contact_info and contact_info.custom_company:
		company_name = frappe.db.get_value("qp_IQ_Company", contact_info.custom_company, "co_name") or ""
	else:
		company_name = ""

	try:
		session_obj = getattr(frappe.local, "session_obj", None)
		if session_obj:
			session_obj.data[session_key] = company_name
			if hasattr(session_obj, "update"):
				session_obj.update()
		else:
			if hasattr(frappe, "session") and hasattr(frappe.session, "data"):
				frappe.session.data[session_key] = company_name
	except Exception:
		pass

	return company_name

def set_company_name_on_session_creation(login_manager):
	try:
		user = getattr(login_manager, "user", None) or frappe.session.user
		if user and user != "Guest":
			get_user_company_name(user=user)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "liseniq: set_company_name_on_session_creation")

