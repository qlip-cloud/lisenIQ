# your_app/api/survey_dashboard.py
#
# Servicio que transforma la salida del Script Report
# "Survey Response Custom Report Front" (formato largo: una fila
# por respondiente x pregunta) en el payload que consume el
# dashboard (formato ancho: un registro por respondiente).
#
# AJUSTES QUE DEBES REVISAR ANTES DE USAR EN PRODUCCIÓN:
#   1. ENGAGEMENT_QUESTIONS: confirma que el texto de estas preguntas
#      coincide EXACTO con el `qn_statement` guardado en qp_IQ_Question.
#   2. Rango de la escala Likert: asumo 1-5. Si tu encuesta usa otra
#      escala (0-10, 1-6, etc.) ajusta la validación en _to_float/uso.
#   3. eNPS: detecto la pregunta de recomendación por texto exacto.
#      Si no existe para una encuesta dada, el dashboard debe ocultar
#      ese widget (lo maneja el front con enps == null).

import math
import re
from collections import defaultdict, OrderedDict
from frappe import _
import frappe

REPORT_NAME = "Survey Response Custom Report Front"

# Preguntas que conforman el Índice de Engagement (mismo set que
# TEMAS_INDICE_DE_ENGAGEMENT en tu reporte). Ajusta si tu catálogo cambia.
ENGAGEMENT_QUESTIONS = {
    "Si me ofrecieran un trabajo en condiciones similares en otra empresa, me quedaría donde estoy",
    "Le recomendaría a un amigo o familiar que trabaje en esta organización",
    "Siento compromiso y orgullo de trabajar en esta organización",
    "Hago parte de un equipo de alto desempeño en la organización",
    "Me veo aprendiendo y creciendo en esta organización en el futuro",
    "Los líderes en esta organización me inspiran",
}
ENPS_QUESTION_TEXT = "Le recomendaría a un amigo o familiar que trabaje en esta organización"

# Preguntas ABIERTAS (comentarios de texto libre). Se identifican por el
# TAG/VARIABLE (columna 'variable' del reporte, viene de
# qn_demographic -> dt_title), no por el tema (columna 'theme').
# Ajusta el valor si en tu catálogo el tag se llama distinto.
OPEN_TEXT_TAG = "Abierta"


def _norm(text):
    text = re.sub(r"\s+", " ", (text or "")).strip().lower()
    return text.rstrip("?¿.!¡ ")


_ENPS_QUESTION_NORM = _norm(ENPS_QUESTION_TEXT)
_ENGAGEMENT_QUESTIONS_NORM = {_norm(q) for q in ENGAGEMENT_QUESTIONS}
_OPEN_TEXT_TAG_NORM = _norm(OPEN_TEXT_TAG)

FIXED_COLUMNS = {
    "name", "gender", "custom_dob", "country", "custom_academic_level",
    "entry_date", "question", "variable", "theme", "answer",
}

STOPWORDS = set(
    "de la que el en y a los del se las por un para con no una su al lo como "
    "más pero sus le ya o este sí porque esta entre cuando muy sin sobre "
    "también me hasta hay donde quien desde todo nos durante todos uno les "
    "ni contra otros ese eso ante ellos e esto mí antes algunos qué unos yo "
    "otro otras otra él tanto esa estos mucho quienes nada muchos cual poco "
    "ella estar estas algunas algo nosotros mi mis tú te ti tu tus ellas "
    "nosotras vosotros vosotras os mío mía míos mías tuyo tuya tuyos tuyas "
    "suyo suya suyos suyas nuestro nuestra nuestros nuestras vuestro vuestra "
    "vuestros vuestras esos esas".split()
)


def _norm_demo_value(v):
    """Limpia un valor demográfico: recorta espacios y colapsa vacíos a None."""
    if v is None:
        return None
    v = str(v).strip()
    return v or None


def _to_float(value):
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _get_nps_question_texts():
    """
    Textos (normalizados) de las preguntas marcadas como tipo 'NPS' en el
    catálogo, vía qp_IQ_Question.qn_type -> qp_IQ_QuestionType.qnt_type_name.
    Esta es la fuente de verdad para identificar la(s) pregunta(s) de eNPS;
    ENPS_QUESTION_TEXT queda solo como respaldo por si esta consulta no
    encuentra nada (p. ej. catálogo sin configurar todavía).
    """
    rows = frappe.db.sql(
        """
        SELECT DISTINCT q.qn_statement AS question_text
        FROM `tabqp_IQ_Question` q
        LEFT JOIN `tabqp_IQ_QuestionType` qt ON q.qn_type = qt.name
        WHERE qt.qnt_type_name = 'NPS'
        """,
        as_dict=True,
    )
    texts = {_norm(r.question_text) for r in rows if r.question_text}
    return texts or {_ENPS_QUESTION_NORM}


