import frappe

@frappe.whitelist()
def complete_tour(tour_name):
    user = frappe.session.user
    if not user or user == "Guest":
        return {"error": "User not logged in"}

    contact = frappe.db.get_value(
        "Contact",
        {"user": user, "custom_is_liseniq_contact": 0},
        ["name"],
        as_dict=True,
    )
    if not contact:
        return {"error": "No valid contact found for the user"}

    existing = frappe.get_all(
        "qp_IQ_Tour",
        filters={"parent": contact.name, "tour_name": tour_name},
        fields=["name"]
    )

    if existing:
        frappe.db.set_value("qp_IQ_Tour", existing[0].name, "completed", 1)
    else:
        contact_doc = frappe.get_doc("Contact", contact.name)
        contact_doc.append("custom_tours", {
            "tour_name": tour_name,
            "completed": 1,
            "completed_on": frappe.utils.now()
        })
        contact_doc.save(ignore_permissions=True)

    return {"success": True}