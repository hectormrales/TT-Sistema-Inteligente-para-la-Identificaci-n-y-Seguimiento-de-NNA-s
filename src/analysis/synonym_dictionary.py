# src/analysis/synonym_dictionary.py
import json
import re
from typing import Dict, List, Set
from pathlib import Path

class SynonymDictionary:
    """
    Diccionario de sinónimos especializado para términos relacionados con NNA,
    violencia de género y feminicidios.
    """
    
    def __init__(self):
        self.synonyms = {}
        self.reverse_index = {}  # Para búsqueda rápida
        self._load_default_synonyms()
    
    def _load_default_synonyms(self):
        """Carga sinónimos por defecto basados en fuentes oficiales."""
        # Términos relacionados con feminicidio
        feminicide_terms = [
            "feminicidio", "femicidio", "asesinato de mujer", "homicidio de mujer",
            "crimen de género", "violencia feminicida", "muerte violenta de mujer"
        ]
        
        # Términos relacionados con NNA
        children_terms = [
            "niños", "niñas", "niña", "niño", "menores", "menor", "infantes", "infante",
            "adolescentes", "adolescente", "jóvenes", "púberes", "NNA", "nna",
            "hijos", "hijas", "hijo", "hija", "bebés", "bebé", "recién nacidos",
            "neonatos", "lactantes", "pequeños", "chicos", "chicas", "muchachos",
            "muchachas", "críos", "crías", "chavos", "chavas", "morritos", "morritas"
        ]
        
        # Términos relacionados con violencia
        violence_terms = [
            "violencia", "agresión", "maltrato", "abuso", "lesiones", "golpes",
            "violencia física", "violencia psicológica", "violencia sexual",
            "violencia doméstica", "violencia familiar", "violencia intrafamiliar",
            "tortura", "vejaciones", "acoso", "hostigamiento"
        ]
        
        # Términos relacionados con orfandad
        orphan_terms = [
            "huérfanos", "huérfanas", "huérfano", "huérfana", "orfandad",
            "sin padres", "sin madre", "sin padre", "abandonados", "desamparados",
            "víctimas indirectas", "víctimas colaterales", "hijos de víctimas"
        ]
        
        # Términos relacionados con justicia
        justice_terms = [
            "justicia", "proceso legal", "juicio", "tribunal", "sentencia",
            "condena", "absolución", "veredicto", "investigación", "denuncia",
            "querella", "ministerio público", "fiscalía", "procuraduría",
            "detención", "arresto", "captura", "orden de aprehensión"
        ]
        
        # Términos relacionados con protección
        protection_terms = [
            "protección", "refugio", "albergue", "casa hogar", "DIF",
            "asistencia social", "custodia", "tutela", "adopción",
            "medidas cautelares", "orden de restricción", "alejamiento"
        ]
        
        # Agregar grupos de sinónimos
        self.add_synonym_group(feminicide_terms)
        self.add_synonym_group(children_terms)
        self.add_synonym_group(violence_terms)
        self.add_synonym_group(orphan_terms)
        self.add_synonym_group(justice_terms)
        self.add_synonym_group(protection_terms)
        
        # Sinónimos específicos adicionales
        specific_synonyms = {
            "madre": ["mamá", "progenitora", "genitora", "materna"],
            "padre": ["papá", "progenitor", "genitor", "paterno"],
            "familia": ["hogar", "núcleo familiar", "parientes", "familiares"],
            "asesinato": ["homicidio", "crimen", "muerte violenta", "occisión"],
            "víctima": ["afectada", "perjudicada", "damnificada", "lesionada"],
            "agresor": ["atacante", "perpetrador", "victimario", "criminal"],
            "denuncia": ["acusación", "reporte", "querella", "demanda"],
            "investigación": ["pesquisa", "indagatoria", "averiguación"],
            "evidencia": ["prueba", "indicio", "elemento probatorio"],
            "testigo": ["declarante", "deponente", "informante"]
        }
        
        for main_term, synonyms in specific_synonyms.items():
            self.add_synonym_group([main_term] + synonyms)
    
    def add_synonym_group(self, terms: List[str]):
        """
        Agrega un grupo de términos sinónimos.
        
        Args:
            terms: Lista de términos que son sinónimos entre sí
        """
        # Normalizar términos
        normalized_terms = [self._normalize_term(term) for term in terms]
        
        # Cada término en el grupo es sinónimo de todos los demás
        for term in normalized_terms:
            if term not in self.synonyms:
                self.synonyms[term] = set()
            
            # Agregar todos los otros términos como sinónimos
            for other_term in normalized_terms:
                if other_term != term:
                    self.synonyms[term].add(other_term)
            
            # Actualizar índice reverso
            self.reverse_index[term] = term
    
    def _normalize_term(self, term: str) -> str:
        """Normaliza un término para búsqueda consistente."""
        return term.lower().strip()
    
    def get_synonyms(self, term: str) -> Set[str]:
        """
        Obtiene todos los sinónimos de un término.
        
        Args:
            term: Término de búsqueda
            
        Returns:
            Conjunto de sinónimos (incluyendo el término original)
        """
        normalized_term = self._normalize_term(term)
        
        if normalized_term in self.synonyms:
            result = self.synonyms[normalized_term].copy()
            result.add(normalized_term)
            return result
        
        return {normalized_term}
    
    def expand_search_query(self, query: str) -> str:
        """
        Expande una consulta de búsqueda incluyendo sinónimos.
        
        Args:
            query: Consulta de búsqueda original
            
        Returns:
            Consulta expandida con sinónimos
        """
        words = query.lower().split()
        expanded_terms = []
        
        for word in words:
            synonyms = self.get_synonyms(word)
            if len(synonyms) > 1:
                # Si hay sinónimos, crear una expresión OR
                synonym_list = list(synonyms)
                expanded_terms.append(f"({' OR '.join(synonym_list)})")
            else:
                expanded_terms.append(word)
        
        return ' '.join(expanded_terms)
    
    def find_terms_in_text(self, text: str) -> Dict[str, List[str]]:
        """
        Encuentra términos conocidos y sus sinónimos en un texto.
        
        Args:
            text: Texto a analizar
            
        Returns:
            Diccionario con términos encontrados y sus sinónimos
        """
        normalized_text = text.lower()
        found_terms = {}
        
        for term in self.synonyms.keys():
            if term in normalized_text:
                synonyms = list(self.get_synonyms(term))
                found_terms[term] = synonyms
        
        return found_terms
    
    def save_to_file(self, filepath: str):
        """Guarda el diccionario en un archivo JSON."""
        # Convertir sets a listas para serialización JSON
        serializable_synonyms = {
            term: list(synonyms) for term, synonyms in self.synonyms.items()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(serializable_synonyms, f, ensure_ascii=False, indent=2)
    
    def load_from_file(self, filepath: str):
        """Carga el diccionario desde un archivo JSON."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convertir listas de vuelta a sets
            self.synonyms = {
                term: set(synonyms) for term, synonyms in data.items()
            }
            
            # Reconstruir índice reverso
            self.reverse_index = {term: term for term in self.synonyms.keys()}
            
        except FileNotFoundError:
            print(f"Archivo {filepath} no encontrado. Usando sinónimos por defecto.")
        except Exception as e:
            print(f"Error cargando diccionario: {e}. Usando sinónimos por defecto.")

# Función de utilidad para búsqueda mejorada
def enhanced_search(df, query: str, search_columns: List[str] = None):
    """
    Realiza búsqueda mejorada usando sinónimos.
    
    Args:
        df: DataFrame a buscar
        query: Consulta de búsqueda
        search_columns: Columnas donde buscar (por defecto: titulo, contenido)
        
    Returns:
        DataFrame filtrado con resultados
    """
    # Importar pandas localmente para evitar errores de importación
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("Pandas requerido para enhanced_search")
        
    if search_columns is None:
        search_columns = ['titulo', 'contenido']
    
    # Inicializar diccionario de sinónimos
    synonym_dict = SynonymDictionary()
    
    # Expandir consulta con sinónimos
    expanded_query = synonym_dict.expand_search_query(query)
    
    # Realizar búsqueda en las columnas especificadas
    mask = pd.Series([False] * len(df))
    
    for column in search_columns:
        if column in df.columns:
            # Búsqueda simple por términos (se puede mejorar con regex)
            column_mask = df[column].str.contains(
                query, case=False, na=False, regex=False
            )
            
            # También buscar sinónimos
            for word in query.lower().split():
                synonyms = synonym_dict.get_synonyms(word)
                for synonym in synonyms:
                    synonym_mask = df[column].str.contains(
                        synonym, case=False, na=False, regex=False
                    )
                    column_mask = column_mask | synonym_mask
            
            mask = mask | column_mask
    
    return df[mask]

# Importar pandas solo si está disponible
try:
    import pandas as pd
except ImportError:
    print("Pandas no está instalado. La función enhanced_search no estará disponible.")
    def enhanced_search(*args, **kwargs):
        raise ImportError("Pandas requerido para enhanced_search")