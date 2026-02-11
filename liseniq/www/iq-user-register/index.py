import frappe
from frappe.utils.password import check_password
from frappe.core.doctype.user.user import test_password_strength

def get_context(context):
    context.show_sidebar = False
    context.show_topbar = False
    context.no_cache = True
    context.title = "Registro de Usuario"
    return context


@frappe.whitelist(allow_guest=True)
def register_user(first_name, last_name, email, company_name, password, accept_terms):
    if not (first_name and last_name and email and company_name and password):
        return {"status": "error", "message": "Todos los campos son obligatorios."}

    if not accept_terms:
        return {"status": "error", "message": "Debe aceptar los términos y condiciones."}
    
    if frappe.db.exists("User", {"email": email}):
        return {"status": "error", "message": "Ya existe un usuario con este correo electrónico."}
    
    try:
        result = test_password_strength(password, user_inputs=[email, first_name, last_name])
        if result.get('feedback', {}).get('password_policy_validation_passed') == False:
            suggestions = result.get('feedback', {}).get('suggestions', [])
            message = "La contraseña no cumple con los requisitos de seguridad."
            if suggestions:
                message += " " + " ".join(suggestions)
            return {"status": "error", "message": message}
    except Exception as e:
        frappe.log_error(f"Error validando contraseña: {str(e)}", "Password Validation Error")
    
    try:
      user = frappe.get_doc({
          "doctype": "User",
          "first_name": first_name,
          "last_name": last_name,
          "email": email,
          "enabled": 1,
          "new_password": password
      })
      user.insert(ignore_permissions=True)
      try:
          contact = frappe.get_doc('Contact', filters={'email_id': email})
          if contact:
              contact.custom_is_liseniq_user = 1
              contact.save(ignore_permissions=True)
      except Exception as e:
          pass  # No hacemos nada si no encontramos un contacto, el usuario se creó correctamente
      try:
          company = frappe.get_doc({
              "doctype": "qp_IQ_Company",
              "co_name": company_name,
              "co_admin_name": user.full_name,
              "co_admin_email": email,
              "co_accept_terms": 1,
              "co_accept_privacy_policy": 1
          })
          company.insert(ignore_permissions=True)
          frappe.db.commit()
      except Exception as e:
          user.delete(ignore_permissions=True)
          frappe.db.rollback()
          return {"status": "error", "message": f"Error al crear la compañía: {str(e)}"}
    except Exception as e:
        frappe.db.rollback()
        return {"status": "error", "message": f"Error al crear el usuario: {str(e)}"}
    return {"status": "success", "message": "Usuario registrado exitosamente."}

