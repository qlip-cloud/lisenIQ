# -*- coding: utf-8 -*-
"""
Lógica pura (sin frappe) del dashboard Liderazgo 360°.
Recibe filas "largas" (una por evaluador x comportamiento) y devuelve el mismo
payload JSON que consume el front-end (modelo DML y modelos a la medida).
Compatible con Python 3.6+ (ERPNext v13).
"""
import re
import unicodedata
from collections import OrderedDict
from statistics import mean, pstdev

ESCALA = {"min": 1, "max": 5}

# Campos obligatorios y sus alias (se comparan normalizados: sin tildes, minúsculas, solo a-z0-9)
CANONICAL_ALIASES = OrderedDict([
    ("evaluador_id", ["id_evaluator", "documento evaluador", "evaluator document", "evaluador documento", "evaluator id"]),
    ("evaluador", ["evaluator", "evaluador", "nombre evaluador"]),
    ("evaluado_id", ["id_evaluatee", "documento evaluado", "evaluated document", "evaluado documento", "evaluated id"]),
    ("evaluado", ["evaluatee", "evaluado", "evaluated", "nombre evaluado", "lider", "leader"]),
    ("relacion", ["relation", "relacion", "relación", "tipo de evaluador", "relationship", "rol evaluador"]),
    ("tema", ["tema", "dimension", "dimensión", "theme"]),
    ("competencia", ["variable", "competencia", "competency"]),
    ("comportamiento", ["question", "comportamiento", "behavior", "behaviour", "pregunta"]),
    ("respuesta", ["answer", "respuesta", "response", "valor", "puntaje"]),
])
REQUIRED = ["evaluado", "relacion", "tema", "competencia", "comportamiento", "respuesta"]

# Columnas técnicas que NUNCA se tratan como demográficos
IGNORE_ALIASES = [
    "email evaluador", "email evaluado", "email", "correo", "name", "idx", "creation", "modified",
    "owner", "survey", "encuesta", "medicion", "medición", "fecha", "date", "docstatus", "id",
    "email_evaluator", "email_evaluatee", "fecha de nacimiento", "fecha de ingreso", "custom_dob", "entry_date", "pregunta abierta", "comentario", "comentarios", "observaciones",
]


