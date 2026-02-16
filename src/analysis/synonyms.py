# src/analysis/synonyms.py — Diccionario de sinónimos NNA + Feminicidio
"""
Diccionario especializado para búsqueda semántica de términos
relacionados con: feminicidios, NNA (víctimas indirectas),
violencia de género, justicia y protección.

Incluye búsqueda mejorada con ranking por relevancia.
"""

import json
import re
from typing import Dict, List, Set, Optional

import pandas as pd


class SynonymDictionary:
    """Diccionario de sinónimos para búsqueda semántica."""

    def __init__(self):
        self.synonyms: Dict[str, Set[str]] = {}
        self.reverse_index: Dict[str, str] = {}
        self._load_defaults()

    # ── Carga de sinónimos ──────────────────────────────────

    def _load_defaults(self):
        """Carga grupos de sinónimos predefinidos para el dominio."""
        groups = {
            # ── Feminicidio y violencia letal ────────────────
            'feminicidio': [
                "feminicidio", "femicidio", "asesinato de mujer",
                "homicidio de mujer", "crimen de género",
                "violencia feminicida", "muerte violenta de mujer",
                "homicidio doloso de mujer", "crimen pasional",
                "asesinada", "ultimada", "privada de la vida",
            ],
            # ── NNA y víctimas indirectas ────────────────────
            'nna': [
                "niños", "niñas", "niña", "niño", "menores", "menor",
                "infantes", "infante", "adolescentes", "adolescente",
                "jóvenes", "púberes", "NNA", "nna", "hijos", "hijas",
                "hijo", "hija", "bebés", "bebé", "recién nacidos",
                "neonatos", "lactantes", "pequeños", "chicos", "chicas",
                "muchachos", "muchachas", "críos", "crías",
                "chavos", "chavas", "morritos", "morritas",
                "menores de edad", "menor de edad",
            ],
            # ── Orfandad (eje central del proyecto) ──────────
            'orfandad': [
                "huérfanos", "huérfanas", "huérfano", "huérfana",
                "orfandad", "sin padres", "sin madre", "sin padre",
                "abandonados", "desamparados", "víctimas indirectas",
                "víctimas colaterales", "hijos de víctimas",
                "hijos de la víctima", "hijas de la víctima",
                "quedaron sin madre", "quedaron solos",
                "niños sobrevivientes", "orfandad por feminicidio",
                "menores afectados", "menores desprotegidos",
            ],
            # ── Violencia de género ──────────────────────────
            'violencia': [
                "violencia", "agresión", "maltrato", "abuso", "lesiones",
                "golpes", "violencia física", "violencia psicológica",
                "violencia sexual", "violencia doméstica",
                "violencia familiar", "violencia intrafamiliar",
                "tortura", "vejaciones", "acoso", "hostigamiento",
                "violencia de género", "violencia contra la mujer",
                "violencia contra mujeres", "agresión sexual",
                "violación", "ataque", "brutalidad",
            ],
            # ── Alerta de género ─────────────────────────────
            'alerta_genero': [
                "alerta de género", "alerta de violencia de género",
                "AVG", "declaratoria de alerta", "alerta por feminicidio",
                "alerta de violencia contra las mujeres",
            ],
            # ── Justicia / proceso legal ─────────────────────
            'justicia': [
                "justicia", "proceso legal", "juicio", "tribunal",
                "sentencia", "condena", "absolución", "veredicto",
                "investigación", "denuncia", "querella",
                "ministerio público", "fiscalía", "procuraduría",
                "detención", "arresto", "captura", "orden de aprehensión",
                "carpeta de investigación", "vinculación a proceso",
                "prisión preventiva", "sentencia condenatoria",
            ],
            # ── Protección institucional ─────────────────────
            'proteccion': [
                "protección", "refugio", "albergue", "casa hogar", "DIF",
                "asistencia social", "custodia", "tutela", "adopción",
                "medidas cautelares", "orden de restricción", "alejamiento",
                "SIPINNA", "procuraduría de protección",
                "sistema de protección de NNA",
            ],
            # ── Relaciones familiares ────────────────────────
            'familia': [
                "madre", "mamá", "progenitora", "materna",
                "padre", "papá", "progenitor", "paterno",
                "familia", "hogar", "núcleo familiar", "parientes",
                "familiares", "esposa", "pareja", "concubina",
                "ex pareja", "ex esposa", "ex novia", "cónyuge",
            ],
            # ── Actores ─────────────────────────────────────
            'actores': [
                "víctima", "afectada", "perjudicada", "occisa",
                "agresor", "atacante", "perpetrador", "victimario",
                "criminal", "homicida", "feminicida", "asesino",
                "imputado", "acusado", "sospechoso", "presunto",
            ],
        }

        for terms in groups.values():
            self.add_synonym_group(terms)

    # ── API pública ─────────────────────────────────────────

    def add_synonym_group(self, terms: List[str]):
        """Registra un grupo de términos como sinónimos entre sí."""
        normalized = [t.lower().strip() for t in terms]
        for term in normalized:
            self.synonyms.setdefault(term, set())
            for other in normalized:
                if other != term:
                    self.synonyms[term].add(other)
            self.reverse_index[term] = term

    def get_synonyms(self, term: str) -> Set[str]:
        """Devuelve el conjunto de sinónimos (incluye el término original)."""
        key = term.lower().strip()
        if key in self.synonyms:
            return self.synonyms[key] | {key}
        # Buscar coincidencia parcial
        for k, syns in self.synonyms.items():
            if key in k or k in key:
                return syns | {k, key}
        return {key}

    def expand_search_query(self, query: str) -> List[str]:
        """
        Expande una consulta de búsqueda en una lista de
        todos los términos (originales + sinónimos).
        """
        expanded = set()
        for word in query.lower().split():
            expanded.update(self.get_synonyms(word))
        return sorted(expanded)

    def find_terms_in_text(self, text: str) -> Dict[str, List[str]]:
        """Encuentra términos conocidos en un texto."""
        lower = text.lower()
        return {
            term: list(self.get_synonyms(term))
            for term in self.synonyms
            if term in lower
        }

    # ── Persistencia ────────────────────────────────────────

    def save_to_file(self, filepath: str):
        """Guarda el diccionario a JSON."""
        data = {k: sorted(v) for k, v in self.synonyms.items()}
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_file(self, filepath: str):
        """Carga el diccionario desde JSON."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.synonyms = {k: set(v) for k, v in data.items()}
            self.reverse_index = {t: t for t in self.synonyms}
        except FileNotFoundError:
            print(f"  Archivo {filepath} no encontrado — usando sinónimos por defecto.")
        except Exception as e:
            print(f"  Error cargando diccionario: {e}")


# ── Función de búsqueda mejorada (standalone) ───────────────

def enhanced_search(
    df: pd.DataFrame,
    query: str,
    search_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Búsqueda en DataFrame usando expansión de sinónimos.
    Devuelve resultados ordenados por número de coincidencias.
    """
    if search_columns is None:
        search_columns = ['titulo', 'contenido']

    syn = SynonymDictionary()
    all_terms = syn.expand_search_query(query)

    # Contar coincidencias para ranking
    hit_count = pd.Series(0, index=df.index, dtype=int)

    for col in search_columns:
        if col not in df.columns:
            continue
        col_lower = df[col].fillna('').str.lower()
        for term in all_terms:
            matches = col_lower.str.contains(
                re.escape(term), case=False, na=False, regex=True
            )
            # Matches en título valen más
            weight = 3 if col == 'titulo' else 1
            hit_count += matches.astype(int) * weight

    mask = hit_count > 0
    result = df[mask].copy()
    result['_search_hits'] = hit_count[mask]
    result = result.sort_values('_search_hits', ascending=False)
    result = result.drop(columns=['_search_hits'])

    return result
