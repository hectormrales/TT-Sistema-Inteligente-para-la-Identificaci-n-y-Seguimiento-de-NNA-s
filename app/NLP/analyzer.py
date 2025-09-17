# app/nlp/analyzer.py
import spacy
import re
from typing import List, Tuple

# Carga el modelo de español
nlp = spacy.load("es_core_news_sm")

# Palabras clave expandidas para identificar NNA
KEYWORDS_DIRECTOS = [
    # Términos familiares
    "hijo", "hija", "hijos", "hijas", "hijita", "hijito",
    "niño", "niña", "niños", "niñas", "niñito", "niñita",
    "bebé", "bebés", "recién", "nacido", "nacida",
    "criatura", "criaturas", "infante", "infantes",
    
    # Términos de edad
    "menor", "menores", "menor de edad", "menores de edad",
    "adolescente", "adolescentes", "joven", "jóvenes",
    "chavito", "chavita", "chaval", "chavala",
    
    # Términos de orfandad/abandono
    "huérfano", "huérfanos", "huérfana", "huérfanas",
    "abandonado", "abandonada", "abandonados", "abandonadas",
    
    # Términos escolares
    "estudiante", "estudiantes", "alumno", "alumna", "alumnos", "alumnas",
    "escolar", "escolares",
    
    # Otros términos relacionados
    "pequeño", "pequeña", "pequeños", "pequeñas",
    "chico", "chica", "chicos", "chicas",
    "muchachito", "muchachita", "muchacho", "muchacha"
]

# Patrones de edad que indican menores
PATRONES_EDAD = [
    r"\b(?:de\s+)?(\d{1,2})\s+años?\b",
    r"\bmeses?\s+de\s+edad\b",
    r"\brecién\s+nacid[ao]s?\b",
    r"\b(?:un|una)\s+año\b",
    r"\b(?:dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|dieciséis|diecisiete)\s+años?\b"
]

# Contextos que indican situaciones de NNA en riesgo
CONTEXTOS_RIESGO = [
    "embarazada", "embarazo", "gestante", "gestación",
    "madre soltera", "madre joven",
    "familia", "hogar", "casa", "domicilio familiar",
    "escuela", "colegio", "jardín", "guardería",
    "tutela", "custodia", "patria potestad",
    "adopción", "foster", "acogida"
]

def find_nna_mentions(text: str) -> bool:
    """
    Busca menciones de NNA en el texto usando múltiples estrategias
    """
    if not text or len(text.strip()) < 10:
        return False
    
    text_lower = text.lower()
    mentions_found = []
    
    # 1. Búsqueda directa de palabras clave
    direct_mentions = find_direct_keywords(text_lower)
    if direct_mentions:
        mentions_found.extend(direct_mentions)
    
    # 2. Búsqueda por patrones de edad
    age_mentions = find_age_patterns(text)
    if age_mentions:
        mentions_found.extend(age_mentions)
    
    # 3. Análisis con spaCy para lemas y contexto
    spacy_mentions = find_spacy_mentions(text)
    if spacy_mentions:
        mentions_found.extend(spacy_mentions)
    
    # 4. Búsqueda contextual
    context_mentions = find_contextual_mentions(text_lower)
    if context_mentions:
        mentions_found.extend(context_mentions)
    
    # Imprimir las menciones encontradas para debug
    if mentions_found:
        unique_mentions = list(set(mentions_found))
        print(f"Menciones de NNA encontradas: {unique_mentions}")
        return True
    else:
        print("No se encontraron menciones de NNA")
        return False

def find_direct_keywords(text: str) -> List[str]:
    """Busca palabras clave directas en el texto"""
    found = []
    for keyword in KEYWORDS_DIRECTOS:
        if keyword in text:
            found.append(f"palabra_clave: {keyword}")
    return found

def find_age_patterns(text: str) -> List[str]:
    """Busca patrones que indican edad de menores"""
    found = []
    for pattern in PATRONES_EDAD:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            if pattern == r"\b(?:de\s+)?(\d{1,2})\s+años?\b":
                age = int(match.group(1))
                if age < 18:  # Solo considerar menores de edad
                    found.append(f"edad: {age} años")
            else:
                found.append(f"patrón_edad: {match.group()}")
    return found

def find_spacy_mentions(text: str) -> List[str]:
    """Usa spaCy para análisis más sofisticado"""
    found = []
    doc = nlp(text.lower())
    
    # Buscar lemas de palabras clave
    target_lemmas = {"hijo", "hija", "niño", "niña", "menor", "huérfano", "bebé", "adolescente"}
    
    for token in doc:
        if token.lemma_ in target_lemmas:
            found.append(f"lema: {token.lemma_} ({token.text})")
    
    # Buscar entidades nombradas que puedan ser personas jóvenes
    for ent in doc.ents:
        if ent.label_ == "PER":  # Persona
            # Buscar indicadores de edad cerca de la entidad
            start_idx = max(0, ent.start - 5)
            end_idx = min(len(doc), ent.end + 5)
            context = doc[start_idx:end_idx].text
            
            for keyword in ["años", "menor", "niño", "niña", "hijo", "hija"]:
                if keyword in context.lower():
                    found.append(f"entidad_persona: {ent.text} (contexto: {keyword})")
                    break
    
    return found

def find_contextual_mentions(text: str) -> List[str]:
    """Busca menciones contextuales que sugieren presencia de NNA"""
    found = []
    
    # Buscar combinaciones que sugieren NNA en riesgo
    if "embarazada" in text and any(word in text for word in ["asesinada", "muerta", "víctima", "feminicidio"]):
        found.append("contexto: embarazada_victima (posible NNA no nacido)")
    
    if "madre" in text and any(age_word in text for age_word in ["joven", "adolescente"]):
        found.append("contexto: madre_joven")
    
    # Buscar patrones de familia con violencia
    family_violence_patterns = [
        r"(?:hijos?|hijas?|niños?|niñas?).{0,50}(?:presente|presenciaron|vieron|testigo)",
        r"(?:familia|hogar|casa).{0,30}(?:menores?|niños?|hijos?)",
        r"(?:menor|niño|niña|hijo|hija).{0,50}(?:herido|lastimado|afectado)"
    ]
    
    for pattern in family_violence_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            found.append(f"contexto_familiar: {pattern[:30]}...")
    
    return found

# Función de prueba para debugging
def test_analyzer(text: str) -> None:
    """Función para probar el analizador con un texto específico"""
    print(f"\n=== ANALIZANDO TEXTO ===")
    print(f"Texto: {text[:100]}...")
    print(f"Resultado: {find_nna_mentions(text)}")
    print("=" * 50)