def _get_universe(survey, demo_fields, field_titles):
    """
    Todas las personas esperadas para esta medición, vía qp_IQ_SurveyRecipient
    (filtrado por sr_survey) -> Contact (sr_contact).
    Devuelve filas en el MISMO orden de campos que 'records' (sin enps/answers),
    para poder filtrarlas con los mismos controles demográficos del front.

    IMPORTANTE: qp_IQ_DemographicType puede tener VARIOS registros distintos
    con el mismo dt_title (ej. "Sede" repetido 14 veces con IDs distintos —
    probablemente uno por medición/versión). El contacto puede tener su valor
    guardado bajo un ID "hermano" distinto al que usa esta medición en
    particular. Por eso el emparejamiento se hace por NOMBRE (dt_title),
    no por el ID exacto de demo_fields.
    """
    sr_survey = frappe.db.get_value("qp_IQ_Survey", filters={"su_name": survey}, fieldname="name")
    contacts = frappe.get_all(
        "qp_IQ_SurveyRecipient", filters={"sr_survey": sr_survey}, pluck="sr_contact"
    )
    contacts = [c for c in contacts if c]
    if not contacts:
        return []

    gender_map = {}
    for row in frappe.get_all("Contact", filters={"name": ["in", contacts]}, fields=["name", "gender"]):
        gender_map[row.name] = row.gender

    # demo_data_by_title[contact][dt_title] = value (más reciente primero)
    demo_data_by_title = {}
    if demo_fields:
        placeholders = ", ".join(["%s"] * len(contacts))
        rows = frappe.db.sql(
            f"""
            SELECT cad.parent as contact, dt.dt_title as title, cad.cad_value as value
            FROM `tabqp_IQ_ContactAdditionalDetail` cad
            LEFT JOIN `tabqp_IQ_DemographicType` dt ON cad.cad_demographic_type = dt.name
            WHERE cad.parent IN ({placeholders})
            ORDER BY cad.modified DESC
            """,
            contacts,
            as_dict=True,
        )
        for r in rows:
            if not r.title:
                continue
            bucket = demo_data_by_title.setdefault(r.contact, {})
            bucket.setdefault(r.title, r.value)  # conserva el más reciente (ya viene ordenado)

    universe = []
    for c in contacts:
        row = [_norm_demo_value(gender_map.get(c)) or "Sin dato"]
        row += [
            _norm_demo_value(demo_data_by_title.get(c, {}).get(field_titles.get(f))) or "Sin dato"
            for f in demo_fields
        ]
        universe.append(row)
    return universe


@frappe.whitelist(methods=["GET"])
def get_available_surveys(exclude=None):
    """
    Lista de mediciones disponibles para comparar en la pestaña de
    Tendencias, tomadas de qp_IQ_Survey (no de Survey directamente).

    - El nombre a mostrar/usar es qp_IQ_Survey.su_name, que es un Link cuyo
      valor coincide con el Survey.name real (el mismo parámetro 'survey'
      que espera get_dashboard_data).
    - Se filtra para que solo aparezcan mediciones con el mismo su_owner y
      su_template que la medición actual, así son comparables entre sí
      (mismas dimensiones/preguntas).
    """
    exclude = frappe.db.get_value("qp_IQ_Survey", {"name": exclude}, "su_name") if exclude else None
    filters = {}
    if exclude:
        current = frappe.db.get_value(
            "qp_IQ_Survey", {"su_name": exclude}, ["su_owner", "su_template"], as_dict=True
        )
        if current:
            filters["su_owner"] = current.su_owner
            filters["su_template"] = current.su_template
        filters["su_name"] = ["!=", exclude]

    rows = frappe.get_all(
        "qp_IQ_Survey",
        filters=filters,
        fields=["name","su_name", "creation"],
        order_by="creation desc",
        limit_page_length=200,
    )
    return [{"name": r.name, "title": r.su_name} for r in rows if r.su_name]


