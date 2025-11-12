# src/analysis/synonym_dictionary.py
import json
import re
from typing import Dict, List, Set
from pathlib import Path

class SynonymDictionary:
    """
    Diccionario de sinnimos especializado para trminos relacionados con NNA,
    violencia de gnero y feminicidios.
    """
    
    def __init__(self):
        self.synonyms = {}
        self.reverse_index = {}  # Para bsqueda rpida
        self._load_default_synonyms()
    
    def _load_default_synonyms(self):
        """Carga sinnimos por defecto basados en fuentes oficiales."""
        # Trminos relacionados con feminicidio
        feminicide_terms = [
            "feminicidio", "femicidio", "asesinato de mujer", "homicidio de mujer",
            "crimen de gnero", "violencia feminicida", "muerte violenta de mujer"
        ]
        
        # Trminos relacionados con NNA
        children_terms = [
            "nios", "nias", "nia", "nio", "menores", "menor", "infantes", "infante",
            "adolescentes", "adolescente", "jvenes", "pberes", "NNA", "nna",
            "hijos", "hijas", "hijo", "hija", "bebs", "beb", "recin nacidos",
            "neonatos", "lactantes", "pequeos", "chicos", "chicas", "muchachos",
            "muchachas", "cros", "cras", "chavos", "chavas", "morritos", "morritas"
        ]
        
        # Trminos relacionados con violencia
        violence_terms = [
            "violencia", "agresin", "maltrato", "abuso", "lesiones", "golpes",
            "violencia fsica", "violencia psicolgica", "violencia sexual",
            "violencia domstica", "violencia familiar", "violencia intrafamiliar",
            "tortura", "vejaciones", "acoso", "hostigamiento"
        ]
        
        # Trminos relacionados con orfandad
        orphan_terms = [
            "hurfanos", "hurfanas", "hurfano", "hurfana", "orfandad",
            "sin padres", "sin madre", "sin padre", "abandonados", "desamparados",
            "vctimas indirectas", "vctimas colaterales", "hijos de vctimas"
        ]
        
        # Trminos relacionados con justicia
        justice_terms = [
            "justicia", "proceso legal", "juicio", "tribunal", "sentencia",
            "condena", "absolucin", "veredicto", "investigacin", "denuncia",
            "querella", "ministerio pblico", "fiscala", "procuradura",
            "detencin", "arresto", "captura", "orden de aprehensin"
        ]
        
        # Trminos relacionados con proteccin
        protection_terms = [
            "proteccin", "refugio", "albergue", "casa hogar", "DIF",
            "asistencia social", "custodia", "tutela", "adopcin",
            "medidas cautelares", "orden de restriccin", "alejamiento"
        ]
        
        # Agregar grupos de sinnimos
        self.add_synonym_group(feminicide_terms)
        self.add_synonym_group(children_terms)
        self.add_synonym_group(violence_terms)
        self.add_synonym_group(orphan_terms)
        self.add_synonym_group(justice_terms)
        self.add_synonym_group(protection_terms)
        
        # Sinnimos especficos adicionales
        specific_synonyms = {
            "madre": ["mam", "progenitora", "genitora", "materna"],
            "padre": ["pap", "progenitor", "genitor", "paterno"],
            "familia": ["hogar", "ncleo familiar", "parientes", "familiares"],
            "asesinato": ["homicidio", "crimen", "muerte violenta", "occisin"],
            "vctima": ["afectada", "perjudicada", "damnificada", "lesionada"],
            "agresor": ["atacante", "perpetrador", "victimario", "criminal"],
            "denuncia": ["acusacin", "reporte", "querella", "demanda"],
            "investigacin": ["pesquisa", "indagatoria", "averiguacin"],
            "evidencia": ["prueba", "indicio", "elemento probatorio"],
            "testigo": ["declarante", "deponente", "informante"]
        }
        
        for main_term, synonyms in specific_synonyms.items():
            self.add_synonym_group([main_term] + synonyms)
    
    def add_synonym_group(self, terms: List[str]):
        """
        Agrega un grupo de trminos sinnimos.
        
        Args:
            terms: Lista de trminos que son sinnimos entre s
        """
        # Normalizar trminos
        normalized_terms = [self._normalize_term(term) for term in terms]
        
        # Cada trmino en el grupo es sinnimo de todos los dems
        for term in normalized_terms:
            if term not in self.synonyms:
                self.synonyms[term] = set()
            
            # Agregar todos los otros trminos como sinnimos
            for other_term in normalized_terms:
                if other_term != term:
                    self.synonyms[term].add(other_term)
            
            # Actualizar ndice reverso
            self.reverse_index[term] = term
    
    def _normalize_term(self, term: str) -> str:
        """Normaliza un trmino para bsqueda consistente."""
        return term.lower().strip()
    
    def get_synonyms(self, term: str) -> Set[str]:
        """
        Obtiene todos los sinnimos de un trmino.
        
        Args:
            term: Trmino de bsqueda
            
        Returns:
            Conjunto de sinnimos (incluyendo el trmino original)
        """
        normalized_term = self._normalize_term(term)
        
        if normalized_term in self.synonyms:
            result = self.synonyms[normalized_term].copy()
            result.add(normalized_term)
            return result
        
        return {normalized_term}
    
    def expand_search_query(self, query: str) -> str:
        """
        Expande una consulta de bsqueda incluyendo sinnimos.
        
        Args:
            query: Consulta de bsqueda original
            
        Returns:
            Consulta expandida con sinnimos
        """
        words = query.lower().split()
        expanded_terms = []
        
        for word in words:
            synonyms = self.get_synonyms(word)
            if len(synonyms) > 1:
                # Si hay sinnimos, crear una expresin OR
                synonym_list = list(synonyms)
                expanded_terms.append(f"({' OR '.join(synonym_list)})")
            else:
                expanded_terms.append(word)
        
        return ' '.join(expanded_terms)
    
    def find_terms_in_text(self, text: str) -> Dict[str, List[str]]:
        """
        Encuentra trminos conocidos y sus sinnimos en un texto.
        
        Args:
            text: Texto a analizar
            
        Returns:
            Diccionario con trminos encontrados y sus sinnimos
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
        # Convertir sets a listas para serializacin JSON
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
            
            # Reconstruir ndice reverso
            self.reverse_index = {term: term for term in self.synonyms.keys()}
            
        except FileNotFoundError:
            print(f"Archivo {filepath} no encontrado. Usando sinnimos por defecto.")
        except Exception as e:
            print(f"Error cargando diccionario: {e}. Usando sinnimos por defecto.")

# Funcin de utilidad para bsqueda mejorada
def enhanced_search(df, query: str, search_columns: List[str] = None):
    """
    Realiza bsqueda mejorada usando sinnimos.
    
    Args:
        df: DataFrame a buscar
        query: Consulta de bsqueda
        search_columns: Columnas donde buscar (por defecto: titulo, contenido)
        
    Returns:
        DataFrame filtrado con resultados
    """
    # Importar pandas localmente para evitar errores de importacin
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("Pandas requerido para enhanced_search")
        
    if search_columns is None:
        search_columns = ['titulo', 'contenido']
    
    # Inicializar diccionario de sinnimos
    synonym_dict = SynonymDictionary()
    
    # Expandir consulta con sinnimos
    expanded_query = synonym_dict.expand_search_query(query)
    
    # Realizar bsqueda en las columnas especificadas
    mask = pd.Series([False] * len(df))
    
    for column in search_columns:
        if column in df.columns:
            # Bsqueda simple por trminos (se puede mejorar con regex)
            column_mask = df[column].str.contains(
                query, case=False, na=False, regex=False
            )
            
            # Tambin buscar sinnimos
            for word in query.lower().split():
                synonyms = synonym_dict.get_synonyms(word)
                for synonym in synonyms:
                    synonym_mask = df[column].str.contains(
                        synonym, case=False, na=False, regex=False
                    )
                    column_mask = column_mask | synonym_mask
            
            mask = mask | column_mask
    
    return df[mask]

# Importar pandas solo si est disponible
try:
    import pandas as pd
except ImportError:
    print("Pandas no est instalado. La funcin enhanced_search no estar disponible.")
    def enhanced_search(*args, **kwargs):
        raise ImportError("Pandas requerido para enhanced_search")
