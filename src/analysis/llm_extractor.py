# src/analysis/llm_extractor.py — Motor Unificado de Clasificación y Extracción con LLM (v8.0)
"""
Reemplaza el pipeline pesado de BETO (~440 MB) + spaCy (~550 MB) + BERTopic (~470 MB)
por un arquitectura de 2 etapas ligera, determinista en sus candados y sin falsos positivos:

  Etapa 1 — Pre-filtro de Admisión Rápido (`passes_admission_gate`):
    Verifica en < 1 ms sobre el texto completo que:
      a) No sea ruido evidente (deportes, finanzas, horóscopos, espectáculos).
      b) No sea una noticia internacional ajena a México.
      c) Exista DOBLE SEÑAL obligatoria en el cuerpo:
         [Señal 1: Muerte violenta de mujer] + [Señal 2: Maternidad / Hijos / NNA / DIF].
    El ~85-90% de las noticias irrelevantes se descartan aquí sin gastar un solo token.

  Etapa 2 — Auditoría con 5 Candados Anti-Falsos Positivos + Extracción Estructurada:
    Envía el artículo candidato a un LLM gratuito/ligero (Groq Llama-3.3-70B,
    Google Gemini 2.5 Flash, OpenRouter :free o Azure OpenAI) exigiendo un JSON
    validado con Pydantic (`CasoExtraidoSchema`) que evalúa 5 candados booleanos:
      1. candado_1_es_caso_concreto (No estadísticas, leyes, marchas ni opinión)
      2. candado_2_ocurrio_en_mexico (Hecho ocurrido en algún estado/municipio de México)
      3. candado_3_victima_mortal_es_mujer_madre (Víctima letal es mujer/madre, no niña sin hijos)
      4. candado_4_menor_no_es_el_agresor (Descarta matricidio donde el hijo asesina a la madre)
      5. candado_5_hay_nna_huerfanos_o_sobrevivientes (Existen menores que quedan en orfandad/desamparo)
         + `cita_textual_evidencia` verificada contra el texto original para impedir alucinaciones.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import unicodedata
from typing import Any, Literal, Optional

import requests
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _load_dotenv_if_present() -> None:
    """Carga variables de `.env` sin dependencias externas si no están ya en `os.environ`."""
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)
        return
    except ImportError:
        pass

    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".env",
    )
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key:
                        os.environ.setdefault(key, val)
        except Exception:
            pass


_load_dotenv_if_present()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. ESQUEMA ESTRICTO PYDANTIC CON LOS 5 CANDADOS ANTI-FALSOS POSITIVOS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CasoExtraidoSchema(BaseModel):
    """
    Esquema estructurado de auditoría y extracción en un solo paso.
    Compatible con los campos de `investigacion_json` del Dashboard y PostgreSQL.
    """

    # ── Los 5 Candados de Auditoría (Chain-of-Thought) ──────────────────────
    candado_1_es_caso_concreto: bool = Field(
        default=False,
        description=(
            "True SOLO si la noticia relata un crimen/feminicidio real de una mujer específica. "
            "False si son estadísticas (INEGI, SESNSP, REDIM), leyes/reformas (Ley Monzón), "
            "marchas, becas, programas de gobierno o columnas de opinión."
        ),
    )
    candado_2_ocurrio_en_mexico: bool = Field(
        default=False,
        description=(
            "True SOLO si el crimen ocurrió en territorio mexicano (cualquier estado o municipio de México). "
            "False si ocurrió en otro país (Colombia, Argentina, España, EE.UU., Perú, Centroamérica, etc.)."
        ),
    )
    candado_3_victima_mortal_es_mujer_madre: bool = Field(
        default=False,
        description=(
            "True SOLO si la persona asesinada (víctima mortal directa) era una mujer que tenía hijos/as "
            "o menores bajo su cuidado. False si la única víctima asesinada era una niña/menor sin hijos "
            "(feminicidio infantil sin huérfanos sobrevivientes) o si la víctima mortal era un hombre."
        ),
    )
    candado_4_menor_no_es_el_agresor: bool = Field(
        default=False,
        description=(
            "True SOLO si los hijos/menores son inocentes y sobrevivientes. "
            "False si el hijo o menor fue quien asesinó a la madre (matricidio/parricidio) "
            "sin que existan otros hermanos menores inocentes que hayan quedado en orfandad."
        ),
    )
    candado_5_hay_nna_huerfanos_o_sobrevivientes: bool = Field(
        default=False,
        description=(
            "True SOLO si el texto menciona explícita o implícitamente que la mujer asesinada dejó "
            "hijos/as menores de edad (niños, niñas, bebés o adolescentes) vivos en situación de "
            "orfandad, desamparo, que presenciaron el crimen, fueron sustraídos tras el crimen o "
            "quedaron bajo resguardo de familiares/DIF."
        ),
    )

    # ── Evidencia Textual Anti-Alucinaciones ────────────────────────────────
    cita_textual_evidencia: str = Field(
        default="",
        description=(
            "Oración o fragmento COPIADO TEXTUALMENTE de la noticia donde se menciona a los hijos, "
            "menores o situación de orfandad. Si no se menciona en el texto, dejar vacío ''."
        ),
    )
    motivo_descarte: Optional[str] = Field(
        default=None,
        description=(
            "Si alguno de los 5 candados es False, explica brevemente la razón exacta del descarte "
            "(ej. 'Estadística o ley', 'Matricidio', 'Víctima mortal es menor sin hijos', 'Otro país', "
            "'No menciona hijos huérfanos'). Si todos los candados son True, poner null."
        ),
    )

    # ── Clasificación y Confianza ───────────────────────────────────────────
    clasificacion: Literal["Alta", "Media", "No relevante"] = Field(
        default="No relevante",
        description=(
            "'Alta' si cumple los 5 candados con evidencia clara de menores huérfanos/sobrevivientes. "
            "'Media' si cumple los primeros 4 candados y sugiere que era madre pero sin detallar situación de los menores. "
            "'No relevante' si falla cualquiera de los candados."
        ),
    )
    confianza: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Nivel de certeza del análisis en rango [0.0, 1.0].",
    )

    # ── Datos Estructurados para Expediente / Dashboard (`investigacion_json`) ──
    estado: str = Field(
        default="No especificado",
        description="Estado de México donde ocurrió el caso (ej. 'Estado de México', 'Puebla', 'Jalisco', 'CDMX').",
    )
    municipio: str = Field(
        default="No especificado",
        description="Ciudad, municipio o alcaldía donde ocurrió el caso (ej. 'Ecatepec', 'Iztapalapa', 'León').",
    )
    ubicacion: str = Field(
        default="No especificada",
        description="Ubicación combinada en formato 'Municipio, Estado' (ej. 'Ecatepec, Estado de México').",
    )
    victimas: str = Field(
        default="No especificada",
        description="Nombre y edad de la madre/mujer asesinada si se menciona (ej. 'Mariana N., 28 años').",
    )
    ninos_afectados: int | str = Field(
        default=0,
        description="Número entero de NNA huérfanos/afectados (ej. 2) o texto ('Varios', 'Al menos 1', 0 si no aplica).",
    )
    edades: str = Field(
        default="No especificada",
        description="Edades de los NNA afectados si se mencionan (ej. '4 y 7 años', 'Bebé de 8 meses').",
    )
    situacion_actual: str = Field(
        default="No especificada",
        description=(
            "Situación actual reportada de los menores (ej. 'Bajo resguardo del DIF', "
            "'Al cuidado de abuelos maternos', 'Presenció el ataque', 'Sustraída tras el crimen')."
        ),
    )
    medios_contacto: str = Field(
        default="No especificado",
        description=(
            "Institución que atiende el caso o dependencia sugerida para seguimiento según la ubicación "
            "(ej. 'DIF Municipal de Ecatepec / FGJEM')."
        ),
    )
    resumen: str = Field(
        default="",
        description="Resumen conciso (máximo 120 palabras) del hecho y la situación de los menores.",
    )


def _sanitize_llm_json(raw_dict: Any) -> dict[str, Any]:
    """
    Sanitiza y normaliza las respuestas crudas de cualquier LLM (Groq, Gemini, etc.)
    antes de pasar por `CasoExtraidoSchema.model_validate`.

    Resuelve discrepancias comunes como:
      - `clasificacion: "Baja"` -> Mapeado a "Media" o "No relevante".
      - `clasificacion: null` -> Inferido a partir del estado de los 5 candados.
      - `ninos_afectados: null` -> Normalizado a 0.
      - Valores `null` en cadenas -> Convertidos a cadenas vacías o textos por defecto.
      - Valores booleanos representados como texto ("true", "si", "1") o enteros.
    """
    if not isinstance(raw_dict, dict):
        return {}

    d = dict(raw_dict)

    # 1. Sanitizar candados booleanos
    for bool_field in [
        "candado_1_es_caso_concreto",
        "candado_2_ocurrio_en_mexico",
        "candado_3_victima_mortal_es_mujer_madre",
        "candado_4_menor_no_es_el_agresor",
        "candado_5_hay_nna_huerfanos_o_sobrevivientes",
    ]:
        val = d.get(bool_field)
        if isinstance(val, bool):
            continue
        if isinstance(val, str):
            d[bool_field] = val.strip().lower() in ("true", "1", "si", "sí", "yes")
        elif isinstance(val, (int, float)):
            d[bool_field] = bool(val)
        else:
            d[bool_field] = False

    # 2. Sanitizar clasificacion (Literal['Alta', 'Media', 'No relevante'])
    clasif = d.get("clasificacion")
    c1 = d.get("candado_1_es_caso_concreto", False)
    c2 = d.get("candado_2_ocurrio_en_mexico", False)
    c3 = d.get("candado_3_victima_mortal_es_mujer_madre", False)
    c4 = d.get("candado_4_menor_no_es_el_agresor", False)
    c5 = d.get("candado_5_hay_nna_huerfanos_o_sobrevivientes", False)

    if not isinstance(clasif, str) or not clasif.strip():
        if c1 and c2 and c3 and c4:
            d["clasificacion"] = "Alta" if c5 else "Media"
        else:
            d["clasificacion"] = "No relevante"
    else:
        norm = clasif.strip()
        low = norm.lower()
        if low in ("alta", "alto"):
            d["clasificacion"] = "Alta"
        elif low in ("media", "medio"):
            d["clasificacion"] = "Media"
        elif low in ("baja", "bajo", "media baja", "baja media"):
            # Si el modelo clasifica 'Baja', si cumple candados es Media; si no, No relevante
            d["clasificacion"] = "Media" if (c1 and c2 and c3 and c4 and c5) else "No relevante"
        elif "no" in low or "descart" in low:
            d["clasificacion"] = "No relevante"
        else:
            d["clasificacion"] = "No relevante"

    # 3. Sanitizar ninos_afectados (int | str, nunca None)
    na = d.get("ninos_afectados")
    if na is None or na == "":
        d["ninos_afectados"] = 0
    elif isinstance(na, (int, float)):
        d["ninos_afectados"] = int(na)
    elif isinstance(na, str):
        na_str = na.strip()
        if na_str.isdigit():
            d["ninos_afectados"] = int(na_str)
        else:
            m = re.search(r"\d+", na_str)
            d["ninos_afectados"] = int(m.group(0)) if m else na_str

    # 4. Sanitizar confianza (float [0.0, 1.0])
    conf = d.get("confianza")
    try:
        if conf is None or conf == "":
            d["confianza"] = 0.88 if d.get("clasificacion") in ("Alta", "Media") else 0.05
        else:
            d["confianza"] = max(0.0, min(1.0, float(conf)))
    except (ValueError, TypeError):
        d["confianza"] = 0.50

    # 5. Sanitizar campos de texto (reemplazar None con valores seguros)
    text_defaults = [
        ("cita_textual_evidencia", ""),
        ("motivo_descarte", None),
        ("estado", "No especificado"),
        ("municipio", "No especificado"),
        ("ubicacion", "No especificada"),
        ("victimas", "No especificada"),
        ("edades", "No especificada"),
        ("situacion_actual", "No especificada"),
        ("medios_contacto", "No especificado"),
        ("resumen", ""),
    ]
    for field_name, default_val in text_defaults:
        val = d.get(field_name)
        if val is None:
            d[field_name] = default_val
        elif not isinstance(val, str):
            d[field_name] = str(val).strip()
        else:
            d[field_name] = val.strip()

    return d


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. PRE-FILTRO DE ADMISIÓN RÁPIDO (GATEKEEPER LÉXICO SOBRE TEXTO COMPLETO)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_NOISE_TITLE_PATTERNS = [
    re.compile(r"\b(?:liga\s+mx|f[uú]tbol|gol(?:es)?|partido|cl[aá]sico|liguilla|champions\s+league)\b", re.I),
    re.compile(r"\b(?:box|boxeador|ufc|nfl|nba|mlb|f[oó]rmula\s*1|gp\s+de\s+m[eé]xico)\b", re.I),
    re.compile(r"\b(?:hor[oó]scopo|signo\s+zodiacal|predicciones?\s+astrol)\b", re.I),
    re.compile(r"\b(?:receta\s+de|ingredientes\s+para|platillo|gastronom[ií]a)\b", re.I),
    re.compile(r"\b(?:clima\s+hoy|pron[oó]stico\s+del\s+tiempo|frente\s+fr[ií]o|onda\s+tropical)\b", re.I),
    re.compile(r"\b(?:d[oó]lar\s+hoy|tipo\s+de\s+cambio|bolsa\s+de\s+valores|wall\s+street|criptomoneda|bitcoin)\b", re.I),
    re.compile(r"\b(?:estrenos?\s+de\s+netflix|reality\s+show|concierto\s+de|gira\s+musical)\b", re.I),
]

# Señal 1 obligatoria: Violencia letal / feminicidio contra mujer
_SIGNAL_VIOLENCIA_MUJER = re.compile(
    r"\b("
    r"feminicid(?:io|ios|a|as)|femicid(?:io|ios)|violencia\s+feminicida|"
    r"asesin(?:an|ada|adas|aron|ó|ato)|"
    r"mat(?:an|aron|ó)\s+(?:a\s+)?(?:su\s+|una\s+|la\s+)?(?:mujer|madre|mam[aá]|esposa|pareja|novia|ex\s*pareja|joven|hija)|"
    r"mujer\s+(?:sin\s+vida|muerta|hallada|encontrada|baleada|ejecutada|ultimada|estrangulada|apu[ñn]alada|degollada|calcinada)|"
    r"madre\s+(?:sin\s+vida|muerta|asesinada|hallada|baleada|ejecutada|ultimada)|"
    r"hallan\s+(?:sin\s+vida|muerta|el\s+cuerpo\s+de)\s+(?:a\s+)?(?:una\s+)?(?:mujer|madre|joven)|"
    r"encuentran\s+(?:sin\s+vida|muerta)\s+(?:a\s+)?(?:una\s+)?(?:mujer|madre|joven)|"
    r"priv(?:an|ó|ada)\s+de\s+la\s+vida|"
    r"cuerpo\s+sin\s+vida\s+de\s+(?:una\s+)?(?:mujer|madre|joven)|"
    r"muerte\s+violenta\s+de\s+(?:una\s+)?mujer|"
    r"ultim(?:an|ada|aron)|ejecut(?:an|ada|aron)"
    r")\b",
    re.IGNORECASE,
)

# Indicadores geográficos de México (auto-contenidos, sin dependencias externas)
_MEXICO_PATTERN = re.compile(
    r"\b("
    r"m[eé]xico|mexican[oa]s?|cdmx|ciudad\s+de\s+m[eé]xico|estado\s+de\s+m[eé]xico|edomex|"
    r"aguascalientes|baja\s+california|campeche|chiapas|chihuahua|coahuila|colima|"
    r"durango|guanajuato|guerrero|hidalgo|jalisco|michoac[aá]n|morelos|nayarit|"
    r"nuevo\s+le[oó]n|oaxaca|puebla|quer[eé]taro|quintana\s+roo|san\s+luis\s+potos[ií]|"
    r"sinaloa|sonora|tabasco|tamaulipas|tlaxcala|veracruz|yucat[aá]n|zacatecas|"
    r"ecatepec|neza|nezahualc[oó]yotl|toluca|tlalnepantla|naucalpan|chimalhuac[aá]n|chalco|cuautitl[aá]n|"
    r"iztapalapa|tl[aá]huac|gustavo\s+a\.?\s+madero|cuauht[eé]moc|coyoac[aá]n|xochimilco|azcapotzalco|"
    r"guadalajara|zapopan|tlaquepaque|tonal[aá]|monterrey|apodaca|escobedo|tijuana|mexicali|ensenada|"
    r"ciudad\s+ju[aá]rez|ju[aá]rez|le[oó]n|celaya|irapuato|culiac[aá]n|mazatl[aá]n|canc[uú]n|acapulco|"
    r"chilpancingo|iguala|m[eé]rida|villahermosa|hermosillo|saltillo|torre[oó]n|tuxtla|tapachula|"
    r"xalapa|coatzacoalcos|poza\s+rica|tehuac[aá]n|reynosa|matamoros|nuevo\s+laredo|tampico|"
    r"pachuca|cuernavaca|tepic|chetumal|"
    r"fgjem|fgjcdmx|fgr|semefo|dif|sipinna|conavim|inmujeres|sesnsp|inegi"
    r")\b",
    re.IGNORECASE,
)

# Indicadores de países extranjeros (descarte cuando no hay contexto mexicano mayoritario)
_FOREIGN_PATTERN = re.compile(
    r"\b("
    r"colombia|bogot[aá]|medell[ií]n|cali\b(?!\s*fornia)|barranquilla|"
    r"argentina|buenos\s+aires|c[oó]rdoba\s+argentina|rosario|"
    r"espa[ñn]a|madrid|barcelona|sevilla|valencia|"
    r"per[uú]|lima|arequipa|chile|santiago\s+de\s+chile|valpara[ií]so|"
    r"venezuela|caracas|ecuador|quito|guayaquil|bolivia|paraguay|uruguay|montevideo|"
    r"brasil|s[aã]o\s+paulo|r[ií]o\s+de\s+janeiro|"
    r"el\s+salvador|guatemala|honduras|tegucigalpa|nicaragua|managua|costa\s+rica|"
    r"panam[aá]|rep[uú]blica\s+dominicana|santo\s+domingo|cuba|puerto\s+rico"
    r")\b",
    re.IGNORECASE,
)


def is_mexico_context(title: str, content: str, source_url: str = "") -> bool:
    """
    Determina de forma ultrarrápida y sin dependencias externas si una noticia
    pertenece al contexto geográfico de México.
    """
    title_str = title or ""
    content_str = content or ""
    mx_hits = len(_MEXICO_PATTERN.findall(title_str)) * 3 + len(_MEXICO_PATTERN.findall(content_str))
    foreign_hits = len(_FOREIGN_PATTERN.findall(title_str)) * 3 + len(_FOREIGN_PATTERN.findall(content_str))

    if foreign_hits > 0 and mx_hits == 0:
        return False
    if foreign_hits >= mx_hits and foreign_hits > 0:
        return False
    if mx_hits > 0:
        return True
    if source_url and ".mx" in source_url.lower() and "google" not in source_url.lower():
        return True
    return False

# Señal 2 obligatoria: Maternidad / Hijos / Menores / Orfandad / DIF
_SIGNAL_NNA_O_MATERNIDAD = re.compile(
    r"\b("
    r"hu[eé]rfan[oa]s?|orfandad|v[ií]ctimas?\s+indirectas?|v[ií]ctimas?\s+colaterales?|"
    r"hij[oa]s?|ni[ñn][oa]s?|menor(?:es)?|beb[eé]s?|adolescentes?|infantes?|peque[ñn][oa]s?|"
    r"madre\s+de|mam[aá]\s+de|dej[oó]\s+en\s+la\s+orfandad|qued(?:an|aron|ó)\s+sin\s+madre|"
    r"frente\s+a\s+sus?\s+|delante\s+de\s+sus?\s+|"
    r"resguardo\s+del?\s+dif|procuradur[ií]a\s+de\s+protecci[oó]n|casa\s+hogar|custodia|abuelos?\s+maternos?|"
    r"nna"
    r")\b",
    re.IGNORECASE,
)

# Patrones de Falso Positivo inequívoco en el título (cuando NO hay señal de caso individual)
_CLEAR_STATS_OR_LAW_TITLE = re.compile(
    r"\b("
    r"iniciativa\s+de\s+(?:ley|reforma)|aprueban?\s+(?:ley|reforma)|ley\s+monz[oó]n|"
    r"congreso\s+(?:aprueba|discute|propone)|senado\s+aprueba|"
    r"cifras?\s+del?\s+(?:sesnsp|inegi|snsp)|estad[ií]sticas?\s+de\s+feminicidio|"
    r"informe\s+(?:anual|trimestral|nacional)|encuesta\s+nacional|"
    r"convocan\s+a\s+marcha|marcha\s+del\s+8m"
    r")\b",
    re.IGNORECASE,
)

# Patrón de matricidio evidente en el título ("Hijo mata/asesina/apuñala a su madre")
_MATRICIDIO_TITLE = re.compile(
    r"\b(?:hijo|hija|joven|sujeto|adolescente)\s+(?:de\s+\d+\s+a[ñn]os\s+)?(?:mata|mat[oó]|asesina|asesin[oó]|apu[ñn]ala|apu[ñn]al[oó]|estrangula|estrangul[oó]|balea|bale[oó]|quita\s+la\s+vida)\s+a\s+su\s+(?:propia\s+)?(?:madre|mam[aá]|progenitora)\b",
    re.IGNORECASE,
)


def _normalize_plain(text: str) -> str:
    """Normaliza texto a minúsculas sin marcas diacríticas combinantes para comparaciones."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def passes_admission_gate(
    title: str,
    content: str,
    source_url: str = "",
) -> tuple[bool, str]:
    """
    Pre-filtro de admisión ultra-rápido (< 1 ms) sobre título + cuerpo completo.

    Determina si vale la pena enviar el artículo al LLM.
    Garantiza alto Recall para casos reales mientras descarta ~85-90% de ruido.

    Returns:
        (pasa: bool, razon: str)
    """
    title_str = (title or "").strip()
    content_str = (content or "").strip()
    combined = f"{title_str} {content_str}".strip()

    if len(combined) < 25:
        return False, "Texto vacío o demasiado corto"

    # 1. Ruido temático evidente en el título
    for pat in _NOISE_TITLE_PATTERNS:
        if pat.search(title_str):
            return False, "Ruido temático en título (deportes/finanzas/entretenimiento)"

    # 2. Matricidio explícito en el título (hijo asesina a su madre) sin mención de orfandad de hermanos
    if _MATRICIDIO_TITLE.search(title_str) and not re.search(r"\b(?:orfandad|hu[eé]rfan|hermanit[oa]s?)\b", combined, re.I):
        return False, "Matricidio detectado en título (el hijo es el agresor)"

    # 3. Filtro geográfico de México (auto-contenido y sin dependencias externas)
    if not is_mexico_context(title_str, content_str, source_url):
        return False, "Noticia internacional (fuera de México)"

    # 4. Si el título es puramente sobre una reforma de ley/estadística y no menciona caso individual
    if _CLEAR_STATS_OR_LAW_TITLE.search(title_str):
        if not re.search(r"\b(?:fue\s+asesinada|hallada\s+sin\s+vida|dej[oó]\s+a\s+sus?\s+(?:\d+\s+)?hijos?)\b", content_str, re.I):
            return False, "Nota legislativa o estadística sin caso individual"

    # 5. Doble señal obligatoria en el texto completo
    has_violence = bool(_SIGNAL_VIOLENCIA_MUJER.search(combined))
    if not has_violence:
        return False, "Sin señal de muerte violenta de mujer / feminicidio"

    has_nna = bool(_SIGNAL_NNA_O_MATERNIDAD.search(combined))
    if not has_nna:
        return False, "Sin mención a hijos, menores, maternidad u orfandad"

    return True, "Candidata válida para auditoría LLM"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. VALIDADOR DETERMINISTA DE LOS 5 CANDADOS (EN PYTHON)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _verify_quote_in_text(quote: str, full_text: str) -> bool:
    """
    Verifica que la `cita_textual_evidencia` proporcionada por el LLM realmente
    provenga del artículo original y no sea una alucinación inventada.

    Comprueba que al menos el 55% de las palabras significativas (≥ 4 letras)
    de la cita aparezcan en el texto original normalizado.
    """
    if not quote or len(quote.strip()) < 8:
        return False

    norm_quote = _normalize_plain(quote)
    if norm_quote in ("no especificado", "no especificada", "ninguna", "n/a", "null", "none", "sin evidencia"):
        return False

    norm_text = _normalize_plain(full_text)

    # Si la subcadena exacta está presente, pasa directo
    if norm_quote in norm_text:
        return True

    # Verificar solapamiento de palabras significativas (≥ 4 caracteres)
    words = [w for w in re.findall(r"[a-z0-9]{4,}", norm_quote)]
    if not words:
        return False

    matched = sum(1 for w in words if w in norm_text)
    ratio = matched / len(words)
    return ratio >= 0.55