@frappe.whitelist(methods=["GET"])
def get_dashboard_data(survey):
    """
    Devuelve el payload consumido por la Website Page del dashboard,
    filtrado a una sola medición (Survey).

    Uso desde el front: frappe.call({
        method: "your_app.api.survey_dashboard.get_dashboard_data",
        args: { survey: "<nombre_de_la_medicion>" }
    })
    """
    survey = frappe.get_value("qp_IQ_Survey", {"name": survey}, "su_name")
    if not survey:
        frappe.throw("Falta el parámetro 'survey'")

    if not frappe.db.exists("Survey", survey):
        frappe.throw(f"Encuesta no encontrada: {survey}")

    # Verifica que el usuario actual tenga permisos para acceder a la medición

    verify_permissions_user_company(survey)

    # Reutiliza el reporte existente en vez de reimplementar las
    # consultas (respeta permisos, histórico vs. en vivo, etc.)
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
        universe = _get_universe(survey, [], {})
        return {
            "questions": [],
            "records": [],
            "universe": universe,
            "wordclouds": {},
            "demographic_fields": [],
            "meta": {"n_respondentes": 0, "n_universo": len(universe) or None, "survey": survey, "enps_question_matched": False},
        }

    col_labels = {c["fieldname"]: c["label"] for c in (report.get("columns") or [])}
    demo_fields = [k for k in rows[0].keys() if k not in FIXED_COLUMNS]
    demographic_fields = [{"key": "gender", "label": col_labels.get("gender", "Género")}]
    demographic_fields += [{"key": f, "label": col_labels.get(f, f)} for f in demo_fields]

    # 1) Catálogo de preguntas Likert/índice: (tema, variable, pregunta) -> code
    #    Se excluyen a propósito:
    #    - Preguntas con tag/variable "Abiertas" (van solo a la nube de palabras)
    #    - Preguntas SIN tema asignado (dato incompleto en el catálogo,
    #      no deben contaminar ningún promedio ni gráfica)
    question_order = OrderedDict()
    for r in rows:
        theme = r.get("theme")
        variable = r.get("variable")
        if not theme or _norm(variable) == _OPEN_TEXT_TAG_NORM:
            continue
        key = (theme, variable or "Sin variable", r.get("question") or "")
        if key not in question_order:
            question_order[key] = {
                "code": len(question_order),
                "is_index": _norm(key[2]) in _ENGAGEMENT_QUESTIONS_NORM,
            }

    questions_payload = [
        [tema, variable, pregunta, meta["is_index"]]
        for (tema, variable, pregunta), meta in question_order.items()
    ]

    # 2) Agrupar filas por respondiente (columna 'name' = ID de la respuesta)
    respondents = OrderedDict()
    open_text_rows = defaultdict(list)     # pregunta -> [texto, ...] (solo válidos, no vacíos)
    open_text_total = defaultdict(int)     # pregunta -> total de filas encontradas (válidas + vacías)
    open_text_theme = {}                   # pregunta -> tema (para mostrarlo en el título de cada tarjeta)
    raw_by_resp_code = {}                  # (resp_id, code) -> valor numérico crudo
    code_max = defaultdict(float)          # code -> valor máximo observado (para detectar escala 1-10)
    code_to_question = {}                  # code -> texto de la pregunta

    for r in rows:
        resp_id = r.get("name")
        if resp_id not in respondents:
            demo_values = [_norm_demo_value(r.get("gender")) or "Sin dato"]
            demo_values += [_norm_demo_value(r.get(f)) or "Sin dato" for f in demo_fields]
            respondents[resp_id] = {"demo": demo_values, "answers": {}, "enps": None}

        theme = r.get("theme") or "Sin tema"
        variable = r.get("variable") or "Sin variable"
        question_text = r.get("question") or ""
        raw_answer = r.get("answer")

        if _norm(variable) == _OPEN_TEXT_TAG_NORM:
            # Pregunta abierta (identificada por tag/variable "Abiertas"):
            # nunca entra a "answers" ni a ningún promedio. Se agrupa por
            # PREGUNTA (texto exacto), no por tema, para que cada pregunta
            # abierta tenga su propia nube de palabras y tabla.
            group_label = question_text or theme
            open_text_theme[group_label] = theme
            open_text_total[group_label] += 1
            text = raw_answer.strip() if isinstance(raw_answer, str) else ""
            if len(text) > 1:
                open_text_rows[group_label].append(text)
            continue

        if not r.get("theme"):
            # Pregunta (no abierta) sin tema asignado: se ignora por
            # completo, no cuenta para ningún promedio.
            continue

        key = (theme, variable, question_text)
        code = question_order[key]["code"]
        code_to_question[code] = question_text
        num = _to_float(raw_answer)
        if num is not None:
            raw_by_resp_code[(resp_id, code)] = num
            if num > code_max[code]:
                code_max[code] = num

    # 2b) Identificar la(s) pregunta(s) de eNPS por su TIPO en el catálogo
    # (qp_IQ_QuestionType.qnt_type_name = 'NPS'), no por coincidencia de
    # texto. Esas preguntas se responden en escala 1-10 y se convierten a
    # 1-5 por RANGOS (no proporcional):
    #   1-2 -> 1   3-4 -> 2   5-6 -> 3   7-8 -> 4   9-10 -> 5
    # El valor crudo 1-10 se conserva aparte para el cálculo del eNPS.
    nps_question_texts = _get_nps_question_texts()
    nps_codes = {c for c, q in code_to_question.items() if _norm(q) in nps_question_texts}
    enps_code = next((c for c, q in code_to_question.items() if _norm(q) == _ENPS_QUESTION_NORM), None)
    if enps_code is None and nps_codes:
        enps_code = next(iter(nps_codes))
    # Respaldo: cualquier pregunta con valores >5 detectados en los datos,
    # por si el catálogo de tipos no está configurado para alguna.
    wide_scale_codes = nps_codes | {c for c, m in code_max.items() if m > 5}

    def _nps_to_5(v):
        # 1,2->1  3,4->2  5,6->3  7,8->4  9,10->5
        return min(5, max(1, math.ceil(v / 2.0)))

    for (resp_id, code), num in raw_by_resp_code.items():
        if code in wide_scale_codes:
            val = _nps_to_5(num) if 1 <= num <= 10 else None
            if code == enps_code and 1 <= num <= 10:
                respondents[resp_id]["enps"] = num
        else:
            val = num if 1 <= num <= 5 else None
        respondents[resp_id]["answers"][code] = val

    n_questions = len(question_order)
    records_payload = []
    for resp in respondents.values():
        answers_arr = [resp["answers"].get(i) for i in range(n_questions)]
        records_payload.append(resp["demo"] + [resp["enps"], answers_arr])

    # 3) Nube de palabras y tabla por CADA PREGUNTA abierta (no agrupadas),
    #    con metadata (válidas, en blanco, palabras únicas) para la pestaña
    #    "Preguntas Abiertas"
    wordclouds = {}
    for question_label, texts in open_text_rows.items():
        counts = defaultdict(int)
        for text in texts:
            for word in re.findall(r"[a-záéíóúñü]{4,}", text.lower()):
                if word not in STOPWORDS:
                    counts[word] += 1
        top_words = sorted(counts.items(), key=lambda x: -x[1])[:40]
        n_total = open_text_total.get(question_label, len(texts))
        wordclouds[question_label] = {
            "theme": open_text_theme.get(question_label, ""),
            "words": [{"word": w, "count": c} for w, c in top_words],
            "n_valid": len(texts),
            "n_blank": max(n_total - len(texts), 0),
            "total_unique_words": len(counts),
        }

    universe = _get_universe(survey, demo_fields, col_labels)

    enps_question_avg = None
    if enps_code is not None:
        vals = [resp["answers"].get(enps_code) for resp in respondents.values() if resp["answers"].get(enps_code) is not None]
        if vals:
            enps_question_avg = round(sum(vals) / len(vals), 2)

    return {
        "questions": questions_payload,
        "records": records_payload,
        "universe": universe,
        "wordclouds": wordclouds,
        "demographic_fields": demographic_fields,
        "meta": {
            "n_respondentes": len(respondents),
            "n_universo": len(universe) or None,
            "survey": survey,
            "enps_question_matched": enps_code is not None,
            # Diagnóstico: promedio (escala 1-5) de la pregunta de eNPS ya
            # convertida por rangos. Úsalo para validar contra el 4.55 esperado.
            "enps_question_avg": enps_question_avg,
        },
    }


def verify_permissions_user_company(survey):
    """
    Verifica que el usuario actual tenga permisos para acceder a la medición
    (Survey) dada, comparando su compañía con el su_owner de la medición.
    Lanza PermissionError si no tiene acceso.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("No autorizado"), frappe.PermissionError)

    user_contact = frappe.get_doc("Contact", {"email_id": frappe.session.user})
    company = user_contact.custom_company if user_contact else None
    associated_companies = frappe.get_all("qp_IQ_ContactCompany", filters={"parent": user_contact.name}, pluck="cc_company") if user_contact else []

    companies = set(filter(None, [company] + associated_companies))
    survey_owner = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey}, "su_owner")
    if survey_owner not in companies:
        frappe.throw(_("No autorizado para acceder a esta medición"), frappe.PermissionError)