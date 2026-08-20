# listenaiq/api/cultura_dashboard.py
#
# Adaptado del patrón de listenaiq/api/survey_dashboard.py (dashboard de
# Engagement) para el dashboard de Cultura Organizacional (metodología OCC).
#
# DIFERENCIAS DE MODELO FRENTE A ENGAGEMENT (confirmadas con el usuario):
#   - Engagement usa UN nivel (theme). Cultura usa DOS niveles:
#       theme    -> Tipo de Cultura   (Responsable / Competitiva / Humanista)
#       variable -> Dimensión         (Principios, Sostenibilidad, ... 9 en total)
#                   o el tag "Abiertas" para las 3 preguntas de texto libre.
#   - No hay eNPS ni Índice de Engagement en Cultura: se removió toda esa
#     lógica (detección de tipo NPS, conversión de escala 1-10->1-5, etc.).
#   - Escala fija 1-5 para las 72 preguntas (confirmado con el usuario).
#   - El catálogo solo guarda el texto del atributo "positivo" (no existe
#     un campo separado para el "limitante"/negativo).
#
# AJUSTES QUE DEBES REVISAR ANTES DE USAR EN PRODUCCIÓN:
#   1. REPORT_NAME: se asume el MISMO Report que Engagement
#      ("Survey Response Custom Report Front"), reutilizado con un
#      `survey` distinto (confirmado). Si Cultura usa un Report separado,
#      cambia esta constante.
#   2. TIPO_COLOR_HINT / TIPO_ORDER_HINT: son solo una sugerencia de orden
#      y color para cuando el `theme` coincide exactamente con estos 3
#      nombres. Si tu catálogo usa otra ortografía (p. ej. "Responsable "
#      con espacio, o mayúsculas distintas), edítalos aquí. El dashboard
#      sigue funcionando aunque no coincidan (usa colores por defecto),
#      pero el orden y los colores de marca no se verían igual que en el
#      HTML original.
#   3. FIXED_COLUMNS: debe reflejar exactamente las columnas fijas que
#      devuelve tu Report (más allá de las demográficas dinámicas).

import re
from collections import defaultdict, OrderedDict

import frappe

REPORT_NAME = "Survey Response Custom Report Front"

# Tag/variable que marca las preguntas de texto libre (mismo patrón que
# Engagement). Ajusta si en el catálogo de Cultura el tag se llama distinto.
OPEN_TEXT_TAG = "Abierta"

# Umbral mínimo de anonimato: ningún resultado se desagrega para grupos
# con menos personas que esto (mismo valor que el HTML original).
MIN_N = 5

# Orden y color sugeridos para los 3 Tipos de Cultura, si el `theme`
# coincide exactamente con estos nombres (colores extraídos por muestreo
# de píxeles del PDF original de metodología OCC).
TIPO_ORDER_HINT = ["Responsable", "Competitiva", "Humanista"]
TIPO_COLOR_HINT = {
    "Responsable": "#0889D6",
    "Competitiva": "#EB493C",
    "Humanista": "#48BBA1",
}
DEFAULT_TIPO_COLOR = "#888888"

FIXED_COLUMNS = {
    "name", "gender", "custom_dob", "country", "custom_academic_level",
    "entry_date", "question", "variable", "theme", "answer",
}


def _norm(text):
    text = re.sub(r"\s+", " ", (text or "")).strip().lower()
    return text.rstrip("?¿.!¡ ")


_OPEN_TEXT_TAG_NORM = _norm(OPEN_TEXT_TAG)


def _to_float(value):
    try:
        v = float(str(value).strip().replace(",", "."))
        return v
    except (TypeError, ValueError):
        return None


