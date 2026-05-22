# -*- coding: utf-8 -*-
"""
Test del Post-Filtro v6.0 contra los datos etiquetados.

Simula el efecto del post-filtro sobre los 127 FP y 38 VP
usando SOLO los títulos (el campo más disponible) para medir
cuántos FP se bloquean y cuántos VP se preservan.
"""
import re
import sys
import io
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ── Copiar los patrones del detector ──────────────────────────────
PATRONES_VP = (
    r"(?:quedaron?|quedan)\s+(?:en\s+)?(?:orfandad|huérfan|desamp)",
    r"deja(?:ndo|ron|\s)\s*(?:a\s+)?(?:sus\s+)?(?:\d+\s+)?hijos?",
    r"era\s+madre\s+de\s+\d+",
    r"madre\s+de\s+(?:dos|tres|cuatro|cinco|seis|siete|familia)",
    r"(?:frente|delante)\s+(?:a|de)\s+(?:sus?\s+)?hijos?",
    r"hijos?\s+(?:estaban?|quedaron?)\s+presentes?",
    r"(?:menor|niño|niña|hijo|hija)\s+(?:presenció|presenciaron|vio|atestiguó)",
    r"(?:menor|niño|niña)\s+(?:que\s+)?presenció",
    r"(?:menores?|hijos?|niños?)\s+(?:bajo|en)\s+(?:resguardo|custodia|protección)",
    r"(?:DIF|SNDIF|procuraduría)\s+(?:resguard|custodi|proteg)",
    r"resguardo\s+del\s+DIF",
    r"(?:sustra|rapt|secuestr|desaparec)\w+\s+(?:a\s+)?(?:su\s+)?(?:menor|hija|hijo|niña|niño)",
    r"(?:menor|hija|hijo|niña)\s+(?:reportada?|desaparecida?)\s+(?:como|tras|luego|después)",
    r"doble\s+feminicidio.*(?:menor|hija|hijo)",
    r"(?:dos|tres|cuatro|\d+)\s+menores\s+(?:quedan|quedaron)\s+(?:en\s+)?orfandad",
    r"hijos?\s+(?:quedaron?|quedan)\s+solos?",
    r"(?:tragedia|feminicidio).*(?:deja|dejó).*(?:menor|huérfan|orfandad)",
    r"(?:hijo|hija|menor|niño|niña)\s+(?:que\s+)?(?:relat|narr|cont|dijo|revel)",
    r"testimonio\s+(?:del?\s+)?(?:menor|niño|niña|hijo)",
)

PATRONES_FP = (
    r"hijo\w*\s+(?:la\s+)?(?:mat[óoaé]|asesin[óoaé]|habría\s+(?:matado|asesinado))",
    r"hijo\w*\s+(?:presuntamente\s+)?(?:mata|asesina|habría)",
    r"(?:su\s+)?hijo\w*\s+(?:la|lo|le)\s+(?:mat|asesin|apuñal|dispar)",
    r"(?:hija|yerno)\s+(?:fueron?|fue)\s+detenid[oa]s?",
    r"(?:hija|hijo).*(?:detenid[oa]|arrest[oa]d[oa])\s+(?:por|como)",
    r"(?:feminicidio|asesinato)\s+(?:de\s+)?(?:una\s+)?(?:menor|jovencita|niña|adolescente)\b",
    r"(?:menor|niña|adolescente)\s+(?:de\s+\d+\s+años\s+)?(?:asesinada|encontrada\s+sin\s+vida)",
    r"(?:mujer\s+)?(?:asesina|mata)\s+a\s+su\s+(?:hijo|hija)\b",
    r"(?:homicidio|muerte)\s+de\s+su\s+hijo",
    r"(?:olvidarlo|dejarlo|dejándolo)\s+(?:\d+\s+)?horas?\s+(?:en\s+)?(?:el\s+)?auto",
    r"menor\s+cayó\s+de\s+un",
    r"(?:detienen|arrestan|capturan)\s+a\s+(?:un\s+)?menor\s+(?:por|como|de)",
    r"(?:adolescente|menor)\s+(?:es\s+)?(?:imputad[oa]|acusad[oa]|detenid[oa]|vinculad[oa])",
    r"formulan\s+imputación\s+a\s+(?:un\s+)?adolescente",
    r"menor\s+de\s+\d+\s+años\s+(?:por\s+)?(?:asesinato|feminicidio|homicidio)",
    r"(?:visibilizar|dimensionar|atender|documentar)\s+(?:la\s+)?orfandad",
    r"orfandad\s+por\s+feminicidio\s*:\s*\d+\s+años",
    r"(?:deuda|crisis|problema|reto)\s+(?:que|de).*orfandad",
    r"podcast|editorial|opinión|columna",
    r"(?:primer|segund|tercer|cuart|quint|sext|séptim|octav|noven|décim)\w*\s+lugar",
    r"\d+\s+de\s+cada\s+\d+\s+(?:menor|niñ|mujer)",
    r"\d+\s+(?:niñas|menores|mujeres)\s+(?:asesinadas|desaparecidas)\s+en\s+(?:una\s+)?década",
    r"se\s+(?:disparó|incrementó|registró)\s+\d+%",
    r"(?:cifras?|datos?)\s+(?:del?\s+)?(?:SNSP|INEGI|SESNSP)",
    r"(?:sentencia|fallo|resolución)\s+(?:de\s+)?(?:la\s+)?(?:CoIDH|Corte\s+IDH|CIDH)",
    r"(?:congreso|senado|cámara)\s+(?:obligará|aprobó|aprueba)",
    r"(?:obligará?|obliga)\s+al\s+Estado\s+a\s+(?:proteger|atender)",
    r"(?:incrementa|aumenta|destina)\s+recursos\s+(?:para|a)",
    r"beca\s+(?:rita|benito|bienestar)",
    r"abuso\s+sexual\s+(?:contra|de|a)\s+(?:un[oa]?\s+)?menor",
    r"(?:corrupción|explotación|trata)\s+de\s+menores",
    r"(?:extorsión|secuestro)\s+a\s+mujeres",
    r"(?:matan|asesinan|ejecutan)\s+a\s+(?:un\s+)?(?:hombre|mesero|pareja)",
    r"(?:matan|asesinan)\s+a\s+(?:madre\s+e\s+hijo|pareja)\s+(?:cuando|mientras)\s+(?:intentaban|iban)",
    r"ataque\s+armado\s+en\s+(?:parque|calle|bar|restaurante)",
)