def aplicar_candados_estrictos(
    extracted: CasoExtraidoSchema,
    title: str,
    content: str,
) -> dict[str, Any]:
    """
    Aplica los 5 candados de forma determinista en Python sobre la respuesta del LLM.
    Incluso si el LLM intentara clasificar como 'Alta' una noticia que viola un candado,
    esta función fuerza su descarte a 'No relevante'.

    Retorna un diccionario unificado con:
      - Todas las columnas requeridas por `SimplifiedNewsAnalyzer` y `Noticia` en PostgreSQL
      - El diccionario `investigacion_json` listo para persistirse en la base de datos
    """
    full_text = f"{title or ''} {content or ''}".strip()

    c1 = bool(extracted.candado_1_es_caso_concreto)
    c2 = bool(extracted.candado_2_ocurrio_en_mexico)
    c3 = bool(extracted.candado_3_victima_mortal_es_mujer_madre)
    c4 = bool(extracted.candado_4_menor_no_es_el_agresor)
    c5 = bool(extracted.candado_5_hay_nna_huerfanos_o_sobrevivientes)

    razones_fallo: list[str] = []
    if not c1:
        razones_fallo.append("Falla Candado 1: No es un caso individual concreto (es estadística, ley, marcha u opinión)")
    if not c2:
        razones_fallo.append("Falla Candado 2: El hecho no ocurrió en México")
    if not c3:
        razones_fallo.append("Falla Candado 3: La víctima mortal no es una mujer/madre (ej. víctima directa es menor sin hijos o es hombre)")
    if not c4:
        razones_fallo.append("Falla Candado 4: El menor/hijo es el agresor (matricidio)")
    if not c5:
        razones_fallo.append("Falla Candado 5: No hay evidencia de NNA sobrevivientes o en orfandad")

    # Verificar que la cita textual exista en el texto original
    quote_valid = _verify_quote_in_text(extracted.cita_textual_evidencia, full_text)

    if razones_fallo:
        # Cualquier candado roto → Descarte absoluto a No relevante
        clasificacion_final = "No relevante"
        score_semantico = 0.05
        score_fem = 0.60 if (c1 and c3) else 0.10
        score_nna = 0.05
        score_v_ind = 0.0
        menores_identificados = "No"
        nna_victima_indirecta = "No"
        motivo = extracted.motivo_descarte or "; ".join(razones_fallo)
    else:
        # Cumple los 5 candados booleanos
        if quote_valid:
            clasificacion_final = "Alta" if extracted.clasificacion != "Media" else "Media"
            score_semantico = max(float(extracted.confianza or 0.85), 0.85) if clasificacion_final == "Alta" else 0.65
            score_fem = 0.95
            score_nna = 0.95
            score_v_ind = 0.95
            menores_identificados = "Si"
            nna_victima_indirecta = "Si"
            motivo = None
        else:
            # Cumple los 5 candados según el LLM pero no pudo extraer una cita verificable del texto
            # (Por ejemplo, cuando el snippet es muy corto y solo sugiere el caso) → Degradar a Media
            clasificacion_final = "Media"
            score_semantico = 0.50
            score_fem = 0.75
            score_nna = 0.50
            score_v_ind = 0.45
            menores_identificados = "Si"
            nna_victima_indirecta = "Si"
            motivo = "Cumple candados pero requiere verificar cita textual en fuente completa"

    # Normalizar ubicación para el dashboard
    ubicacion = extracted.ubicacion
    if not ubicacion or ubicacion.lower() in ("no especificada", "no especificado"):
        partes = [
            p for p in (extracted.municipio, extracted.estado)
            if p and p.lower() not in ("no especificado", "no especificada")
        ]
        ubicacion = ", ".join(partes) if partes else "No especificada"

    investigacion_data = {
        "ubicacion": ubicacion,
        "estado": extracted.estado or "No especificado",
        "municipio": extracted.municipio or "No especificado",
        "victimas": extracted.victimas or "No especificada",
        "ninos_afectados": extracted.ninos_afectados if extracted.ninos_afectados is not None else 0,
        "edades": extracted.edades or "No especificada",
        "situacion_actual": extracted.situacion_actual or "No especificada",
        "medios_contacto": extracted.medios_contacto or "No especificado",
        "resumen": extracted.resumen or "",
        "cita_textual_evidencia": extracted.cita_textual_evidencia or "",
        "candados": {
            "candado_1_es_caso_concreto": c1,
            "candado_2_ocurrio_en_mexico": c2,
            "candado_3_victima_mortal_es_mujer_madre": c3,
            "candado_4_menor_no_es_el_agresor": c4,
            "candado_5_hay_nna_huerfanos_o_sobrevivientes": c5,
            "cita_verificada_en_texto": quote_valid,
        },
        "motivo_descarte": motivo,
        "clasificacion": clasificacion_final,
        "confianza": round(score_semantico, 4),
    }

    return {
        "score_semantico": round(score_semantico, 4),
        "score_feminicidio": round(score_fem, 4),
        "score_nna": round(score_nna, 4),
        "score_victima_indirecta": round(score_v_ind, 4),
        "score_compuesto": round(score_semantico, 4),
        "relevancia_final": round(score_semantico, 4),
        "clasificacion": clasificacion_final,
        "clasificacion_final": clasificacion_final,
        "es_relevante": clasificacion_final in ("Alta", "Media"),
        "menores_identificados": menores_identificados,
        "nna_victima_indirecta": nna_victima_indirecta,
        "confianza": "alta" if score_semantico >= 0.75 else ("media" if score_semantico >= 0.45 else "alta"),
        "motivo_descarte": motivo,
        "investigacion_json": investigacion_data if clasificacion_final in ("Alta", "Media") else None,
        "auditoria_completa": investigacion_data,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. MOTOR DE EXTRACCIÓN MULTI-PROVEEDOR (GROQ / GEMINI / OPENROUTER / AZURE)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SYSTEM_PROMPT_AUDITOR = """Eres un auditor forense y analista especializado en derechos de la niñez (NNA) en México.
Tu objetivo es analizar noticias periodísticas para detectar ÚNICAMENTE casos reales ocurridos en México donde una mujer fue víctima de feminicidio (o homicidio violento) y, como consecuencia, sus hijos o hijas menores de edad (niños, niñas, bebés o adolescentes) quedaron en situación de orfandad, desamparo, presenciaron el crimen, fueron sustraídos o quedaron bajo resguardo del DIF o familiares.

REGLAS ESTRICTAS DE AUDITORÍA (LOS 5 CANDADOS ANTI-FALSOS POSITIVOS):
1. `candado_1_es_caso_concreto`: Pon `false` si la nota habla de estadísticas generales (INEGI, SESNSP, REDIM), discusiones legislativas (Ley Monzón, reformas en congresos), marchas del 8M, entrega general de becas/apoyos o columnas de opinión sin relatar el asesinato específico de una mujer.
2. `candado_2_ocurrio_en_mexico`: Pon `false` si el crimen ocurrió en otro país (Colombia, Argentina, España, EE.UU., Perú, Venezuela, etc.), incluso si fue publicado por un periódico mexicano.
3. `candado_3_victima_mortal_es_mujer_madre`: Pon `false` si la ÚNICA persona asesinada es una niña, bebé o adolescente que NO tenía hijos propios (es decir, feminicidio infantil donde la menor es la víctima mortal directa y no hay hijos huérfanos). Pon `true` si fue asesinada una madre/mujer dejando hijos menores vivos (incluso si en el mismo ataque también murió otro familiar, siempre que haya al menos un menor sobreviviente/huérfano).
4. `candado_4_menor_no_es_el_agresor`: Pon `false` si el hijo o hija fue quien mató a su propia madre (matricidio/parricidio) y no existen otros hermanos menores inocentes en orfandad.
5. `candado_5_hay_nna_huerfanos_o_sobrevivientes`: Pon `true` SOLO si el texto indica que la víctima tenía hijos/as menores que le sobreviven (ej. "dejó dos hijos en la orfandad", "era madre de tres pequeños", "fue asesinada frente a su hijo de 5 años", "DIF resguardó a los menores", "su bebé fue robado tras el asesinato").
6. `cita_textual_evidencia`: DEBES copiar palabra por palabra la oración exacta de la noticia que demuestra el candado 5. Si la noticia NO menciona hijos sobrevivientes/huérfanos, deja `cita_textual_evidencia` como cadena vacía `""` y `candado_5_hay_nna_huerfanos_o_sobrevivientes` en `false`. NUNCA inventes citas que no estén en el texto.

Devuelve ÚNICAMENTE un objeto JSON válido con la estructura exacta solicitada, sin bloques markdown adicionales."""


class LLMExtractor:
    """
    Cliente unificado multi-proveedor con rotación automática (Fallback) y caché en memoria.

    Orden de prioridad automático (según las llaves presentes en el entorno):
      1. Groq Cloud (`GROQ_API_KEY`) — 100% gratis, ultra rápido (`llama-3.3-70b-versatile`)
      2. Google Gemini (`GEMINI_API_KEY`) — gratis en Google AI Studio (`gemini-2.5-flash`)
      3. OpenRouter (`OPENROUTER_API_KEY`) — modelos `:free` (`meta-llama/llama-3.3-70b-instruct:free`)
      4. Azure OpenAI / OpenAI (`AZURE_OPENAI_API_KEY` o `OPENAI_API_KEY`) — para producción en Azure
      5. Fallback Determinista Local — si no hay ninguna API key configurada o no hay red.
    """

    def __init__(self, preferred_provider: Optional[str] = None):
        self.preferred_provider = (
            preferred_provider
            or os.environ.get("LLM_PROVIDER", "auto").strip().lower()
        )
        self._cache: dict[str, dict[str, Any]] = {}
        self.providers = self._discover_providers()

    def _discover_providers(self) -> list[dict[str, str]]:
        """Detecta todos los proveedores configurados en variables de entorno."""
        available: list[dict[str, str]] = []

        groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        if groq_key:
            available.append({
                "name": "groq",
                "api_key": groq_key,
                "model": os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
                "base_url": "https://api.groq.com/openai/v1/chat/completions",
            })

        gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if gemini_key:
            available.append({
                "name": "gemini",
                "api_key": gemini_key,
                "model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            })

        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if openrouter_key:
            available.append({
                "name": "openrouter",
                "api_key": openrouter_key,
                "model": os.environ.get(
                    "OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"
                ),
                "base_url": "https://openrouter.ai/api/v1/chat/completions",
            })

        azure_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
        if azure_key and azure_endpoint:
            deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
            api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
            base_url = (
                f"{azure_endpoint.rstrip('/')}/openai/deployments/"
                f"{deployment}/chat/completions?api-version={api_version}"
            )
            available.append({
                "name": "azure_openai",
                "api_key": azure_key,
                "model": deployment,
                "base_url": base_url,
            })

        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if openai_key:
            available.append({
                "name": "openai",
                "api_key": openai_key,
                "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                "base_url": "https://api.openai.com/v1/chat/completions",
            })

        # Si el usuario especificó un proveedor preferido, ponerlo al frente
        if self.preferred_provider and self.preferred_provider != "auto":
            available.sort(
                key=lambda p: 0 if p["name"] == self.preferred_provider else 1
            )

        return available

    @staticmethod
    def _build_user_prompt(title: str, content: str, source_url: str = "") -> str:
        schema_example = {
            "candado_1_es_caso_concreto": True,
            "candado_2_ocurrio_en_mexico": True,
            "candado_3_victima_mortal_es_mujer_madre": True,
            "candado_4_menor_no_es_el_agresor": True,
            "candado_5_hay_nna_huerfanos_o_sobrevivientes": True,
            "cita_textual_evidencia": "Frase exacta copiada del artículo",
            "motivo_descarte": None,
            "clasificacion": "Alta",
            "confianza": 0.95,
            "estado": "Estado de México",
            "municipio": "Ecatepec",
            "ubicacion": "Ecatepec, Estado de México",
            "victimas": "Nombre de la víctima, edad",
            "ninos_afectados": 2,
            "edades": "4 y 7 años",
            "situacion_actual": "Bajo resguardo del DIF / familiares",
            "medios_contacto": "DIF Municipal / Fiscalía Estatal",
            "resumen": "Resumen breve del caso y situación de los menores.",
        }
        return (
            f"Analiza la siguiente noticia y responde ESTRICTAMENTE en JSON con estas claves exactas:\n"
            f"{json.dumps(schema_example, ensure_ascii=False)}\n\n"
            f"--- DATOS DE LA NOTICIA ---\n"
            f"URL / Fuente: {source_url or 'No especificada'}\n"
            f"TÍTULO: {title}\n"
            f"CONTENIDO COMPLETO:\n{(content or '')[:6000]}\n"
        )

    def _call_openai_compatible(
        self,
        provider: dict[str, str],
        title: str,
        content: str,
        source_url: str = "",
    ) -> dict[str, Any]:
        """Llama a Groq, OpenRouter, Azure OpenAI u OpenAI usando formato Chat Completions JSON."""
        headers = {
            "Content-Type": "application/json",
        }
        if provider["name"] == "azure_openai":
            headers["api-key"] = provider["api_key"]
        else:
            headers["Authorization"] = f"Bearer {provider['api_key']}"

        payload: dict[str, Any] = {
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_AUDITOR},
                {"role": "user", "content": self._build_user_prompt(title, content, source_url)},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        max_retries = 2
        for attempt in range(max_retries + 1):
            resp = requests.post(
                provider["base_url"],
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code == 429:
                if attempt < max_retries:
                    backoff = 2.0 * (attempt + 1)
                    logger.warning(
                        "[LLMExtractor] 429 Rate limit en proveedor '%s'. Reintentando en %.1fs (intento %d/%d)...",
                        provider["name"],
                        backoff,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(backoff)
                    continue
                raise RuntimeError(f"Rate limit (429) persistente en proveedor {provider['name']}")
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            return self._parse_json_response(raw_text)

        raise RuntimeError(f"Fallo de conexión tras reintentos con {provider['name']}")

    def _call_gemini(
        self,
        provider: dict[str, str],
        title: str,
        content: str,
        source_url: str = "",
    ) -> dict[str, Any]:
        """Llama a Google Gemini API con esquema estructurado."""
        model_name = provider["model"]
        api_key = provider["api_key"]
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent?key={api_key}"
        )
        payload = {
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT_AUDITOR}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": self._build_user_prompt(title, content, source_url)}],
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }

        max_retries = 2
        for attempt in range(max_retries + 1):
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 429:
                if attempt < max_retries:
                    backoff = 2.0 * (attempt + 1)
                    logger.warning(
                        "[LLMExtractor] 429 Rate limit en proveedor gemini. Reintentando en %.1fs (intento %d/%d)...",
                        backoff,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(backoff)
                    continue
                raise RuntimeError("Rate limit (429) persistente en proveedor gemini")
            resp.raise_for_status()
            data = resp.json()
            raw_text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "{}")
            )
            return self._parse_json_response(raw_text)

        raise RuntimeError("Fallo de conexión tras reintentos con gemini")

        data = resp.json()
        raw_text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "{}")
        )
        return self._parse_json_response(raw_text)

    @staticmethod
    def _parse_json_response(raw_text: str) -> dict[str, Any]:
        """Limpia bloques markdown si existen y parsea el JSON."""
        cleaned = (raw_text or "").strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # En caso de texto extra alrededor del JSON, extraer desde primera '{' hasta última '}'
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]

        return json.loads(cleaned)

    # ── Motor Fallback Determinista Local (sin API keys o sin red) ──────────

    @staticmethod
    def _deterministic_fallback_extract(
        title: str,
        content: str,
        source_url: str = "",
    ) -> CasoExtraidoSchema:
        """
        Analizador determinista de respaldo que evalúa los 5 candados mediante
        reglas sintácticas/léxicas estrictas cuando no hay ninguna API key configurada.
        """
        full_text = f"{title or ''}. {content or ''}".strip()

        # Verificar filtro geográfico México
        is_mexico = is_mexico_context(title or "", content or "", source_url)

        # Candado 1: ¿Es caso concreto y NO estadística/ley/opinión?
        is_stats_or_law = bool(
            re.search(
                r"\b(?:cifras?\s+de\s+feminicidio|estad[ií]sticas?\s+de|informe\s+anual|"
                r"iniciativa\s+de\s+ley|ley\s+monz[oó]n|congreso\s+aprueba|senado\s+aprueba|"
                r"entrega\s+de\s+becas|columna\s+de\s+opini[oó]n|editorial)\b",
                full_text,
                re.I,
            )
        )
        has_concrete_crime = bool(_SIGNAL_VIOLENCIA_MUJER.search(full_text))
        c1_caso_concreto = has_concrete_crime and not is_stats_or_law

        # Candado 4: ¿El menor NO es el agresor (matricidio)?
        is_matricidio = bool(
            _MATRICIDIO_TITLE.search(full_text)
            or re.search(
                r"\b(?:su\s+)?(?:hijo|hija|menor|adolescente)\s+(?:la\s+)?(?:mat[oó]|asesin[oó]|apu[ñn]al[oó]|estrangul[oó]|priv[oó]\s+de\s+la\s+vida)\b",
                full_text,
                re.I,
            )
            or re.search(
                r"\basesinada\s+por\s+su\s+(?:propio\s+)?(?:hijo|hija)\b",
                full_text,
                re.I,
            )
        )
        c4_menor_no_agresor = not is_matricidio

        # Candado 5: Oración con evidencia de NNA huérfano / sobreviviente
        patron_evidencia_nna = re.compile(
            r"([^.!?]*?\b(?:"
            r"hu[eé]rfan[oa]s?|orfandad|"
            r"dej[oó]\s+(?:a\s+)?(?:sus?\s+)?(?:\d+|dos|tres|cuatro|cinco|varios)?\s*(?:hijos?|hijas?|menores?|ni[ñn][oa]s?|peque[ñn][oa]s?)|"
            r"(?:era\s+)?madre\s+de\s+(?:\d+|dos|tres|cuatro|cinco)\s+(?:hijos?|hijas?|menores?|ni[ñn][oa]s?|peque[ñn][oa]s?)|"
            r"frente\s+a\s+sus?\s+(?:\d+|dos|tres\s+)?(?:hijos?|hijas?|menores?|ni[ñn][oa]s?)|"
            r"(?:menor(?:es)?|hijos?|hijas?|ni[ñn][oa]s?|beb[eé])\s+(?:qued(?:aron|an|ó)|presenci(?:ó|aron)|bajo\s+resguardo|en\s+orfandad|al\s+cuidado\s+de|fue\s+sustra[ií]d[oa]|fue\s+robad[oa])|"
            r"resguardo\s+del?\s+dif|entregad[oa]s?\s+al?\s+dif"
            r")\b[^.!?]*[.!?]?)",
            re.IGNORECASE,
        )
        evidencia_match = patron_evidencia_nna.search(full_text)
        cita_evidencia = evidencia_match.group(1).strip() if evidencia_match else ""
        c5_hay_nna_huerfanos = bool(cita_evidencia)

        # Candado 3: ¿La víctima mortal es una mujer adulta/madre y NO únicamente una niña sin hijos?
        is_direct_child_victim = bool(
            re.search(
                r"\b(?:feminicidio|asesinato|homicidio)\s+de\s+(?:una\s+|la\s+)?(?:ni[ñn]a|menor|beb[eé]|adolescente|su\s+hija)\b|"
                r"\b(?:ni[ñn]a|menor|beb[eé])\s+de\s+\d+\s+(?:a[ñn]os|meses)\s+(?:fue\s+)?(?:asesinada|hallada\s+sin\s+vida|encontrada\s+muerta)\b",
                full_text,
                re.I,
            )
        )
        c3_victima_madre = has_concrete_crime and (not is_direct_child_victim or c5_hay_nna_huerfanos)

        all_ok = c1_caso_concreto and is_mexico and c3_victima_madre and c4_menor_no_agresor and c5_hay_nna_huerfanos

        motivo = None
        if not all_ok:
            if not is_mexico:
                motivo = "Ocurrió fuera de México"
            elif not c4_menor_no_agresor:
                motivo = "Matricidio (el hijo/menor es el agresor)"
            elif not c3_victima_madre:
                motivo = "La víctima mortal directa es una menor sin hijos en orfandad"
            elif not c1_caso_concreto:
                motivo = "Estadística, legislación o nota sin caso concreto"
            else:
                motivo = "No menciona hijos menores que hayan quedado en orfandad"

        return CasoExtraidoSchema(
            candado_1_es_caso_concreto=c1_caso_concreto,
            candado_2_ocurrio_en_mexico=is_mexico,
            candado_3_victima_mortal_es_mujer_madre=c3_victima_madre,
            candado_4_menor_no_es_el_agresor=c4_menor_no_agresor,
            candado_5_hay_nna_huerfanos_o_sobrevivientes=c5_hay_nna_huerfanos,
            cita_textual_evidencia=cita_evidencia if all_ok else "",
            motivo_descarte=motivo,
            clasificacion="Alta" if all_ok else "No relevante",
            confianza=0.88 if all_ok else 0.05,
            resumen=(title or "")[:200],
        )

    # ── Punto de Entrada Principal para Clasificar y Extraer ────────────────

    def analyze_article(
        self,
        title: str,
        content: str,
        source_url: str = "",
        force_fallback: bool = False,
    ) -> dict[str, Any]:
        """
        Analiza una noticia completa aplicando:
          1. Pre-filtro rápido `passes_admission_gate` (< 1 ms, 0 tokens).
          2. Auditoría LLM con rotación de proveedores gratuitos (o fallback determinista).
          3. Validación estricta de los 5 candados en Python (`aplicar_candados_estrictos`).
        """
        title_str = (title or "").strip()
        content_str = (content or "").strip()

        # Cache por hash MD5 de título + primeros 1000 chars de contenido
        cache_key = hashlib.md5(
            f"{title_str.lower()}|{content_str[:1000].lower()}".encode("utf-8", errors="ignore")
        ).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        # ── Etapa 1: Pre-filtro de Admisión Rápido ──────────────────────────
        passed_gate, gate_reason = passes_admission_gate(title_str, content_str, source_url)
        if not passed_gate:
            result = {
                "score_semantico": 0.0,
                "score_feminicidio": 0.0,
                "score_nna": 0.0,
                "score_victima_indirecta": 0.0,
                "score_compuesto": 0.0,
                "relevancia_final": 0.0,
                "clasificacion": "No relevante",
                "clasificacion_final": "No relevante",
                "es_relevante": False,
                "menores_identificados": "No",
                "nna_victima_indirecta": "No",
                "confianza": "alta",
                "modo": "admission_gate_rejected",
                "motivo_descarte": gate_reason,
                "investigacion_json": None,
            }
            self._cache[cache_key] = result
            return result

        # ── Etapa 2: Auditoría LLM con rotación de proveedores ──────────────
        extracted_schema: Optional[CasoExtraidoSchema] = None
        provider_used = "deterministic_fallback"

        if not force_fallback:
            for provider in self.providers:
                try:
                    if provider["name"] == "gemini":
                        raw_dict = self._call_gemini(provider, title_str, content_str, source_url)
                    else:
                        raw_dict = self._call_openai_compatible(provider, title_str, content_str, source_url)

                    sanitized = _sanitize_llm_json(raw_dict)
                    extracted_schema = CasoExtraidoSchema.model_validate(sanitized)
                    provider_used = f"llm_{provider['name']}:{provider['model']}"
                    break
                except Exception as exc:
                    logger.warning(
                        "[LLMExtractor] Proveedor '%s' falló (%s). Probando siguiente proveedor...",
                        provider["name"],
                        exc,
                    )
                    continue

        if extracted_schema is None:
            extracted_schema = self._deterministic_fallback_extract(title_str, content_str, source_url)
            if force_fallback:
                provider_used = "deterministic_fallback_budget_reached"

        # ── Etapa 3: Validación Determinista de los 5 Candados en Python ────
        final_result = aplicar_candados_estrictos(extracted_schema, title_str, content_str)
        final_result["modo"] = provider_used
        if final_result.get("investigacion_json") is not None:
            final_result["investigacion_json"]["metodo"] = provider_used

        self._cache[cache_key] = final_result
        return final_result

    def analyze_batch(
        self,
        titles: list[str],
        contents: list[str],
        urls: Optional[list[str]] = None,
        delay_between_llm_calls: float = 1.2,
        max_llm_calls: int = 25,
    ) -> list[dict[str, Any]]:
        """
        Analiza un lote de noticias aplicando:
          1. Gatekeeper ultra-rápido (< 1 ms).
          2. Presupuesto de llamadas LLM (max_llm_calls) para respetar límites de cuota gratuita.
          3. Pausa adaptativa entre llamadas consecutivas a Groq/Gemini para evitar HTTP 429.
        """
        n = len(titles)
        if urls is None:
            urls = [""] * n

        results: list[dict[str, Any]] = []
        llm_calls = 0

        for idx in range(n):
            force_fallback = (llm_calls >= max_llm_calls)
            res = self.analyze_article(
                titles[idx],
                contents[idx],
                urls[idx],
                force_fallback=force_fallback,
            )
            results.append(res)

            if res.get("modo", "").startswith("llm_"):
                llm_calls += 1
                if delay_between_llm_calls > 0 and idx < n - 1:
                    time.sleep(delay_between_llm_calls)

        logger.info(
            "[LLMExtractor] Lote de %d noticias procesado (%d llamadas a LLM, %d filtradas por gatekeeper/presupuesto).",
            n,
            llm_calls,
            n - llm_calls,
        )
        return results