def _get_universe(survey, demo_fields):
    """
    Todas las personas convocadas a esta medición, vía qp_IQ_SurveyRecipient
    (filtrado por sr_survey) -> Contact (sr_contact). Misma fuente de verdad
    que usan los 'records' de respuestas reales, así que la participación
    por segmento demográfico se puede calcular por conteo directo
    (sin necesidad de heurísticas de cruce/matching).
    """
    contacts = frappe.get_all(
        "qp_IQ_SurveyRecipient", filters={"sr_survey": survey}, pluck="sr_contact"
    )
    contacts = [c for c in contacts if c]
    if not contacts:
        return []

    gender_map = {}
    for row in frappe.get_all("Contact", filters={"name": ["in", contacts]}, fields=["name", "gender"]):
        gender_map[row.name] = row.gender

    demo_data = {}
    if demo_fields:
        placeholders = ", ".join(["%s"] * len(contacts))
        rows = frappe.db.sql(
            f"""
            SELECT cad.parent as contact, cad.cad_demographic_type as demo_id, cad.cad_value as value
            FROM `tabqp_IQ_ContactAdditionalDetail` cad
            WHERE cad.parent IN ({placeholders})
            """,
            contacts,
            as_dict=True,
        )
        for r in rows:
            demo_data.setdefault(r.contact, {})[r.demo_id] = r.value

    universe = []
    for c in contacts:
        row = [gender_map.get(c) or "Sin dato"]
        row += [demo_data.get(c, {}).get(f) or "Sin dato" for f in demo_fields]
        universe.append(row)
    return universe