def norm(text):
    t = unicodedata.normalize("NFKD", str(text or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def to_float(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def r2(x):
    return None if x is None else round(x, 2)


def map_columns(columns, demographic_columns=None):
    """columns: lista de (fieldname, label[, fieldtype]). Devuelve (mapa_canonico, lista_demograficos).
    mapa_canonico[campo] = fieldname real; demograficos = [(fieldname, label)]"""
    date_fields = set(c[0] for c in columns if len(c) > 2 and c[2] in ("Date", "Datetime", "Time"))
    columns = [(c[0], c[1]) for c in columns]
    by_field, by_label = {}, {}
    for fieldname, label in columns:
        by_field.setdefault(norm(fieldname), fieldname)
        by_label.setdefault(norm(label), fieldname)
    mapping = {}
    for canon, aliases in CANONICAL_ALIASES.items():
        found_f = None
        # 1) coincidencia por fieldname (no depende del idioma/traducción de la etiqueta)
        for a in aliases:
            if norm(a) in by_field:
                found_f = by_field[norm(a)]
                break
        # 2) coincidencia por etiqueta
        if found_f is None:
            for a in aliases:
                if norm(a) in by_label:
                    found_f = by_label[norm(a)]
                    break
        if found_f is not None:
            mapping[canon] = found_f
    missing = [c for c in REQUIRED if c not in mapping]
    if missing:
        found = ", ".join("%s (%s)" % (l or f, f) for f, l in columns)
        raise ValueError("Faltan columnas requeridas en el reporte: %s. Columnas encontradas: %s"
                         % (", ".join(missing), found))
    used = set(mapping.values())
    ignore = set(norm(a) for a in IGNORE_ALIASES)
    demos = []
    if demographic_columns:
        wanted = [norm(c) for c in demographic_columns]
        for fieldname, label in columns:
            if norm(label) in wanted or norm(fieldname) in wanted:
                demos.append((fieldname, label or fieldname))
    else:
        for fieldname, label in columns:
            if fieldname in used or fieldname in date_fields:
                continue
            if norm(fieldname) in ignore or norm(label) in ignore:
                continue
            demos.append((fieldname, label or fieldname))
    return mapping, demos


def rows_to_records(rows, columns, demographic_columns=None):
    """rows: lista de dicts o de listas (según el reporte). columns: lista de dicts/str del reporte."""
    cols = []
    for c in columns:
        if isinstance(c, dict):
            cols.append((c.get("fieldname") or c.get("label"), c.get("label") or c.get("fieldname"), c.get("fieldtype")))
        else:
            # formato "Label:Tipo:Ancho"
            lab = str(c).split(":")[0]
            ft = str(c).split(":")[1] if ":" in str(c) else None
            cols.append((lab, lab, ft))
    mapping, demos = map_columns(cols, demographic_columns)
    order = [c[0] for c in cols]
    label_of = dict((c[0], c[1]) for c in cols)
    out = []
    diag = {"filas": 0, "no_dict": 0, "sin_respuesta_numerica": 0, "sin_tema_comp_comport_evaluado": 0,
            "muestra": None, "tipo_fila": None}
    for row in rows:
        diag["filas"] += 1
        if diag["tipo_fila"] is None:
            diag["tipo_fila"] = type(row).__name__
        if isinstance(row, (list, tuple)):
            row = dict(zip(order, row))
        if not isinstance(row, dict):
            diag["no_dict"] += 1
            continue

        def g(fieldname):
            # por fieldname; si la fila trae la etiqueta como clave, también se acepta
            if fieldname in row:
                return row.get(fieldname)
            return row.get(label_of.get(fieldname))

        if diag["muestra"] is None:
            diag["muestra"] = {"claves": sorted(str(k) for k in row.keys())[:30],
                               "respuesta": g(mapping["respuesta"]), "tema": g(mapping["tema"]),
                               "competencia": g(mapping["competencia"]),
                               "comportamiento": g(mapping["comportamiento"]), "evaluado": g(mapping["evaluado"])}
        v = to_float(g(mapping["respuesta"]))
        if v is None:
            diag["sin_respuesta_numerica"] += 1
            continue
        rec = {k: g(mapping[k]) for k in mapping}
        rec["respuesta"] = v
        rec["relacion"] = str(rec.get("relacion") or "").strip()
        for k in ("tema", "competencia", "comportamiento", "evaluado"):
            rec[k] = str(rec.get(k) or "").strip()
        if not (rec["tema"] and rec["competencia"] and rec["comportamiento"] and rec["evaluado"]):
            diag["sin_tema_comp_comport_evaluado"] += 1
            continue
        rec["demo"] = {label: str(g(f) if g(f) is not None else "").strip() for f, label in demos}
        out.append(rec)
    rows_to_records.last_diag = diag
    return out, [label for _, label in demos]


def rel_type(rel):
    n = norm(rel)
    if n.startswith("auto"):
        return "auto"
    if n.startswith("jefe") or n.startswith("superior") or n.startswith("supervisor"):
        return "jefe"
    if n.startswith("par"):
        return "par"
    if n.startswith("colab") or n.startswith("subordinado") or n.startswith("reporte"):
        return "colaborador"
    return "otro"


def group_stats(recs):
    """Promedio simple pooled. auto = Autoevaluación; otros = TODO lo demás (Jefe+Par+Colaborador, sin ponderar)."""
    by = {"auto": [], "otros": [], "jefe": [], "par": [], "colaborador": []}
    for r in recs:
        t = r["_t"]
        if t == "auto":
            by["auto"].append(r["respuesta"])
        else:
            by["otros"].append(r["respuesta"])
            if t in by:
                by[t].append(r["respuesta"])
    res = {k: (r2(mean(v)) if v else None) for k, v in by.items()}
    # brecha = diferencia de los valores ya redondeados (igual que el HTML validado)
    res["brecha"] = round(res["auto"] - res["otros"], 2) if res["auto"] is not None and res["otros"] is not None else None
    types = [res[k] for k in ("jefe", "par", "colaborador") if res[k] is not None]
    res["dispersion"] = round(pstdev(types), 3) if len(types) > 1 else 0.0
    return res


def _item(base, recs):
    s = group_stats(recs)
    d = dict(base)
    d.update({k: s[k] for k in ("auto", "otros", "jefe", "par", "colaborador", "brecha")})
    d["_disp"] = s["dispersion"]
    ots = [r["respuesta"] for r in recs if r["_t"] != "auto"]
    d["_raw"] = mean(ots) if ots else None  # media sin redondear: desempata rankings
    return d


def _sort_otros(items, reverse=True):
    # None al final; estable respecto al orden original
    return sorted(items, key=lambda x: (x["otros"] is None, -(x["_raw"] or 0) if reverse else (x["_raw"] or 0)))


def _quasi_identifier(recs, label):
    """True si >50% de los valores distintos del campo corresponden a un único líder evaluado."""
    vals = {}
    for r in recs:
        v = r["demo"].get(label, "")
        if v:
            vals.setdefault(v, set()).add(r["evaluado"])
    if len(vals) < 2:
        return True  # 0 o 1 valor distinto: no sirve para segmentar
    single = sum(1 for s in vals.values() if len(s) == 1)
    return single / float(len(vals)) > 0.5


def build_payload(rows, columns, cliente, medicion, demographic_columns=None):
    recs, demo_labels = rows_to_records(rows, columns, demographic_columns)
    if not recs:
        d = getattr(rows_to_records, "last_diag", {})
        if not d.get("filas"):
            raise ValueError("El reporte devolvió 0 filas para esta medición. Verifica que el filtro del reporte "
                             "(REPORT_FILTER, por defecto 'survey') sea el correcto y que la medición tenga respuestas.")
        raise ValueError("El reporte devolvió %s filas pero ninguna es utilizable. Diagnóstico: %s"
                         % (d.get("filas"), d))
    for r in recs:
        r["_t"] = rel_type(r["relacion"])

    vmin = min(r["respuesta"] for r in recs)
    vmax = max(r["respuesta"] for r in recs)

    def pair(r):
        return (str(r.get("evaluador_id") or r.get("evaluador") or ""), str(r.get("evaluado_id") or r["evaluado"]))

    gs = group_stats(recs)
    kpis = {
        "n_lideres": len(set(str(r.get("evaluado_id") or r["evaluado"]) for r in recs)),
        "n_evaluaciones": len(set(pair(r) for r in recs)),
        "n_evaluadores": len(set(p[0] for p in map(pair, recs))),
        "n_respuestas": len(recs),
        "puntaje_auto": gs["auto"],
        "puntaje_otros": gs["otros"],
        "brecha_global": gs["brecha"],
    }

    # --- dimensiones (orden de primera aparición; el front las reordena) ---
    temas = OrderedDict()
    for r in recs:
        temas.setdefault(r["tema"], []).append(r)
    dimensiones = [_item({"tema": t}, rs) for t, rs in temas.items()]

    # --- competencias ---
    comps = OrderedDict()
    for r in recs:
        comps.setdefault((r["tema"], r["competencia"]), []).append(r)
    competencias = [_item({"competencia": c, "tema": t}, rs) for (t, c), rs in sorted(comps.items())]
    competencias = _sort_otros(competencias)

    # --- comportamientos ---
    behs = OrderedDict()
    for r in recs:
        behs.setdefault((r["tema"], r["competencia"], r["comportamiento"]), []).append(r)
    comportamientos = []
    for (t, c, b), rs in behs.items():
        it = _item({"comportamiento": b, "competencia": c, "tema": t}, rs)
        it["dispersion"] = it.pop("_disp")
        comportamientos.append(it)
    comportamientos = _sort_otros(comportamientos)

    for it in dimensiones + competencias:
        it.pop("_disp", None)

    n5 = min(5, len(competencias))
    top_f = competencias[:n5]
    top_o = _sort_otros(competencias, reverse=False)[:n5]

    asc = _sort_otros(comportamientos, reverse=False)
    gaps = sorted([b for b in comportamientos if b["brecha"] is not None], key=lambda x: -x["brecha"])
    by_disp = sorted(comportamientos, key=lambda x: x["dispersion"])

    for lst in (dimensiones, competencias, comportamientos):
        for it in lst:
            it.pop("_raw", None)
    payload = {
        "meta": {"cliente": cliente, "medicion": medicion},
        "escala": {"min": int(vmin) if vmin < 1 else 1, "max": 5 if vmax <= 5 else int(vmax)},
        "kpis": kpis,
        "dimensiones": dimensiones,
        "competencias": competencias,
        "top_fortalezas_comp": top_f,
        "top_oportunidades_comp": top_o,
        "comportamientos": comportamientos,
        "behav_top5": comportamientos[:5],
        "behav_bottom5": asc[:5],
        "behav_top10": comportamientos[:10],
        "behav_bottom10": asc[:10],
        "gap_top10": gaps[:10],
        "consenso_bajo": list(reversed(by_disp[-8:])),
        "consenso_alto": by_disp[:8],
    }

    # --- demográficos (sin umbral mínimo de N) ---
    fields, demos = [], {}
    for label in demo_labels:
        if _quasi_identifier(recs, label):
            continue
        values = sorted(set(r["demo"].get(label, "") for r in recs if r["demo"].get(label, "")))
        rows_out = []
        for v in values:
            rs = [r for r in recs if r["demo"].get(label, "") == v]
            s = group_stats(rs)
            rows_out.append({
                "valor": v,
                "n_evaluadores": len(set(pair(r)[0] for r in rs)),
                "n_lideres": len(set(str(r.get("evaluado_id") or r["evaluado"]) for r in rs)),
                "auto": s["auto"], "otros": s["otros"], "jefe": s["jefe"], "par": s["par"],
                "colaborador": s["colaborador"], "brecha": s["brecha"],
            })
        fields.append({"key": label, "label": label, "values": values})
        demos[label] = rows_out
    payload["demographic_fields"] = fields
    payload["demographics"] = demos
    return payload
