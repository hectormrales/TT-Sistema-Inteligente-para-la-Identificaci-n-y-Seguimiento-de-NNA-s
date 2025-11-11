"""
Detector especializado de noticias sobre feminicidios con víctimas indirectas (NNA huérfanos).

Este módulo implementa lógica específica para identificar noticias que cumplan el objetivo:
- Feminicidio/asesinato de mujer
- Con NNA afectados (especialmente huérfanos)
- Víctimas indirectas de violencia feminicida

Autor: Héctor Morales
Fecha: 11 de noviembre de 2025
"""

import re
from typing import Dict, List, Tuple

class FeminicideDetector:
    """
    Detector especializado para identificar noticias sobre feminicidios
    con énfasis en víctimas indirectas (NNA huérfanos).
    """
    
    def __init__(self):
        """Inicializa patrones de detección."""
        self._load_patterns()
    
    def _load_patterns(self):
        """Carga patrones regex para detección."""
        
        # PATRONES DE FEMINICIDIO
        self.feminicide_patterns = [
            # Términos directos
            r'\bfeminicidio[s]?\b',
            r'\bfemicidio[s]?\b',
            
            # Contextos de asesinato de mujer
            r'\bmujer\s+(asesinada|hallada\s+muerta|encontrada\s+sin\s+vida)',
            r'\basesinat[oa]\s+.*?\s+(mujer|femenina)',
            r'\bmadre\s+(asesinada|muerta|asesinato|hallada)',
            r'\bhomicidio\s+de\s+mujer',
            r'\bmujer\s+(v[ií]ctima|fallecida)\s+(de|por)\s+(violencia|crimen)',
            
            # Términos especializados
            r'\bviolencia\s+feminicida',
            r'\bcrimen\s+de\s+g[eé]nero',
            r'\bmachismo\s+letal',
            r'\bfemini[sc]idio\s+infantil',  # Caso especial
            
            # Contextos investigación/justicia
            r'\bcarpeta\s+de\s+investigaci[oó]n.*feminicidio',
            r'\bfiscal[ií]a.*feminicidio',
            r'\binvestiga.*feminicidio',
            r'\balerta.*feminicidio',
            r'\balerta\s+de\s+g[eé]nero',
        ]
        
        # PATRONES DE NNA/HIJOS
        self.children_patterns = [
            r'\bhij[oa]s?\b',
            r'\bmenor[es]?\s+(de\s+edad)?',
            r'\bniñ[oa]s?\b',
            r'\badolescente[s]?\b',
            r'\bbeb[ée][s]?\b',
            r'\binf antes?\b',
            r'\breci[eé]n\s+nacid[oa]s?\b',
            r'\bpeque[ñn][oa]s?\b',
            r'\bcr[ií][oa]s?\b',
        ]
        
        # PATRONES DE ORFANDAD/VÍCTIMAS INDIRECTAS (CRÍTICO)
        self.orphan_patterns = [
            # Orfandad directa
            r'\bhu[eé]rfan[oa]s?\b',
            r'\borfan[oa]s?\b',
            r'\borfandad\b',
            
            # Contextos de abandono/desamparo
            r'\bhij[oa]s?\s+(quedan|quedaron|qued[oó])',
            r'\bmenor[es]?\s+(quedan|quedaron|qued[oó])',
            r'\bniñ[oa]s?\s+(quedan|quedaron|qued[oó])',
            r'\bdesamparad[oa]s?\b',
            r'\babandonad[oa]s?\b',
            
            # Sin madre/padre
            r'\bsin\s+(madre|mam[áa]|pap[áa]|padre)',
            r'\bhij[oa]s?\s+sin\s+madre',
            r'\bmenor[es]?\s+sin\s+madre',
            
            # Víctimas indirectas (término clave)
            r'\bv[ií]ctima[s]?\s+indirecta[s]?\b',
            r'\bv[ií]ctima[s]?\s+colateral[es]?\b',
            r'\bafectad[oa]s?\s+por\s+(el|la)\s+feminicidio',
            
            # Custodia/tutela
            r'\bcustodia\s+(de|del|de\s+los)',
            r'\bal\s+cuidado\s+de',
            r'\btutela\s+de',
            r'\bguarda\s+y\s+custodia',
            r'\bfamiliares\s+(se\s+hacen\s+cargo|cuidan)',
            
            # DIF/instituciones
            r'\bDIF\s+(se\s+hace\s+cargo|atiende|custodia)',
            r'\balbergue\s+para\s+(menores|niños)',
            r'\bcasa\s+hogar',
            
            # Contextos emocionales
            r'\bni[ñn][oa]s?\s+(lloran|presenciaron|encontraron)',
            r'\bhij[oa]s?\s+(llorando|traumatizad[oa]s)',
            r'\bmenor[es]?\s+(testigo|present[oó])',
        ]
        
        # CONTEXTOS REFORZADORES (mejoran confianza)
        self.reinforcing_contexts = [
            r'\bmadre\s+(y|de)\s+tres\s+(hijos|niños|menores)',
            r'\bmadre\s+(y|de)\s+dos\s+(hijos|niños|menores)',
            r'\bmadre\s+soltera',
            r'\bmadre\s+de\s+familia',
            r'\bfamilia\s+destrozada',
            r'\btragedia\s+familiar',
            r'\bdej[oó]\s+hu[eé]rfan[oa]s',
            r'\bquedan\s+al\s+cuidado\s+de',
        ]
        
        # PATRONES DE EXCLUSIÓN (falsos positivos)
        self.exclusion_patterns = [
            # Noticias políticas
            r'\bcampañ?a\s+pol[ií]tica',
            r'\belecciones\s+(federales|estatales)',
            r'\bpresidente\s+(municipal|estatal)',
            
            # Noticias deportivas
            r'\bpartido\s+de\s+(f[uú]tbol|basquetbol)',
            r'\btorneo\s+(de|deportivo)',
            r'\bchampions\s+league',
            
            # Noticias económicas
            r'\bbolsa\s+de\s+valores',
            r'\btipo\s+de\s+cambio',
            r'\binversi[oó]n\s+(extranjera|nacional)',
            
            # Noticias culturales/entretenimiento
            r'\bpremio\s+(nobel|oscar|grammy)',
            r'\bfestival\s+de\s+(cine|m[uú]sica)',
            r'\bconcierto\s+de',
        ]
    
    def detect(self, text: str) -> Dict[str, any]:
        """
        Detecta si una noticia trata sobre feminicidio con víctimas indirectas NNA.
        
        Args:
            text: Texto completo de la noticia (título + contenido)
            
        Returns:
            Diccionario con:
            - is_feminicide: bool - ¿Menciona feminicidio?
            - has_children: bool - ¿Menciona NNA?
            - has_orphans: bool - ¿Menciona huérfanos/víctimas indirectas?
            - is_target_news: bool - ¿Es noticia objetivo? (feminicidio + NNA)
            - confidence: float - Nivel de confianza (0.0-1.0)
            - matched_patterns: list - Patrones que coincidieron
        """
        if not text or not isinstance(text, str):
            return self._empty_result()
        
        text_lower = text.lower()
        
        # Verificar exclusiones primero
        if self._has_exclusion(text_lower):
            return self._empty_result()
        
        # Detectar componentes
        feminicide_matches = self._find_matches(text_lower, self.feminicide_patterns)
        children_matches = self._find_matches(text_lower, self.children_patterns)
        orphan_matches = self._find_matches(text_lower, self.orphan_patterns)
        reinforcing_matches = self._find_matches(text_lower, self.reinforcing_contexts)
        
        # Flags booleanos
        is_feminicide = len(feminicide_matches) > 0
        has_children = len(children_matches) > 0
        has_orphans = len(orphan_matches) > 0
        has_reinforcing = len(reinforcing_matches) > 0
        
        # Noticia objetivo: DEBE tener feminicidio + (NNA O huérfanos)
        is_target = is_feminicide and (has_children or has_orphans)
        
        # Calcular confianza
        confidence = self._calculate_confidence(
            is_feminicide, has_children, has_orphans, has_reinforcing,
            len(feminicide_matches), len(children_matches), 
            len(orphan_matches), len(reinforcing_matches)
        )
        
        # Recopilar patrones que coincidieron
        matched_patterns = {
            'feminicide': feminicide_matches,
            'children': children_matches,
            'orphans': orphan_matches,
            'reinforcing': reinforcing_matches
        }
        
        return {
            'is_feminicide': is_feminicide,
            'has_children': has_children,
            'has_orphans': has_orphans,
            'is_target_news': is_target,
            'confidence': round(confidence, 3),
            'matched_patterns': matched_patterns,
            'priority': self._calculate_priority(is_feminicide, has_orphans, confidence)
        }
    
    def _find_matches(self, text: str, patterns: List[str]) -> List[str]:
        """Encuentra coincidencias de patrones en texto."""
        matches = []
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matches.append(pattern)
        return matches
    
    def _has_exclusion(self, text: str) -> bool:
        """Verifica si el texto contiene patrones de exclusión."""
        return any(re.search(p, text, re.IGNORECASE) for p in self.exclusion_patterns)
    
    def _calculate_confidence(
        self, 
        is_fem: bool, has_child: bool, has_orph: bool, has_reinf: bool,
        num_fem: int, num_child: int, num_orph: int, num_reinf: int
    ) -> float:
        """
        Calcula nivel de confianza de la detección.
        
        Lógica:
        - Feminicidio = base 40%
        - NNA = +20%
        - Huérfanos = +30% (más importante)
        - Reforzadores = +10%
        - Múltiples coincidencias = bonus
        """
        score = 0.0
        
        # Componente feminicidio (40% máximo)
        if is_fem:
            score += 0.30  # Base
            if num_fem >= 2:  # Múltiples menciones
                score += 0.05
            if num_fem >= 3:
                score += 0.05
        
        # Componente NNA (20% máximo)
        if has_child:
            score += 0.15
            if num_child >= 2:
                score += 0.05
        
        # Componente huérfanos/víctimas indirectas (30% máximo)
        if has_orph:
            score += 0.25  # Mayor peso
            if num_orph >= 2:
                score += 0.05
        
        # Contextos reforzadores (10% máximo)
        if has_reinf:
            score += 0.05
            if num_reinf >= 2:
                score += 0.05
        
        # Bonus por combinación perfecta
        if is_fem and has_child and has_orph:
            score += 0.10  # Caso ideal
        
        return min(score, 1.0)  # Máximo 1.0
    
    def _calculate_priority(self, is_fem: bool, has_orph: bool, confidence: float) -> str:
        """
        Calcula prioridad de la noticia.
        
        Returns:
            'ALTA', 'MEDIA', 'BAJA', 'IRRELEVANTE'
        """
        if is_fem and has_orph and confidence >= 0.7:
            return 'ALTA'  # Feminicidio + huérfanos + confianza alta
        elif is_fem and has_orph:
            return 'MEDIA'  # Feminicidio + huérfanos pero confianza baja
        elif is_fem and confidence >= 0.5:
            return 'MEDIA'  # Feminicidio sin mención clara de huérfanos
        elif is_fem:
            return 'BAJA'  # Feminicidio pero poca certeza
        else:
            return 'IRRELEVANTE'  # No es feminicidio
    
    def _empty_result(self) -> Dict[str, any]:
        """Retorna resultado vacío para exclusiones."""
        return {
            'is_feminicide': False,
            'has_children': False,
            'has_orphans': False,
            'is_target_news': False,
            'confidence': 0.0,
            'matched_patterns': {},
            'priority': 'IRRELEVANTE'
        }