@frappe.whitelist()
def get_dashboard_data(survey):
    """
    Devuelve el payload consumido por la Website Page del dashboard de
    Cultura Organizacional, filtrado a una sola medición (Survey).

    Uso desde el front:
        fetch('/api/method/listenaiq.api.cultura_dashboard.get_dashboard_data'
              + '?survey=' + encodeURIComponent(survey),
              { credentials: 'same-origin' })

    Requiere sesión iniciada (no se marca allow_guest=True a propósito,
    confirmado con el usuario).
    """
    if frappe.session.user == "Guest":
        frappe.throw("Debes iniciar sesión para ver este dashboard.", frappe.PermissionError)

    if not survey:
        frappe.throw("Falta el parámetro 'survey'")

    if not frappe.db.exists("Survey", survey):
        frappe.throw(f"Encuesta no encontrada: {survey}")

    from frappe.desk.query_report import run
    
    current_user = frappe.session.user
    frappe.session.user = "Administrator" 
    try:
        report = run(REPORT_NAME, filters={"survey": survey})
    except Exception as e:
        frappe.session.user = current_user
        raise e
    finally:
        frappe.session.user = current_user
    rows = report.get("result") or []

    if not rows:
        universe = _get_universe(survey, [])
        return {
            "attributes": [], "tipos_order": [], "dimensions_order": [],
            "dim_to_tipo": {}, "tipo_colors": {},
            "records": [], "universe": universe, "wordclouds": {},
            "open_text_labels_order": [],
            "demographic_fields": [],
            "meta": {
                "n_respondentes": 0, "n_universo": len(universe) or None,
                "survey": survey, "min_n": MIN_N,
            },
        }

    col_labels = {c["fieldname"]: c["label"] for c in (report.get("columns") or [])}
    demo_fields = [k for k in rows[0].keys() if k not in FIXED_COLUMNS]
    demographic_fields = [{"key": "gender", "label": col_labels.get("gender", "Género")}]
    demographic_fields += [{"key": f, "label": col_labels.get(f, f)} for f in demo_fields]

    # 1) Catálogo de atributos: (tipo=theme, dimension=variable, texto) -> code.
    #    Se excluyen a propósito:
    #    - Preguntas con variable "Abiertas" (van solo a la nube de palabras)
    #    - Preguntas SIN tipo (theme) asignado (dato incompleto en el
    #      catálogo; no deben contaminar ningún promedio ni gráfica)
    question_order = OrderedDict()
    tipos_seen = OrderedDict()   # tipo -> None (preserva orden de aparición)
    dim_to_tipo = OrderedDict()  # dimension -> tipo (primera vez que se ve)
    dims_by_tipo = OrderedDict()  # tipo -> OrderedDict(dimension -> None)

    for r in rows:
        tipo = r.get("theme")
        dimension = r.get("variable")
        if not tipo or _norm(dimension) == _OPEN_TEXT_TAG_NORM:
            continue
        key = (tipo, dimension or "Sin dimensión", r.get("question") or "")
        if key not in question_order:
            question_order[key] = {"code": len(question_order)}
        tipos_seen.setdefault(tipo, None)
        dim_to_tipo.setdefault(dimension or "Sin dimensión", tipo)
        dims_by_tipo.setdefault(tipo, OrderedDict())
        dims_by_tipo[tipo].setdefault(dimension or "Sin dimensión", None)

    attributes_payload = [
        {"code": meta["code"], "tipo": tipo, "dimension": dimension, "text": pregunta}
        for (tipo, dimension, pregunta), meta in question_order.items()
    ]

    # Orden de tipos: si TODOS los tipos del catálogo coinciden con el hint
    # (Responsable/Competitiva/Humanista), usa ese orden fijo; si no,
    # respeta el orden de aparición en los datos (no se inventan tipos).
    if set(tipos_seen.keys()) <= set(TIPO_ORDER_HINT):
        tipos_order = [t for t in TIPO_ORDER_HINT if t in tipos_seen]
    else:
        tipos_order = list(tipos_seen.keys())

    dimensions_order = []
    for tipo in tipos_order:
        dimensions_order += list(dims_by_tipo.get(tipo, {}).keys())

    tipo_colors = {t: TIPO_COLOR_HINT.get(t, DEFAULT_TIPO_COLOR) for t in tipos_order}

    # 2) Agrupar filas por respondiente (columna 'name' = ID de la respuesta)
    respondents = OrderedDict()
    open_text_rows = defaultdict(list)
    open_text_total = defaultdict(int)
    open_text_theme = {}
    open_text_labels_order = []  # preserva el orden de aparición de las preguntas abiertas

    for r in rows:
        resp_id = r.get("name")
        if resp_id not in respondents:
            demo_values = [r.get("gender") or "Sin dato"]
            demo_values += [r.get(f) or "Sin dato" for f in demo_fields]
            respondents[resp_id] = {"demo": demo_values, "answers": {}, "open_text": {}}

        tipo = r.get("theme") or "Sin tipo"
        dimension = r.get("variable") or "Sin dimensión"
        question_text = r.get("question") or ""
        raw_answer = r.get("answer")

        if _norm(dimension) == _OPEN_TEXT_TAG_NORM:
            group_label = question_text or tipo
            if group_label not in open_text_theme:
                open_text_labels_order.append(group_label)
            open_text_theme[group_label] = tipo
            open_text_total[group_label] += 1
            text = raw_answer.strip() if isinstance(raw_answer, str) else ""
            if len(text) > 1:
                open_text_rows[group_label].append(text)
                # Guarda los tokens normalizados de ESTE respondiente para esta
                # pregunta, para que el front pueda recalcular la nube de
                # palabras al aplicar filtros demográficos (en vez de solo
                # mostrar el agregado fijo de toda la medición).
                respondents[resp_id]["open_text"][group_label] = _tokenize_es(text)
            continue

        if not r.get("theme"):
            continue

        key = (tipo, dimension, question_text)
        code = question_order[key]["code"]
        num = _to_float(raw_answer)
        # Escala fija 1-5 (confirmado). Cualquier valor fuera de rango se
        # descarta como dato inválido en vez de contaminar el promedio.
        val = num if (num is not None and 1 <= num <= 5) else None
        respondents[resp_id]["answers"][code] = val

    n_questions = len(question_order)
    records_payload = []
    for resp in respondents.values():
        answers_arr = [resp["answers"].get(i) for i in range(n_questions)]
        # Un arreglo de tokens por pregunta abierta, en el mismo orden que
        # open_text_labels_order (así el front no depende de nombres de
        # pregunta como llaves, solo de la posición — más compacto).
        open_text_arr = [resp["open_text"].get(label, []) for label in open_text_labels_order]
        records_payload.append(resp["demo"] + [answers_arr, open_text_arr])

    # 3) Nube de palabras agregada (todas las respuestas, sin filtrar) — se
    #    sigue enviando como valor por defecto / respaldo, pero el front
    #    ahora puede recalcularla a partir de los tokens por respondiente
    #    (arriba) cuando hay un filtro demográfico activo.
    wordclouds = {}
    for question_label in open_text_labels_order:
        texts = open_text_rows.get(question_label, [])
        counts = defaultdict(int)
        for text in texts:
            for word in _tokenize_es(text):
                counts[word] += 1
        top_words = sorted(counts.items(), key=lambda x: -x[1])[:60]
        n_total = open_text_total.get(question_label, len(texts))
        wordclouds[question_label] = {
            "tipo": open_text_theme.get(question_label, ""),
            "words": [{"word": w, "count": c} for w, c in top_words],
            "n_valid": len(texts),
            "n_blank": max(n_total - len(texts), 0),
            "total_unique_words": len(counts),
        }

    universe = _get_universe(survey, demo_fields)

    return {
        "attributes": attributes_payload,
        "tipos_order": tipos_order,
        "dimensions_order": dimensions_order,
        "dim_to_tipo": dim_to_tipo,
        "tipo_colors": tipo_colors,
        "records": records_payload,
        "universe": universe,
        "wordclouds": wordclouds,
        "open_text_labels_order": open_text_labels_order,
        "demographic_fields": demographic_fields,
        "meta": {
            "n_respondentes": len(respondents),
            "n_universo": len(universe) or None,
            "survey": survey,
            "min_n": MIN_N,
        },
    }


