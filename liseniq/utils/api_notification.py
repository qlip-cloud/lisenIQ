import frappe
from frappe.utils import now

@frappe.whitelist()
def get_unread_notifications():
 
    if frappe.session.user == "Guest":
        return []

    # Filtros para notificaciones no leídas del usuario actual
    filters = {
        "owner": frappe.session.user,
        "pn_is_read": 0
    }

    notifications = frappe.get_list(
        "qp_IQ_PortalNotification",
        filters=filters,
        fields=["name", "pn_title", "pn_message", "creation"],
        order_by="creation desc"
    )
    
    return notifications

@frappe.whitelist()
def mark_notification_as_read(notification_name):
    """
    Marca una notificación específica como leída (pn_is_read=1).
    """
    try:
        # Verificar existencia
        if not frappe.db.exists("qp_IQ_PortalNotification", notification_name):
            return {"status": "error", "message": "Notificación no encontrada"}

        doc = frappe.get_doc("qp_IQ_PortalNotification", notification_name)
        
        # Solo el dueño puede leer sus notificaciones
        if doc.owner != frappe.session.user and frappe.session.user != "Administrator":
             return {"status": "error", "message": "No tienes permiso para modificar esta notificación"}

        # Actualizar estado
        doc.pn_is_read = 1
        if hasattr(doc, 'pn_read_date'):
            doc.pn_read_date = now()
            
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {"status": "success", "message": "Notificación marcada como leída"}
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error marking notification as read")
        return {"status": "error", "message": str(e)}