# Función de utilidad para uso directo
def detect_feminicide_news(text: str) -> Dict[str, any]:
    """
    Función de conveniencia para detección de feminicidios.
    
    Args:
        text: Texto de la noticia
        
    Returns:
        Resultado de detección
    """
    detector = FeminicideDetector()
    return detector.detect(text)


# Ejemplo de uso
if __name__ == "__main__":
    # Casos de prueba
    test_cases = [
        {
            'title': 'Feminicidio en Ecatepec deja tres hijos huérfanos',
            'content': 'Una mujer fue asesinada por su expareja. Los tres menores quedaron al cuidado de familiares.',
            'expected': True
        },
        {
            'title': 'Menor gana premio de matemáticas',
            'content': 'Adolescente de 15 años obtiene primer lugar en olimpiada.',
            'expected': False
        },
        {
            'title': 'Hallan muerta a madre de dos niños',
            'content': 'Fiscalía investiga feminicidio. Los menores presenciaron el crimen.',
            'expected': True
        }
    ]
    
    detector = FeminicideDetector()
    
    print("="*80)
    print("PRUEBAS DE DETECTOR DE FEMINICIDIOS")
    print("="*80)
    
    for idx, case in enumerate(test_cases, 1):
        text = f"{case['title']} {case['content']}"
        result = detector.detect(text)
        
        print(f"\n📰 Caso {idx}:")
        print(f"   Título: {case['title']}")
        print(f"   Esperado: {'✅ OBJETIVO' if case['expected'] else '❌ NO OBJETIVO'}")
        print(f"\n   Resultado:")
        print(f"   - Es feminicidio: {result['is_feminicide']}")
        print(f"   - Tiene NNA: {result['has_children']}")
        print(f"   - Tiene huérfanos: {result['has_orphans']}")
        print(f"   - ES OBJETIVO: {result['is_target_news']} ({'✅' if result['is_target_news'] else '❌'})")
        print(f"   - Confianza: {result['confidence']:.1%}")
        print(f"   - Prioridad: {result['priority']}")
        
        if result['is_target_news'] == case['expected']:
            print(f"   ✅ CORRECTO")
        else:
            print(f"   ❌ ERROR - Se esperaba {case['expected']}")