# ---------------------------------------------------------------------
# Normalización de texto libre para nubes de palabras.
#
# A diferencia del diccionario de canonización hecho a mano para el
# dataset 2026 original (retada/retado/retos -> "Reto", etc. — específico
# de ese vocabulario), aquí se usa una normalización GENÉRICA reutilizable
# para cualquier medición futura: minúsculas sin tildes, elimina
# conectores comunes, y aplica una heurística simple de singularización.
# Es menos precisa que el diccionario curado a mano, pero no depende de
# conocer de antemano las palabras exactas que usará cada encuesta.
# ---------------------------------------------------------------------
import unicodedata

_STOPWORDS_ES = set(
    "de la que el en y a los del se las por un para con no una su al lo como "
    "más pero sus le ya o este sí porque esta entre cuando muy sin sobre "
    "también me hasta hay donde quien desde todo nos durante todos uno les "
    "ni contra otros ese eso ante ellos e esto mí antes algunos qué unos yo "
    "otro otras otra él tanto esa estos mucho quienes nada muchos cual poco "
    "ella estar estas algunas algo nosotros mi mis tú te ti tu tus ellas "
    "nosotras vosotros vosotras os mío mía míos mías tuyo tuya tuyos tuyas "
    "suyo suya suyos suyas nuestro nuestra nuestros nuestras vuestro vuestra "
    "vuestros vuestras esos esas mismo misma podria podría cierta medida "
    "menos otro entre".split()
)


def _strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _singularize(word):
    if word.endswith("ces") and len(word) > 5:
        return word[:-3] + "z"
    if word.endswith("es") and len(word) > 6:
        return word[:-2]
    if word.endswith("s") and len(word) > 5 and not word.endswith(("as", "os")):
        return word[:-1]
    return word


def _tokenize_es(text):
    t = _strip_accents(text.lower())
    words = re.findall(r"[a-z]{3,}", t)
    out = []
    for w in words:
        if w in _STOPWORDS_ES:
            continue
        out.append(_singularize(w))
    return out
