"""Test aislado: valida los patrones regex de Keywords de Oro sin dependencias pesadas."""
import re
from unicodedata import normalize

# ── Copiar solo lo necesario para testing ──

def _normalize_text(text):
    if not isinstance(text, str):
        return ''
    return normalize('NFKD', text).lower()


KEYWORDS_DE_ORO = [
    r'\b(?:dej[oó]|dejaron|dejar[aá]n?)\s+(?:\w+\s+){0,4}(?:en\s+)?orfandad\b',
    r'\b(?:quedan?|quedaron|qued[oó])\s+(?:\w+\s+){0,3}(?:hu[eé]rfan[oa]s?|en\s+orfandad)\b',
    r'\b(?:menores?|ni[ñn][oa]s?|hijos?|hijas?)\s+(?:\w+\s+){0,2}(?:en\s+)?orfandad\b',
    r'\bhu[eé]rfan[oa]s?\s+(?:por|tras|del?|a\s+causa)\b',
    r'\borfandad\s+(?:por|tras|del?|a\s+causa)\s+(?:\w+\s+){0,3}(?:feminicidio|asesinato|homicidio|muerte)\b',
    r'\b(?:bajo|en)\s+(?:resguardo|custodia|protecci[oó]n)\s+(?:del?\s+)?DIF\b',
    r'\bDIF\s+(?:resguarda|tiene|protege|acoge|recibi[oó]|entreg[oó])\b',
    r'\b(?:resguardad[oa]s?|acogid[oa]s?|protegid[oa]s?)\s+(?:por|en)\s+(?:el\s+)?DIF\b',
    r'\b(?:entreg|puestos?|llevad[oa]s?)\s+(?:\w+\s+){0,2}(?:al?\s+)?DIF\b',
    r'\bfrente\s+a\s+sus?\s+(?:hijos?|hijas?|menores?|ni[ñn][oa]s?)\b',
    r'\b(?:delante|enfrente|presencia)\s+de\s+sus?\s+(?:hijos?|hijas?|menores?|ni[ñn][oa]s?)\b',
    r'\b(?:hijos?|hijas?|menores?|ni[ñn][oa]s?)\s+(?:\w+\s+){0,4}(?:presenciaron|vieron|observaron|estaban?\s+presentes?)\b',
    r'\b(?:asesinada|matada|muerta|baleada)\s+(?:\w+\s+){0,3}frente\s+a\s+(?:sus?\s+)?(?:hijos?|hijas?|menores?)\b',
    r'\b(?:quedaron?|quedan?|dejan?|dejaron)\s+(?:\w+\s+){0,3}hu[eé]rfan[oa]s?\b',
    r'\bhu[eé]rfan[oa]s?\s+(?:de\s+)?(?:madre|padre|ambos)\b',
    r'\b(?:dos|tres|cuatro|cinco|\d+)\s+(?:menores?|ni[ñn][oa]s?|hijos?|hijas?)\s+(?:\w+\s+){0,2}hu[eé]rfan[oa]s?\b',
    r'\b(?:ni[ñn][oa]|menor|beb[eé]|hija?)\s+(?:\w+\s+){0,3}(?:fue\s+)?(?:robad[oa]|sustra[ií]d[oa]|raptad[oa]|secuestrad[oa]|llevad[oa])\b',
    r'\b(?:robaron|sustrajeron|raptaron|secuestraron|llevaron)\s+(?:\w+\s+){0,3}(?:a\s+)?(?:la\s+)?(?:ni[ñn]a|menor|beb[eé]|hija)\b',
    r'\b(?:menores?|ni[ñn][oa]s?|hijos?|hijas?)\s+(?:\w+\s+){0,2}(?:sin\s+(?:su\s+)?madre|desamparad[oa]s?|desprotegid[oa]s?|sol[oa]s?)\b',
    r'\b(?:dej[oó]|dejaron)\s+(?:\w+\s+){0,4}(?:sin\s+(?:su\s+)?madre|desamparad[oa]s?|sol[oa]s?)\b',
]


def _check_keywords_de_oro(text_norm):
    for pattern in KEYWORDS_DE_ORO:
        if re.search(pattern, text_norm, re.IGNORECASE):
            return True
    return False


# ── Casos de prueba ──

POSITIVE_CASES = [
    "Feminicidio de Cindy en Cuautitlan dejo a dos menores en orfandad",
    "Doble feminicidio en Cuautitlan: matan a mujer y su hija; nina de 3 anos fue robada",
    "Asesinan a una mujer frente a sus hijos en Ecatepec",
    "Erika Camila esta bajo resguardo del DIF tras el feminicidio de su madre",
    "Quedan huerfanos tres ninos tras feminicidio de su madre",
    "La madre fue asesinada y dejaron a dos menores desamparados",
    "Los hijos de la victima presenciaron el crimen",
    "Mujer baleada frente a sus hijos",
    "Dejó a dos menores en orfandad por feminicidio",
    "Orfandad por feminicidio: 3 ninos quedaron solos",
    "Huerfanos de madre tras feminicidio en Edomex",
]

NEGATIVE_CASES = [
    "Menor de edad asesina a su madre en Guadalajara",
    "Detienen a adolescente por feminicidio en Jalisco",
    "Cifras de feminicidio en Mexico 2025",
    "Marcha contra la violencia de genero en CDMX",
    "Ley contra la violencia vicaria aprobada en el Senado",
]

print("=" * 60)
print("  TEST: Keywords de Oro — Validacion de Patrones Regex")
print("=" * 60)

errors = 0

print("\n--- Casos POSITIVOS (deben detectar keywords de oro) ---\n")
for text in POSITIVE_CASES:
    norm = _normalize_text(text)
    result = _check_keywords_de_oro(norm)
    status = "OK" if result else "FAIL"
    if not result:
        errors += 1
    print("  [{}] {}".format(status, text[:75]))

print("\n--- Casos NEGATIVOS (NO deben detectar keywords de oro) ---\n")
for text in NEGATIVE_CASES:
    norm = _normalize_text(text)
    result = _check_keywords_de_oro(norm)
    status = "OK" if not result else "FAIL"
    if result:
        errors += 1
    print("  [{}] gold={} | {}".format(status, result, text[:75]))

print("\n" + "=" * 60)
if errors == 0:
    print("  TODOS LOS TESTS PASARON")
else:
    print("  {} TESTS FALLARON".format(errors))
print("=" * 60)