def post_filtro(texto):
    texto_lower = texto.lower()
    for patron in PATRONES_FP:
        m = re.search(patron, texto_lower)
        if m:
            return "degradar", m.group(), patron
    for patron in PATRONES_VP:
        m = re.search(patron, texto_lower)
        if m:
            return "confirmar", m.group(), patron
    return "revisar", "", ""


# ── Cargar datos ──────────────────────────────────────────────────
df = pd.read_csv('data/noticias_analyzed_simplified.csv')

# ── Test sobre FP (queremos que se degraden) ──────────────────────
fp = df[(df['clasificacion_final'] == 'Alta') & (df['etiqueta_corregida'] == 0)]
print(f"{'='*70}")
print(f"TEST POST-FILTRO v6.0 — {len(fp)} FALSOS POSITIVOS")
print(f"{'='*70}\n")

fp_degradados = 0
fp_revisados = 0
fp_escaparon = 0

for i, row in fp.iterrows():
    titulo = str(row['titulo'])
    accion, match, patron = post_filtro(titulo)
    if accion == "degradar":
        fp_degradados += 1
    elif accion == "revisar":
        fp_revisados += 1
    else:
        fp_escaparon += 1
        print(f"  ⚠ FP ESCAPÓ (confirmado como VP): [{i}] {titulo[:120]}")
        print(f"    → match VP: '{match}'")

print(f"\n  FP degradados (bloqueados):  {fp_degradados}/{len(fp)} ({100*fp_degradados/len(fp):.1f}%)")
print(f"  FP a revisión (Media):       {fp_revisados}/{len(fp)} ({100*fp_revisados/len(fp):.1f}%)")
print(f"  FP que escaparon como Alta:  {fp_escaparon}/{len(fp)} ({100*fp_escaparon/len(fp):.1f}%)")

# ── Test sobre VP (queremos que se confirmen) ─────────────────────
vp = df[df['etiqueta_corregida'] == 1]
print(f"\n{'='*70}")
print(f"TEST POST-FILTRO v6.0 — {len(vp)} VERDADEROS POSITIVOS")
print(f"{'='*70}\n")

vp_confirmados = 0
vp_revisados = 0
vp_perdidos = 0

for i, row in vp.iterrows():
    titulo = str(row['titulo'])
    accion, match, patron = post_filtro(titulo)
    if accion == "confirmar":
        vp_confirmados += 1
    elif accion == "revisar":
        vp_revisados += 1
    else:
        vp_perdidos += 1
        print(f"  ❌ VP PERDIDO (degradado): [{i}] {titulo[:120]}")
        print(f"    → match FP: '{match}'")

print(f"\n  VP confirmados (Alta):    {vp_confirmados}/{len(vp)} ({100*vp_confirmados/len(vp):.1f}%)")
print(f"  VP a revisión (Media):    {vp_revisados}/{len(vp)} ({100*vp_revisados/len(vp):.1f}%)")
print(f"  VP perdidos (degradados): {vp_perdidos}/{len(vp)} ({100*vp_perdidos/len(vp):.1f}%)")

# ── Resumen ───────────────────────────────────────────────────────
print(f"\n{'='*70}")
print(f"RESUMEN IMPACTO POST-FILTRO v6.0")
print(f"{'='*70}")
print(f"  ANTES:  Precision = 29/(29+127) = 18.6%")

# Calcular nueva precision
# Alta nueva = VP confirmados + FP que escaparon
# Es_relevante = Alta + Media = (VP confirmados + FP escaparon) + (VP revisados + FP revisados)
nueva_alta = vp_confirmados + fp_escaparon
nueva_media = vp_revisados + fp_revisados
nueva_precision_alta = vp_confirmados / nueva_alta * 100 if nueva_alta > 0 else 0
nueva_precision_total = (vp_confirmados + vp_revisados) / (nueva_alta + nueva_media) * 100 if (nueva_alta + nueva_media) > 0 else 0

print(f"  DESPUÉS (solo Alta): Precision = {vp_confirmados}/{nueva_alta} = {nueva_precision_alta:.1f}%")
print(f"  DESPUÉS (Alta+Media): Precision = {vp_confirmados+vp_revisados}/{nueva_alta+nueva_media} = {nueva_precision_total:.1f}%")
print(f"  VP recall (no perdidos): {(vp_confirmados+vp_revisados)}/{len(vp)} = {100*(vp_confirmados+vp_revisados)/len(vp):.1f}%")
print(f"  VP perdidos por degradación FP falsa: {vp_perdidos}")
