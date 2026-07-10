import frappe
import json
from frappe import _

@frappe.whitelist()
def set_active_company(company_id):
    """
    Establece la compañía activa en la sesión del usuario.
    Al cerrar sesión, este dato se destruye automáticamente.
    """
    user = frappe.session.user
    if user == "Guest":
        return "/login"
    
    if "Administrator" in frappe.get_roles(user):
        return "/app"

    contact_name = frappe.db.get_value("Contact", {"user": user}, "name")
    
    relation = frappe.get_all("qp_IQ_ContactCompany", filters={
        "parent": contact_name,
        "parenttype": "Contact",
        "cc_company": company_id
    }, fields=["name", "cc_role_profile"])

    if not relation:
        frappe.throw(_("No tienes permisos para acceder a esta compañía."))

    frappe.session.data["liseniq_active_company"] = company_id
    # Guardamos el perfil en sesión para no re-consultarlo
    frappe.session.data["liseniq_active_role_profile"] = relation[0].cc_role_profile
    
    session_key = "liseniq_company_name"
    frappe.session.data[session_key] = None

    if hasattr(frappe.local, "session_obj") and frappe.local.session_obj:
        frappe.local.session_obj.update()

    return "/iq-home"

@frappe.whitelist()
def get_current_active_company(user=None):
    """
    Función global para obtener la empresa ACTIVA del usuario en todo el backend.
    Prioriza la empresa seleccionada en la sesión (Company Switcher).
    Si no hay, hace fallback a la empresa por defecto del contacto.
    """
    user = user or frappe.session.user
    if not user or user == "Guest" or "Administrator" in frappe.get_roles(user):
        return None

    # 1. Prioridad: Leer de la sesión (Empresa suichada)
    active_company_id = frappe.session.data.get("liseniq_active_company")
    if active_company_id:
        return active_company_id

    # 2. Fallback: Leer del contacto directamente
    contact_company = frappe.db.get_value("Contact", {"user": user}, "custom_company")
    return contact_company


@frappe.whitelist()
def get_user_company_name(user=None):
    session_key = "liseniq_company_name"
    user = user or frappe.session.user
    
    if not user or user == "Guest" or "Administrator" in frappe.get_roles(user):
        return ""

    cached_name = (getattr(frappe.session, "data", {}) or {}).get(session_key)
    if cached_name:
        return cached_name

    active_company_id = frappe.session.data.get("liseniq_active_company")
    
    if not active_company_id:
        contact_name = frappe.db.get_value("Contact", {"user": user}, "name")
        if contact_name:
            companies = frappe.get_all("qp_IQ_ContactCompany", filters={"parent": contact_name, "parenttype": "Contact"}, fields=["cc_company", "cc_role_profile"], order_by="cc_is_default desc")
            
            if len(companies) == 1:
                active_company_id = companies[0].cc_company
                frappe.session.data["liseniq_active_company"] = active_company_id
                frappe.session.data["liseniq_active_role_profile"] = companies[0].cc_role_profile
                if hasattr(frappe.local, "session_obj") and frappe.local.session_obj:
                    frappe.local.session_obj.update()

    company_name = ""
    if active_company_id:
        company_name = frappe.db.get_value("qp_IQ_Company", active_company_id, "co_name") or ""

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

