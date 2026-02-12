import frappe
from frappe.utils.password import check_password
from frappe.core.doctype.user.user import test_password_strength
from frappe.utils import get_url

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
      })

      user.flags.no_welcome_mail = True
      user.flags.no_password_notification = True
      user.new_password = password

      user.insert(ignore_permissions=True)
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
          send_listenaiq_welcome_email(user, company)
      except Exception as e:
          user.delete(ignore_permissions=True)
          frappe.db.rollback()
          return {"status": "error", "message": f"Error al crear la compañía: {str(e)}"}
      try:
          contact = frappe.get_doc('Contact', filters={'email_id': email})
          if contact:
              contact.custom_is_liseniq_contact = 1
              contact.custom_company = company.name
              contact.save(ignore_permissions=True)
      except Exception as e:
          pass  # No hacemos nada si no encontramos un contacto, el usuario se creó correctamente
      
    except Exception as e:
        frappe.db.rollback()
        return {"status": "error", "message": f"Error al crear el usuario: {str(e)}"}
    return {"status": "success", "message": "Usuario registrado exitosamente."}



def send_listenaiq_welcome_email(user, company):
    try:
        login_url = get_url("/login")

        subject = "Bienvenido a ListenIQ – Tu cuenta ha sido creada"

        message = f"""
        <div style="font-family: Arial, sans-serif; background-color: #f4f6f9; padding: 30px;">
            <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 30px; border-radius: 8px;">
                
                <h2 style="color: #2c3e50;">¡Bienvenido a ListenIQ!</h2>
                
                <p>Hola <strong>{user.full_name}</strong>,</p>
                
                <p>Tu cuenta ha sido creada exitosamente. Aquí están los detalles de tu registro:</p>
                
                <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                    <tr>
                        <td style="padding: 8px 0;"><strong>Empresa:</strong></td>
                        <td>{company.co_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>Administrador:</strong></td>
                        <td>{user.full_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>Correo registrado:</strong></td>
                        <td>{user.email}</td>
                    </tr>
                </table>

                <p style="margin-top: 25px;">
                    Puedes iniciar sesión directamente desde el siguiente enlace:
                </p>

                <p>
                    <a href="{login_url}" style="color: #1f6feb;">
                        {login_url}
                    </a>
                </p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{login_url}" 
                       style="background-color: #1f6feb; 
                              color: #ffffff; 
                              padding: 12px 25px; 
                              text-decoration: none; 
                              border-radius: 5px; 
                              display: inline-block;
                              font-weight: bold;">
                        Comenzar con la plataforma
                    </a>
                </div>

                <p style="font-size: 14px; color: #6c757d;">
                    Si no solicitaste esta cuenta, por favor ignora este mensaje.
                </p>

                <p style="margin-top: 30px;">
                    — El equipo de ListenIQ
                </p>

            </div>
        </div>
        """

        frappe.sendmail(
            recipients=[user.email],
            subject=subject,
            message=message
        )

    except Exception as e:
        frappe.log_error(
            f"Error enviando correo de bienvenida personalizado: {str(e)}",
            "ListenIQ Welcome Email Error"
        )