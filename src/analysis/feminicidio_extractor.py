# src/analysis/feminicidio_extractor.py
from __future__ import annotations
from typing import Dict, List, Tuple
import re
import unicodedata
import pandas as pd

try:
    import spacy
    _NLP = spacy.load("es_core_news_sm")
except Exception:
    _NLP = None  # si no está spaCy, seguimos solo con regex

# --- utilidades ---
def _norm(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = text.lower()
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")
    return t

# Estados de México (para ubicar rápidamente)
MEX_STATES = {
    "aguascalientes","baja california","baja california sur","campeche","chiapas","chihuahua",
    "cdmx","ciudad de mexico","coahuila","colima","durango","guanajuato","guerrero","hidalgo",
    "jalisco","mexico","edomex","michoacan","morelos","nayarit","nuevo leon","oaxaca","puebla",
    "queretaro","quintana roo","san luis potosi","sinaloa","sonora","tabasco","tamaulipas",
    "tlaxcala","veracruz","yucatan","zacatecas"
}

# Patrones principales
P_FEM = re.compile(r"\bfemi?nicid(?:io|ios|al|a|as|as|o|os|aria|arias|ario)\b")
P_EVENTO = re.compile(r"\b(asesin(?:ada|ato|o)|homicidio|priv[oó] de la vida|hallad[ao] sin vida|murio|ultimad[ao]|estrangulad[ao]|apu[nñ]alad[ao])\b")
P_VICTIMA = re.compile(r"\b(mujer|joven|adolescente|nina|madre|esposa|novia|estudiante)\b")
P_REL = re.compile(r"\b(pareja|expareja|espos[oa]|novio|exnovio|exespos[oa]|concubin[oa])\b")
P_NEG = re.compile(r"\b(descartan|descarto|no fue|no es|desmienten)\s+(?:el\s+)?femi?nicidio\b")
P_CONTEXTO = re.compile(r"\b(protesta|marcha|estadisticas|cifras|tipificaci[oó]n|tipificar|delito de feminicidio|campan[a|a])\b")

P_EDAD = re.compile(r"\b(?:de\s+)?(\d{1,2})\s*anos\b")
P_MENOR = re.compile(r"\bmenor(?:es)?(?:\s+de\s+edad)?\b")

def score_feminicidio(texto: str) -> Tuple[float, Dict[str, List[str]]]:
    t = _norm(texto)
    hits = {"fem":[],"victima":[],"evento":[],"rel":[],"neg":[],"contexto":[]}
    score = 0.0

    m = P_FEM.findall(t);        hits["fem"] = m;        score += 1.0 if m else 0.0
    v = P_VICTIMA.findall(t);    hits["victima"] = v;    score += 0.4 if v else 0.0
    e = P_EVENTO.findall(t);     hits["evento"] = e;     score += 0.4 if e else 0.0
    r = P_REL.findall(t);        hits["rel"] = r;        score += 0.3 if r else 0.0

    n = P_NEG.findall(t);        hits["neg"] = n;        score -= 0.6 if n else 0.0
    c = P_CONTEXTO.findall(t);   hits["contexto"] = c;   score -= 0.4 if (c and not m) else 0.0

    if score < 0: score = 0.0
    if score > 1.3: score = 1.3
    return score, hits

def extract_fields(texto: str) -> Dict[str, str]:
    t = _norm(texto)
    fields = {"victima_edad":"", "victima_menor":"No", "ubicacion_estado":"", "relacion_agresor":""}

    # Edad
    m = P_EDAD.search(t)
    if m:
        fields["victima_edad"] = m.group(1)
        try:
            if int(m.group(1)) < 18:
                fields["victima_menor"] = "Sí"
        except Exception:
            pass

    # Relación
    m = P_REL.search(t)
    if m:
        fields["relacion_agresor"] = m.group(1)

    # Ubicación (spaCy si está, si no heurística por estados)
    if _NLP is not None:
        doc = _NLP(texto)
        # busca GPE/LOC que coincidan con estados MX
        for ent in doc.ents:
            if ent.label_ in ("LOC","GPE"):
                e = _norm(ent.text)
                if e in MEX_STATES:
                    fields["ubicacion_estado"] = ent.text
                    break
    if not fields["ubicacion_estado"]:
        # fallback simple: busca cualquier estado por texto
        for st in MEX_STATES:
            if st in t:
                fields["ubicacion_estado"] = st.title()
                break

    return fields

def rule_flag(text: str) -> bool:
    t = _norm(text)
    has_exp = bool(P_FEM.search(t))
    has_vic = bool(P_VICTIMA.search(t))
    has_evt = bool(P_EVENTO.search(t))
    has_neg = bool(P_NEG.search(t))
    ctx_only = bool(P_CONTEXTO.search(t)) and not has_exp
    return (has_exp or (has_vic and has_evt)) and (not has_neg) and (not ctx_only)

def annotate_feminicidios(df: pd.DataFrame, text_col: str = "contenido", title_col: str = "titulo",
                          threshold: float = 0.6) -> pd.DataFrame:
    if text_col not in df.columns:
        raise KeyError(f"No existe la columna de texto: {text_col}")
    texts = (df[title_col].fillna('') + ". " + df[text_col].fillna('')).astype(str)

    scores, evidencias, edades, menores, ubic, rels = [], [], [], [], [], []
    for txt in texts:
        sc, hits = score_feminicidio(txt)
        fields = extract_fields(txt)

        scores.append(sc)
        evidencias.append(", ".join(
            [f"fem:{'|'.join(hits['fem'])}" if hits['fem'] else "",
             f"victima:{'|'.join(hits['victima'])}" if hits['victima'] else "",
             f"evento:{'|'.join(hits['evento'])}" if hits['evento'] else "",
             f"rel:{'|'.join(hits['rel'])}" if hits['rel'] else "",
             f"neg:{'|'.join(hits['neg'])}" if hits['neg'] else "",
             f"contexto:{'|'.join(hits['contexto'])}" if hits['contexto'] else ""
            ]).strip(", ").replace(",,", ",")
        )
        edades.append(fields["victima_edad"])
        menores.append(fields["victima_menor"])
        ubic.append(fields["ubicacion_estado"])
        rels.append(fields["relacion_agresor"])

    df = df.copy()
    df["feminicidio_score"] = scores
    rule_flags = [rule_flag(t) for t in texts]
    df["feminicidio_flag"] = [
        "Sí" if (rf or sc >= threshold) else "No"
        for rf , sc in zip(rule_flags, scores)
    ]
    df["feminicidio_evidencia"] = evidencias
    df["victima_edad"] = edades
    df["victima_menor"] = menores
    df["ubicacion_estado"] = ubic
    df["relacion_agresor"] = rels
    return df

def filter_feminicidios(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve solo filas marcadas como feminicidio_probable."""
    if "feminicidio_flag" not in df.columns:
        return df.iloc[0:0]
    return df[df["feminicidio_flag"] == "Sí"].copy()


