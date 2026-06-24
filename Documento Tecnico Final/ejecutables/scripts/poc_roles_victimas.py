"""
scripts/poc_roles_victimas.py
─────────────────────────────────────────────────────────────────
PoC: Extracción de Roles Víctima/Agresor/Menor con spaCy
─────────────────────────────────────────────────────────────────
Objetivo: Determinar si una noticia de feminicidio corresponde
al caso de interés: mujer adulta = víctima FATAL + menor = entidad
separada que sobrevive / queda huérfana.

Hipótesis central:
  Si los TÉRMINOS DE MENOR (hijo, niña, bebé…) aparecen como SUJETO
  de verbos de supervivencia/orfandad (quedar, sobrevivir, rescatar)
  y los TÉRMINOS DE MUJER/MADRE aparecen como OBJETO de verbos
  de violencia (matar, asesinar, privar de la vida…), entonces
  se cumple el patrón de víctima indirecta NNA.

  El caso opuesto (menor como objeto de verbo de violencia) es
  un FALSO POSITIVO que este módulo rechaza.

Correcciones v2:
  [Fix-1] L3 léxico: las palabras sueltas (señales_lex) solo suman
          si L1 ya detectó al menos un verbo de violencia en el texto.
          Los patrones multipalabra (patrones_mp) siguen disparando solos.
  [Fix-2] VERBOS_SUPERVIVENCIA amplíado: presenciar, resguardar,
          testificar. L1b también captura construcciones pasivas buscando
          el participio auxiliado por "ser/estar" + sujeto menor.
  [Fix-3] L2 descarta tokens cuya dep_ sea 'obl:agent' o cuyo head
          inmediato sea la preposición "por", ya que son los AGENTES
          de la voz pasiva (victimarios), no las víctimas.

Parche v3 (robustez del parser):
  [Fix-4] _es_agente_pasivo amplíado: spaCy a veces etiqueta el agente
          pasivo como 'obl' o 'nmod' en lugar de 'obl:agent'. Se añade
          detección por hijo izquierdo con texto "por" (dep_ == 'case')
          para cubrir estos casos de forma dep-agnostic.
  [Fix-5] Retorno forzado True: si un patron_mp FUERTE hace match
          (implica la presencia confirmada del menor) y L2 está limpio,
          se acepta el caso aunque L1a no logró extraer a la mujer como
          objeto directo en el árbol de dependencias.

Dependencias:
    pip install spacy
    python -m spacy download es_core_news_lg
"""

import unicodedata
import re
from typing import Optional

import spacy
from spacy.tokens import Doc, Token, Span


# ═══════════════════════════════════════════════════════════════
# CONSTANTES DE DOMINIO
# ═══════════════════════════════════════════════════════════════

# Términos que denotan a una mujer adulta (posible víctima directa)
TERMINOS_MUJER = {
    "mujer", "madre", "mamá", "mama", "señora", "señorita", "esposa",
    "pareja", "victima", "víctima", "fallecida", "occisa",
}

# Términos que denotan un menor de edad (posible víctima indirecta / NNA)
TERMINOS_MENOR = {
    "hijo", "hija", "niño", "niña", "bebe", "bebé", "infante",
    "menor", "adolescente", "pequeño", "pequeña", "criatura",
    "huerfano", "huérfano", "huerfana", "huérfana",
}

# Verbos de violencia fatal (lema normalizado)
VERBOS_VIOLENCIA = {
    "matar", "asesinar", "privar", "ejecutar", "ultimar",
    "disparar", "apuñalar", "estrangular", "golpear", "feminicidar",
    "fallecer", "morir",  # en voz pasiva/reflexiva
}

# Verbos que sugieren supervivencia o situación de orfandad del menor
# [Fix-2] Añadidos: presenciar, testificar, resguardar (ya estaba como lema base)
VERBOS_SUPERVIVENCIA = {
    "sobrevivir", "quedar", "rescatar", "encontrar", "hallar",
    "salvar", "proteger", "resguardar", "internar",
    "trasladar", "permanecer", "estar", "llorar", "presenciar",
    "ver", "orfanar", "testificar",
}

# Relaciones de dependencia que marcan sujeto
RELS_SUJETO = {"nsubj", "nsubj:pass", "csubj"}

# Relaciones de dependencia que marcan objeto directo / oblicuo
# [Fix-3] 'obl:agent' se EXCLUYE de la comprobación de FP (se trata aparte)
RELS_OBJETO = {"obj", "iobj", "obl", "nmod"}