def global_website_context(context):
    if context is None:
        context = frappe._dict()

    user = frappe.session.user
    
    context.has_portal_access = False
    context.access_error_message = ""
    context.liseniq_company_name = ""
    context.first_login = False
    context.subscription_plan = ""
    context.app_features = []
    context.app_features_json = "[]"

    if user == "Guest":
        context.access_error_message = _("Debe iniciar sesión para acceder.")
        return context

    if "Administrator" in frappe.get_roles(user):
        context.has_portal_access = True
        return context

    contact = frappe.db.get_value(
        "Contact", 
        {"user": user}, 
        ["name", "custom_company", "custom_is_liseniq_contact", "custom_first_login"], 
        as_dict=True
    )
    
    if not contact:
        context.access_error_message = _("El usuario no se encuentra registrado o no tiene permisos de acceso (Contacto no encontrado).")
        return context

    active_company_id = frappe.session.data.get("liseniq_active_company")
    active_role_profile = frappe.session.data.get("liseniq_active_role_profile")
    
    companies = frappe.get_all("qp_IQ_ContactCompany", filters={"parent": contact.name, "parenttype": "Contact"}, fields=["cc_company", "cc_role_profile"])
    
    if not active_company_id:
        if len(companies) == 1:
            active_company_id = companies[0].cc_company
            active_role_profile = companies[0].cc_role_profile
        elif len(companies) == 0:
            active_company_id = contact.custom_company
            active_role_profile = None

    if not active_company_id and len(companies) <= 1:
        context.access_error_message = _("El usuario no tiene una compañía asignada. Contacte al administrador.")
        return context

    if contact.custom_is_liseniq_contact:
        context.access_error_message = _("Su usuario no tiene perfil administrativo para acceder a este portal.")
        return context

    context.has_portal_access = True
    context.liseniq_company_name = active_company_id or "" 
    context.first_login = contact.custom_first_login
        
    tours_list = frappe.get_all(
        "qp_IQ_Tour",
        filters={"parent": contact.name},
        fields=["tour_name", "completed"]
    )
    context.user_tours = {t.tour_name: t.completed for t in tours_list}
    
    if active_company_id:
        try:
            # Cargamos funcionalidades del PLAN DE SUSCRIPCIÓN de la empresa
            active_sub = frappe.get_all(
                "qp_IQ_CompanySubscription",
                filters={"sub_company": active_company_id, "sub_is_active": 1},
                fields=["sub_plan"],
                limit=1
            )

            if active_sub and active_sub[0].sub_plan:
                context.subscription_plan = active_sub[0].sub_plan
                plan_doc = frappe.get_doc("qp_IQ_AppPlan", active_sub[0].sub_plan)
                feature_names = [f.pf_feature for f in plan_doc.pl_features if f.pf_feature]
                
                if feature_names:
                    features = frappe.get_all(
                        "qp_IQ_AppFeature",
                        filters={"name": ("in", feature_names)},
                        fields=["fe_code"]
                    )
                    context.app_features = [f.fe_code for f in features if f.fe_code]
            
            # Cargamos funcionalidades extra del PERFIL DEL USUARIO
            if active_role_profile:
                role_features = frappe.get_all(
                    "qp_IQ_PortalRoleFeature",
                    filters={"parent": active_role_profile, "parenttype": "qp_IQ_PortalRole"},
                    fields=["feature"]
                )
                
                if role_features:
                    role_feature_names = [f.feature for f in role_features if f.feature]
                    if role_feature_names:
                        features_codes = frappe.get_all(
                            "qp_IQ_AppFeature",
                            filters={"name": ("in", role_feature_names)},
                            fields=["fe_code"]
                        )
                        extra_features = [f.fe_code for f in features_codes if f.fe_code]
                        context.app_features.extend(extra_features)

            # Eliminamos duplicados (por si el plan y el rol comparten features)
            context.app_features = list(set(context.app_features))
            context.app_features_json = json.dumps(context.app_features)

        except Exception as e:
            frappe.log_error(title="Error al cargar funcionalidades combinadas", message=str(e))

    return context

def check_access_and_redirect():
    context = frappe._dict()
    global_website_context(context)
    if not context.has_portal_access:
        frappe.throw(context.access_error_message, frappe.PermissionError)

@frappe.whitelist()
def set_first_login_false():
    user = frappe.session.user
    if user and user != "Guest":
        contact_name = frappe.db.get_value("Contact", {"user": user}, "name")
        if contact_name:
            try:
                frappe.db.set_value("Contact", contact_name, "custom_first_login", 0)
                frappe.db.commit()
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), "liseniq: set_first_login_false")

@frappe.whitelist()
def get_user_companies():
    """Devuelve la lista de empresas a las que tiene acceso el usuario para el Company Switcher)."""
    user = frappe.session.user
    if user == "Guest": return []
    
    contact_name = frappe.db.get_value("Contact", {"user": user}, "name")
    if not contact_name: return []

    contact_companies = frappe.get_all(
        "qp_IQ_ContactCompany",
        filters={"parent": contact_name, "parenttype": "Contact"},
        fields=["cc_company"]
    )

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
                "company_name": company_info.co_name or company_id,
                "logo": company_info.co_logo
            })

    return companies_data