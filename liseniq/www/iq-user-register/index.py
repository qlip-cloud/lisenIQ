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
def register_user(first_name, last_name, email, company_name, accept_terms):
    if not (first_name and last_name and email and company_name and accept_terms):
        return {"status": "error", "message": "Todos los campos son obligatorios."}

    if not accept_terms:
        return {"status": "error", "message": "Debe aceptar los términos y condiciones."}
    
    if frappe.db.exists("User", {"email": email}):
        return {"status": "error", "message": "Ya existe un usuario con este correo electrónico."}
    
    # Creación solo de la compañía
    try:
        company = frappe.get_doc({
            "doctype": "qp_IQ_Company",
            "co_name": company_name,
            "co_admin_email": email,
            "co_accept_terms": 1,
            "co_accept_privacy_policy": 1
        })
        company.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        return {"status": "error", "message": f"Error al crear la compañía: {str(e)}"}
    
    # Pre-registro del usuario para que luego se ejecute la integración con B2C al momento de la creación del usuario en el sistema (hook on document User)

    try:
      user = frappe.get_doc({
      "doctype": "User",
      "first_name": first_name,
      "last_name": last_name,
      "email": email,
      "enabled": 1,
      })

      user.insert(ignore_permissions=True)
    except Exception as e:
        pass
    return {"status": "success", "message": "Se ha creado la compañía y enviado un correo de invitación al usuario."}



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
                    <a href="{login_url}" style="color: #1f6feb; text-decoration: none;">
                        {login_url}
                    </a>
                </p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{login_url}" 
                       style='margin-top: 20px; padding: 10px 30px; cursor: pointer; background: #6c2fff !important; color: #fff !important; font-size: 18px !important; font-family: "Rubik", sans-serif !important; font-weight: 500 !important; border: none !important; border-radius: 8px !important; padding: 14px 48px !important; cursor: pointer !important; transition: background 0.2s !important; text-align: center !important;'>
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