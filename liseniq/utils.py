import frappe
from functools import wraps

def get_all_templates():
    """
    Esta función obtiene y devuelve la lista de todas las plantillas.
    Actualmente usa datos de ejemplo, pero en el futuro aquí harías
    una llamada a la base de datos con frappe.get_all().
    """
    mock_data = [
        {
            "name": "Occ Cultura",
            "description": "Mide la cultura actual en la organización y apoya la definición de la cultura requerida para alinearla con la estrategia.",
            "category": "Recursos humanos",
            "type1": "Anónimo",
            "type2": "Cerrado",
            "questions": "78",
            "icon": "psychology"
        },
        {
            "name": "Occ Pulse",
            "description": "Identifica los factores claves de bienestar y ambiente laboral que afectan el compromiso de los colaboradores.",
            "category": "Recursos humanos",
            "type1": "Anónimo",
            "type2": "Cerrado",
            "questions": "78",
            "icon": "query_stats"
        },
        {
            "name": "Occ DEIP",
            "description": "Identifica el nivel de conocimiento, consciencia y madurez sobre la estrategia DEIP e inspirar y monitorear la evolución.",
            "category": "Recursos humanos",
            "type1": "Anónimo",
            "type2": "Cerrado",
            "questions": "78",
            "icon": "hub"
        },
        {
            "name": "Occ Por",
            "description": "Valora las 5 dimensiones que definen a un equipo: Las Personas, la Organización y los Resultados. Auto evaluación.",
            "category": "Recursos humanos",
            "type1": "Anónimo",
            "type2": "Cerrado",
            "questions": "78",
            "icon": "groups"
        },
        {
            "name": "Nueva Plantilla",
            "description": "Este es un nuevo ítem de ejemplo para mostrar la quinta tarjeta en la fila inferior.",
            "category": "General",
            "type1": "Público",
            "type2": "Abierto",
            "questions": "25",
            "icon": "science"
        }
    ]
    return mock_data

def get_page_categories():
    """
    Devuelve la lista de categorías para los filtros.
    En el futuro, esto podría venir de un DocType "Categoría de Plantilla".
    """
    return [
        {"name": "Creadas por ti", "id": "cat-creadas"},
        {"name": "Populares", "id": "cat-populares", "checked": True, "is_popular": True},
        {"name": "Recursos Humanos", "id": "cat-rh"},
        {"name": "Servicio al cliente", "id": "cat-servicio"},
        {"name": "Educacion", "id": "cat-educacion"},
        {"name": "Investigacion de mercado", "id": "cat-investigacion"}
    ]

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if frappe.session.user == "Guest":
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = "/login"
            frappe.local.response["http_status_code"] = 302
            return
        return func(*args, **kwargs)
    return wrapper