# ═══════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════

def _normalizar(texto: str) -> str:
    """Elimina acentos y pasa a minúsculas para comparaciones robustas."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _es_menor(token: Token) -> bool:
    """Devuelve True si el token o su head nominal apuntan a un menor de edad."""
    lema = _normalizar(token.lemma_)
    texto = _normalizar(token.text)
    return lema in TERMINOS_MENOR or texto in TERMINOS_MENOR


def _es_mujer(token: Token) -> bool:
    """Devuelve True si el token apunta a una mujer adulta."""
    lema = _normalizar(token.lemma_)
    texto = _normalizar(token.text)
    return lema in TERMINOS_MUJER or texto in TERMINOS_MUJER


def _es_verbo_violencia(token: Token) -> bool:
    """True si el lema del verbo pertenece al conjunto de violencia fatal."""
    return _normalizar(token.lemma_) in VERBOS_VIOLENCIA


def _es_verbo_supervivencia(token: Token) -> bool:
    """True si el lema del verbo sugiere que el menor sobrevivió / quedó huérfano."""
    return _normalizar(token.lemma_) in VERBOS_SUPERVIVENCIA


def _obtener_span_nominal(token: Token) -> list[Token]:
    """
    Devuelve el token más los modificadores nominales inmediatos (compound, flat,
    appos) para capturar frases como 'sus tres hijos menores'.
    """
    grupo = [token]
    for hijo in token.children:
        if hijo.dep_ in ("compound", "flat", "flat:name", "appos", "nummod", "det"):
            grupo.append(hijo)
    return grupo


def _es_agente_pasivo(token: Token) -> bool:
    """
    [Fix-3 + Fix-4 + Fix-4b] Devuelve True si el token es el AGENTE de una
    construcción pasiva y por lo tanto es el VICTIMARIO, no la víctima.
    Cubre todos los casos que spaCy puede generar en español, incluyendo
    titulares en Title Case donde el parser falla al asignar dep_ correcto:

      Caso A (ideal):   dep_ == 'obl:agent'  → relación explícita de agente.
      Caso B (común):   head directo del token es la preposición "por".
      Caso C (Fix-4):   token con dep_ obl/nmod tiene hijo izquierdo "por"
                        con dep_=="case" (spaCy invierte la relación).
      Caso D (Fix-4b):  VENTANA LÉXICA — independiente del árbol de dep_.
                        Si alguno de los 3 tokens inmediatamente anteriores
                        en el texto normalizado es "por", el token se clasifica
                        como victimario. Esto resuelve el fallo en titulares
                        con Title Case como "Es Asesinada Por Su Propio Hijo"
                        donde spaCy no asigna ninguna de las dep_ anteriores.
    """
    # Caso A: relación canónica de agente pasivo
    if token.dep_ == "obl:agent":
        return True

    # Caso B: el head inmediato del token ES la preposición "por"
    if _normalizar(token.head.text) == "por" and token.head.dep_ == "case":
        return True

    # Caso C (Fix-4): token obl/nmod con hijo izquierdo "por" + dep_=="case"
    if token.dep_ in ("obl", "nmod"):
        for child in token.children:
            if (
                child.i < token.i
                and child.dep_ == "case"
                and _normalizar(child.text) == "por"
            ):
                return True

    # Caso D (Fix-4b): ventana léxica de los 3 tokens anteriores en el doc.
    # No depende del árbol sintáctico: solo mira el texto plano normalizado.
    # Si el token está en posición >= 1 en el documento, revisamos hasta 3
    # tokens previos buscando la preposición "por".
    sent = token.sent
    token_pos_en_sent = token.i - sent.start  # posición relativa en la oración
    inicio = max(0, token_pos_en_sent - 3)
    ventana = [sent[j] for j in range(inicio, token_pos_en_sent)]
    if any(_normalizar(t.text) == "por" for t in ventana):
        return True

    return False


# ═══════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL DE ANÁLISIS
# ═══════════════════════════════════════════════════════════════

def analizar_roles_victimas(
    texto: str,
    nlp: spacy.language.Language,
) -> tuple[bool, dict]:
    """
    Analiza un fragmento de noticia para determinar si corresponde
    al patrón: mujer adulta = víctima fatal + menor = NNA huérfano/sobreviviente.

    Estrategia de tres niveles:
      L1 — Análisis de dependencias sintácticas por oración:
           Busca verbos de violencia cuyo objeto sea una MUJER y verbos
           de supervivencia cuyo sujeto sea un MENOR en la misma noticia.
           L1b también detecta construcciones pasivas donde el menor
           aparece como sujeto paciente (nsubj:pass) de verbos de superv.

      L2 — Detección de rol inverso (rechazo de falsos positivos):
           Si un MENOR aparece como OBJETO de un verbo de violencia,
           se marca como falso positivo y se devuelve False.
           [Fix-3] Se ignoran tokens con dep_ == 'obl:agent' o cuyo head
           sea la preposición "por" (son agentes/victimarios, no víctimas).

      L3 — Señales léxicas de refuerzo:
           Presencia de "huérfano/a", "quedó al cuidado", "DIF",
           "resguardado" como evidencia adicional.
           [Fix-1] Las palabras sueltas (señales_lex) solo cuentan si L1
           detectó al menos un verbo de violencia en el texto completo.
           Los patrones_mp (regex multipalabra) siguen siendo independientes.

    Args:
        texto: Texto de la noticia (título + contenido recomendado).
        nlp: Modelo spaCy ya cargado (es_core_news_lg).

    Returns:
        (es_caso_valido: bool, roles: dict)
        roles incluye:
          - victima_adulta: lista de términos de mujer detectados como objeto
          - menor_superviviente: lista de términos de menor como sujeto de superv.
          - menor_victima_directa: True si un menor fue objeto de violencia (FP)
          - señales_orfandad: palabras léxicas de orfandad encontradas
          - oraciones_procesadas: fragmentos relevantes del árbol dep
    """
    doc: Doc = nlp(texto)

    roles = {
        "victima_adulta": [],          # Mujer detectada como obj de violencia
        "menor_superviviente": [],     # Menor como sujeto de supervivencia
        "menor_victima_directa": False,# Bandera de falso positivo
        "señales_orfandad": [],        # Evidencia léxica adicional
        "oraciones_procesadas": [],    # Trazas del árbol de dependencias
    }

    # ── L1 + L2: Análisis por oración en el árbol de dependencias ──
    # NOTA: Ejecutamos L1/L2 ANTES de L3 para saber si hubo verbo de violencia.
    hay_verbo_violencia_l1 = False  # [Fix-1] bandera para condicionar L3

    for sent in doc.sents:
        for token in sent:
            # Solo procesamos verbos
            if token.pos_ not in ("VERB", "AUX"):
                continue

            verbo_norm = _normalizar(token.lemma_)
            es_violencia = _es_verbo_violencia(token)
            es_superv    = _es_verbo_supervivencia(token)

            if not (es_violencia or es_superv):
                continue  # Verbo irrelevante para el análisis

            if es_violencia:
                hay_verbo_violencia_l1 = True  # [Fix-1]

            # Recopilar sujetos y objetos del verbo actual
            sujetos = [h for h in token.children if h.dep_ in RELS_SUJETO]
            objetos  = [h for h in token.children if h.dep_ in RELS_OBJETO]

            # ── L2: ¿Hay un MENOR como OBJETO de un verbo de violencia? ──
            # [Fix-3] Se descartan tokens que sean agentes de voz pasiva.
            if es_violencia:
                for obj in objetos:
                    if _es_menor(obj) and not _es_agente_pasivo(obj):
                        roles["menor_victima_directa"] = True
                        roles["oraciones_procesadas"].append({
                            "tipo": "FALSO_POSITIVO",
                            "verbo": token.text,
                            "menor_obj": obj.text,
                            "oracion": sent.text[:120],
                        })
                # [Fix-3] También revisar hijos con dep_ == 'obl:agent' explícitamente
                # para registrarlos como agentes, no como FP
                for child in token.children:
                    if child.dep_ == "obl:agent" and _es_menor(child):
                        # Es el agresor en la voz pasiva → no es FP
                        roles["oraciones_procesadas"].append({
                            "tipo": "AGENTE_PASIVO_IGNORADO",
                            "verbo": token.text,
                            "agente": child.text,
                            "oracion": sent.text[:120],
                        })

            # ── L1a: ¿Hay una MUJER como OBJETO de un verbo de violencia? ──
            if es_violencia:
                for obj in objetos:
                    if _es_mujer(obj):
                        roles["victima_adulta"].append(obj.text)
                        roles["oraciones_procesadas"].append({
                            "tipo": "VICTIMA_ADULTA",
                            "verbo": token.text,
                            "mujer_obj": obj.text,
                            "oracion": sent.text[:120],
                        })

            # ── L1b: ¿Hay un MENOR como SUJETO de un verbo de supervivencia? ──
            # [Fix-2] Incluye nsubj:pass para construcciones pasivas como
            # "fueron puestos bajo resguardo", "niño que presenció el feminicidio"
            if es_superv:
                for subj in sujetos:
                    if _es_menor(subj):
                        roles["menor_superviviente"].append(subj.text)
                        roles["oraciones_procesadas"].append({
                            "tipo": "MENOR_SUPERVIVIENTE",
                            "verbo": token.text,
                            "menor_subj": subj.text,
                            "oracion": sent.text[:120],
                        })

    # ── L3: Búsqueda léxica de señales de orfandad ─────────────
    # [Fix-1] Las señales_lex (palabras sueltas) SOLO suman si L1 detectó
    # al menos un verbo de violencia. Los patrones_mp son independientes.
    señales_lex = {
        "huerfano", "huérfano", "huerfana", "huérfana",
        "orfandad", "dif", "resguardado", "resguardada",
        "custodia", "tutela", "amparo",
    }
    texto_norm = _normalizar(texto)

    if hay_verbo_violencia_l1:  # [Fix-1] condición de guardia
        for señal in señales_lex:
            if señal in texto_norm:
                roles["señales_orfandad"].append(señal)

    # Patrones multipalabra: disparan independientemente (tienen más contexto)
    patrones_mp = [
        r"qued[oó]\s+(al\s+)?cuidado",
        r"hijo[s]?\s+qued[oa]ron",
        r"menor[es]?\s+sobrevivi[oó]",
        r"niño[s]?\s+fueron\s+(rescatados?|hallados?|encontrados?)",
        r"menores?\s+(bajo|en)\s+resguardo",          # [Fix-2] nuevo patrón
        r"(niño|menor|hija?)\s+que\s+presenci[oó]",   # [Fix-2] nuevo patrón
    ]
    for patron in patrones_mp:
        if re.search(patron, texto_norm):
            roles["señales_orfandad"].append(f"[patrón]: {patron}")

    # ── Decisión final ──────────────────────────────────────────
    #
    # CASO VÁLIDO si se cumplen TODAS:
    #   (a) No hay menor como víctima directa (L2 limpio)
    #   (b) Al menos una de:
    #       • Mujer detectada como víctima de violencia (L1a)
    #       • Señal léxica de orfandad (L3)
    #   (c) Al menos una de:
    #       • Menor detectado como superviviente/sujeto (L1b)
    #       • Señal léxica de orfandad (L3)
    #
    # [Fix-5] RETORNO FORZADO por patrón fuerte:
    #   Si un patron_mp de alta especificidad hizo match (contiene evidencia
    #   explícita del menor: «presenció», «bajo resguardo», «hijos quedaron»)
    #   Y L2 está limpio (no hay menor como víctima directa),
    #   se acepta el caso SIN exigir que L1a haya extraído a la mujer como
    #   objeto directo —el parser puede fallar en titulares cortos—.
    # [Fix-5b] PATRONES_FUERTES sin acentos: texto_norm ya pasó por _normalizar(),
    # que elimina diacríticos → "presenció" → "presencio", "quedó" → "quedo", etc.
    # Los patrones NO deben contener acentos; se añaden variantes con/sin acento
    # solo en la forma base para mayor cobertura.
    PATRONES_FUERTES = [
        r"quedo\s+(al\s+)?cuidado",                                  # quedó al cuidado
        r"hijo[s]?\s+quedar?on",                                     # hijos quedaron
        r"menor[es]?\s+sobrevivio",                                  # menor sobrevivió
        r"ni[nm]o[s]?\s+fueron\s+(rescatados?|hallados?|encontrados?)",  # niños fueron
        r"menores?\s+(bajo|en)\s+resguardo",                         # bajo resguardo
        r"(nin[oa]s?|menores?|hij[oa]s?)\s+que\s+presencio",        # que presenció
        r"(nin[oa]s?|menores?|hij[oa]s?)\s+presencio\s+el",         # presenció el [crimen]
        r"(nin[oa]s?|menores?|hij[oa]s?)\s+fueron\s+puestos?",      # fueron puestos
        r"testigo[s]?\s+(del?\s+)?feminicidio",                     # testigo del feminicidio
    ]
    # IMPORTANTE: re.search sobre texto_norm (sin acentos, minúsculas)
    hay_patron_fuerte = any(
        re.search(p, texto_norm) for p in PATRONES_FUERTES
    )

    hay_victima_adulta  = len(roles["victima_adulta"]) > 0
    hay_menor_superv    = len(roles["menor_superviviente"]) > 0
    hay_señal_orfandad  = len(roles["señales_orfandad"]) > 0
    es_falso_positivo   = roles["menor_victima_directa"]

    # [Fix-5] Retorno forzado: patrón fuerte + L2 limpio → True
    if hay_patron_fuerte and not es_falso_positivo:
        roles["oraciones_procesadas"].append({
            "tipo": "PATRON_FUERTE_FORZADO",
            "verbo": "—",
            "oracion": texto_norm[:120],
        })
        return True, roles

    es_caso_valido = (
        not es_falso_positivo
        and (hay_victima_adulta or hay_señal_orfandad)
        and (hay_menor_superv   or hay_señal_orfandad)
    )

    return es_caso_valido, roles


# ═══════════════════════════════════════════════════════════════
# BLOQUE DE PRUEBAS
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Cargando modelo spaCy es_core_news_lg …")
    nlp = spacy.load("es_core_news_lg")
    print("Modelo cargado.\n")

    # ─────────────────────────────────────────────────────────────
    # CASOS DE PRUEBA
    # Cada caso es: (descripción, texto, resultado_esperado)
    # ─────────────────────────────────────────────────────────────
    casos = [

        # ── Caso 1: POSITIVO VERDADERO ────────────────────────────
        # Mujer adulta asesinada; sus hijos quedan huérfanos.
        (
            "✅ POSITIVO VERDADERO — Madre asesinada, hijos huérfanos",
            (
                "Un hombre mató a su esposa a golpes en Ecatepec. "
                "Sus tres hijos quedaron huérfanos y fueron resguardados por el DIF. "
                "Los menores, de 4, 7 y 9 años, presenciaron el feminicidio."
            ),
            True,
        ),

        # ── Caso 2: FALSO POSITIVO — Menor asesinada ─────────────
        # El agresor mató a una niña, NO a la madre.
        (
            "❌ FALSO POSITIVO — Niña víctima directa del feminicidio",
            (
                "Un sujeto asesinó a su hija de 8 años en Monterrey. "
                "La menor fue hallada sin vida en el domicilio familiar. "
                "El feminicida fue detenido horas después."
            ),
            False,
        ),

        # ── Caso 3: FALSO POSITIVO — Agresor es el hijo ──────────
        # El hijo adulto mató a su madre; no aplica al caso de interés.
        (
            "❌ FALSO POSITIVO — Hijo adulto asesina a su madre",
            (
                "Un joven de 19 años asesinó a su madre a puñaladas en Guadalajara. "
                "El agresor fue arrestado en flagrancia por vecinos del lugar."
            ),
            False,
        ),

        # ── Caso 4: POSITIVO VERDADERO — Señal léxica ────────────
        # Árbol de dependencias más ambiguo, pero hay señal de orfandad.
        (
            "✅ POSITIVO VERDADERO — Menor huérfano (señal léxica)",
            (
                "Una mujer fue privada de la vida por su pareja sentimental en Puebla. "
                "Su bebé de un año quedó al cuidado de los abuelos maternos. "
                "La Fiscalía inició carpeta de investigación por feminicidio."
            ),
            True,
        ),

        # ── Caso 5: NEGATIVO VERDADERO — Estadísticas ────────────
        # Noticia de cifras/estadísticas, sin caso individual.
        (
            "⬜ NEGATIVO VERDADERO — Noticia estadística sin caso concreto",
            (
                "El INEGI reportó 969 feminicidios en México durante 2023. "
                "El informe señala que el Estado de México concentra el 18% de los casos. "
                "Organizaciones civiles exigieron mayor presupuesto para atención a víctimas."
            ),
            False,
        ),

        # ── Caso 6 [Fix-1]: NEGATIVO VERDADERO — "DIF" en política ──
        # Noticia de presupuesto del DIF; sin verbo de violencia → L3 no activa.
        (
            "⬜ NEGATIVO VERDADERO — Noticia de política con 'DIF' (Fix-1)",
            (
                "El Congreso aprobó un incremento del 12% al presupuesto del DIF nacional. "
                "La secretaria de Bienestar indicó que los recursos se destinarán a programas "
                "de orfandad y tutela en comunidades marginadas."
            ),
            False,
        ),

        # ── Caso 7 [Fix-2]: POSITIVO VERDADERO — "presenció feminicidio" ──
        # Menor testigo del crimen; capturado por patrón multipalabra L3.
        (
            "✅ POSITIVO VERDADERO — Niño que presenció feminicidio (Fix-2)",
            (
                "La madre fue asesinada a balazos frente a su domicilio en Culiacán. "
                "Su hijo de 6 años, que presenció el feminicidio, fue trasladado a una "
                "casa de acogida por personal del DIF municipal."
            ),
            True,
        ),

        # ── Caso 8 [Fix-2]: POSITIVO VERDADERO — "menores bajo resguardo" ──
        # Construcción pasiva; capturado por patrón multipalabra L3.
        (
            "✅ POSITIVO VERDADERO — Menores bajo resguardo (Fix-2)",
            (
                "Una mujer fue ultimada por su pareja en la colonia Doctores. "
                "Sus dos hijos menores de edad fueron puestos bajo resguardo "
                "de las autoridades del DIF capitalino."
            ),
            True,
        ),

        # ── Caso 9 [Fix-3]: NEGATIVO VERDADERO — "Mujer asesinada por su hijo" ──
        # "hijo" es agente pasivo (obl:agent); NO debe disparar FP de menor atacado.
        (
            "❌ FALSO POSITIVO esperado → debe ser False — Hijo victimario (Fix-3)",
            (
                "Mujer asesinada por su hijo en la alcaldía Iztapalapa. "
                "El joven de 22 años fue detenido por elementos de la SSC. "
                "La víctima tenía 48 años y no dejó menores de edad a su cargo."
            ),
            False,
        ),
    ]

    # ─────────────────────────────────────────────────────────────
    # Ejecución y reporte
    # ─────────────────────────────────────────────────────────────
    RESET  = "\033[0m"
    VERDE  = "\033[92m"
    ROJO   = "\033[91m"
    AMARILLO = "\033[93m"
    CYAN   = "\033[96m"

    aciertos = 0
    for i, (descripcion, texto, esperado) in enumerate(casos, 1):
        resultado, roles = analizar_roles_victimas(texto, nlp)
        correcto = resultado == esperado
        if correcto:
            aciertos += 1

        color_titulo = VERDE if correcto else ROJO
        color_res    = VERDE if resultado else ROJO
        icono        = "✓" if correcto else "✗"

        print(f"{color_titulo}{'─'*65}{RESET}")
        print(f"{color_titulo}[{icono}] Caso {i}: {descripcion}{RESET}")
        print(f"    Esperado : {AMARILLO}{esperado}{RESET}")
        print(f"    Obtenido : {color_res}{resultado}{RESET}")

        # Detalles de roles extraídos
        if roles["victima_adulta"]:
            print(f"    {CYAN}Víctima adulta detectada : {roles['victima_adulta']}{RESET}")
        if roles["menor_superviviente"]:
            print(f"    {CYAN}Menor superviviente      : {roles['menor_superviviente']}{RESET}")
        if roles["menor_victima_directa"]:
            print(f"    {ROJO}⚠ Menor como víctima directa (FP bloqueado){RESET}")
        if roles["señales_orfandad"]:
            print(f"    {CYAN}Señales de orfandad      : {roles['señales_orfandad']}{RESET}")

        # Trazas del árbol de dependencias (máx 3 para legibilidad)
        if roles["oraciones_procesadas"]:
            print(f"    Trazas dep:")
            for traza in roles["oraciones_procesadas"][:3]:
                tipo = traza["tipo"]
                verb = traza.get("verbo", "?")
                ent  = traza.get(
                    "mujer_obj",
                    traza.get("menor_subj", traza.get("menor_obj",
                    traza.get("agente", "?")))
                )
                oracion_corta = traza["oracion"][:80]
                print(f"      [{tipo}] verbo='{verb}' entidad='{ent}'")
                print(f"        › {oracion_corta}…")
        print()

    print(f"{'═'*65}")
    print(f"  RESULTADO: {aciertos}/{len(casos)} casos correctos")
    print(f"{'═'*65}")
