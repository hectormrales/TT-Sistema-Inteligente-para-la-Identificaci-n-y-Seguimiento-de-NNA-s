"""
Detector especializado de noticias sobre feminicidios con vctimas indirectas (NNA hurfanos).

Este mdulo implementa lgica especfica para identificar noticias que cumplan el objetivo:
- Feminicidio/asesinato de mujer
- Con NNA afectados (especialmente hurfanos)
- Vctimas indirectas de violencia feminicida

Autor: Hctor Morales
Fecha: 11 de noviembre de 2025
"""

import re
from typing import Dict, List, Tuple

class FeminicideDetector:
    """
    Detector especializado para identificar noticias sobre feminicidios
    con nfasis en vctimas indirectas (NNA hurfanos).
    """
    
    def __init__(self):
        """Inicializa patrones de deteccin."""
        self._load_patterns()
    
    def _load_patterns(self):
        """Carga patrones regex para deteccin."""
        
        # PATRONES DE FEMINICIDIO
        self.feminicide_patterns = [
            # Trminos directos
            r'\bfeminicidio[s]?\b',
            r'\bfemicidio[s]?\b',
            
            # Contextos de asesinato de mujer
            r'\bmujer\s+(asesinada|hallada\s+muerta|encontrada\s+sin\s+vida)',
            r'\basesinat[oa]\s+.*?\s+(mujer|femenina)',
            r'\bmadre\s+(asesinada|muerta|asesinato|hallada)',
            r'\bhomicidio\s+de\s+mujer',
            r'\bmujer\s+(v[i]ctima|fallecida)\s+(de|por)\s+(violencia|crimen)',
            
            # Trminos especializados
            r'\bviolencia\s+feminicida',
            r'\bcrimen\s+de\s+g[e]nero',
            r'\bmachismo\s+letal',
            r'\bfemini[sc]idio\s+infantil',  # Caso especial
            
            # Contextos investigacin/justicia
            r'\bcarpeta\s+de\s+investigaci[o]n.*feminicidio',
            r'\bfiscal[i]a.*feminicidio',
            r'\binvestiga.*feminicidio',
            r'\balerta.*feminicidio',
            r'\balerta\s+de\s+g[e]nero',
        ]
        
        # PATRONES DE NNA/HIJOS
        self.children_patterns = [
            r'\bhij[oa]s?\b',
            r'\bmenor[es]?\s+(de\s+edad)?',
            r'\bni[oa]s?\b',
            r'\badolescente[s]?\b',
            r'\bbeb[e][s]?\b',
            r'\binf antes?\b',
            r'\breci[e]n\s+nacid[oa]s?\b',
            r'\bpeque[n][oa]s?\b',
            r'\bcr[i][oa]s?\b',
        ]
        
        # PATRONES DE ORFANDAD/VCTIMAS INDIRECTAS (CRTICO)
        self.orphan_patterns = [
            # Orfandad directa
            r'\bhu[e]rfan[oa]s?\b',
            r'\borfan[oa]s?\b',
            r'\borfandad\b',
            
            # Contextos de abandono/desamparo
            r'\bhij[oa]s?\s+(quedan|quedaron|qued[o])',
            r'\bmenor[es]?\s+(quedan|quedaron|qued[o])',
            r'\bni[oa]s?\s+(quedan|quedaron|qued[o])',
            r'\bdesamparad[oa]s?\b',
            r'\babandonad[oa]s?\b',
            
            # Sin madre/padre
            r'\bsin\s+(madre|mam[a]|pap[a]|padre)',
            r'\bhij[oa]s?\s+sin\s+madre',
            r'\bmenor[es]?\s+sin\s+madre',
            
            # Vctimas indirectas (trmino clave)
            r'\bv[i]ctima[s]?\s+indirecta[s]?\b',
            r'\bv[i]ctima[s]?\s+colateral[es]?\b',
            r'\bafectad[oa]s?\s+por\s+(el|la)\s+feminicidio',
            
            # Custodia/tutela
            r'\bcustodia\s+(de|del|de\s+los)',
            r'\bal\s+cuidado\s+de',
            r'\btutela\s+de',
            r'\bguarda\s+y\s+custodia',
            r'\bfamiliares\s+(se\s+hacen\s+cargo|cuidan)',
            
            # DIF/instituciones
            r'\bDIF\s+(se\s+hace\s+cargo|atiende|custodia)',
            r'\balbergue\s+para\s+(menores|nios)',
            r'\bcasa\s+hogar',
            
            # Contextos emocionales
            r'\bni[n][oa]s?\s+(lloran|presenciaron|encontraron)',
            r'\bhij[oa]s?\s+(llorando|traumatizad[oa]s)',
            r'\bmenor[es]?\s+(testigo|present[o])',
        ]
        
        # CONTEXTOS REFORZADORES (mejoran confianza)
        self.reinforcing_contexts = [
            r'\bmadre\s+(y|de)\s+tres\s+(hijos|nios|menores)',
            r'\bmadre\s+(y|de)\s+dos\s+(hijos|nios|menores)',
            r'\bmadre\s+soltera',
            r'\bmadre\s+de\s+familia',
            r'\bfamilia\s+destrozada',
            r'\btragedia\s+familiar',
            r'\bdej[o]\s+hu[e]rfan[oa]s',
            r'\bquedan\s+al\s+cuidado\s+de',
        ]
        
        # PATRONES DE EXCLUSIN (falsos positivos)
        self.exclusion_patterns = [
            # Noticias polticas
            r'\bcampa?a\s+pol[i]tica',
            r'\belecciones\s+(federales|estatales)',
            r'\bpresidente\s+(municipal|estatal)',
            
            # Noticias deportivas
            r'\bpartido\s+de\s+(f[u]tbol|basquetbol)',
            r'\btorneo\s+(de|deportivo)',
            r'\bchampions\s+league',
            
            # Noticias econmicas
            r'\bbolsa\s+de\s+valores',
            r'\btipo\s+de\s+cambio',
            r'\binversi[o]n\s+(extranjera|nacional)',
            
            # Noticias culturales/entretenimiento
            r'\bpremio\s+(nobel|oscar|grammy)',
            r'\bfestival\s+de\s+(cine|m[u]sica)',
            r'\bconcierto\s+de',
            
            # Estadísticas y reportes generales (NUEVO - casos NO individuales)
            r'\bconcentra\s+(la\s+)?cuarta\s+parte',
            r'\bestadística[s]?\s+(de|sobre|señala|revela)',
            r'\bporcentaje\s+(de|del)',
            r'\b\d+%\s+(de\s+las|son|corresponde)',
            r'\bdatos?\s+(del|de\s+la)\s+(INEGI|gobierno)',
            r'\breporte\s+(nacional|anual|trimestral)',
            r'\bregistr[oa]\s+oficial',
            r'\bcifras?\s+(oficial[es]?|nacional[es]?)',
            r'\bsegún\s+(el\s+)?INEGI',
            r'\bsegún\s+(las\s+)?cifras',
            r'\btrata\s+de\s+(personas|blancas)',  # Trata != feminicidio directo
            r'\bv[i]ctima[s]?\s+de\s+trata',
            
            # Noticias sobre programas/políticas (no casos individuales)
            r'\bprograma\s+(social|de\s+gobierno)',
            r'\bpol[i]tica\s+p[u]blica',
            r'\biniciativa\s+de\s+ley',
            r'\breforma\s+(legal|constitucional)',
            r'\bcampa[ñ]a\s+(de\s+concientizaci[óo]n|social)',
        ]
        
        # PATRONES DE MÉXICO (para filtrar solo noticias de México)
        self.mexico_patterns = [
            r'\bm[eé]xico\b',
            r'\bmexican[oa]s?\b',
            r'\bcdmx\b',
            r'\bciudad\s+de\s+m[eé]xico\b',
            # Estados de México
            r'\baguascalientes\b', r'\bbaja\s+california\b', r'\bcampeche\b',
            r'\bchiapas\b', r'\bchihuahua\b', r'\bcoahuila\b', r'\bcolima\b',
            r'\bdurango\b', r'\bguanajuato\b', r'\bguerrero\b', r'\bhidalgo\b',
            r'\bjalisco\b', r'\bedomex\b', r'\bestado\s+de\s+m[eé]xico\b',
            r'\bmichoac[aá]n\b', r'\bmorelos\b', r'\bnayarit\b', r'\bnuevo\s+le[oó]n\b',
            r'\boaxaca\b', r'\bpuebla\b', r'\bquer[eé]taro\b', r'\bquintana\s+roo\b',
            r'\bsan\s+luis\s+potos[ií]\b', r'\bsinaloa\b', r'\bsonora\b',
            r'\btabasco\b', r'\btamaulipas\b', r'\btlaxcala\b', r'\bveracruz\b',
            r'\byucat[aá]n\b', r'\bzacatecas\b',
        ]
        
        # PATRONES DE OTROS PAÍSES (para excluir noticias de fuera de México)
        self.other_countries_patterns = [
            r'\bargentina\b', r'\bbolivia\b', r'\bbrasil\b', r'\bchile\b',
            r'\bcolombia\b', r'\bcosta\s+rica\b', r'\bcuba\b', r'\becuador\b',
            r'\bel\s+salvador\b', r'\bespa[ñn]a\b', r'\bguatemala\b', r'\bhonduras\b',
            r'\bnicaragua\b', r'\bpanam[aá]\b', r'\bparaguay\b', r'\bper[uú]\b',
            r'\bpuerto\s+rico\b', r'\brepública\s+dominicana\b', r'\buruguay\b',
            r'\bvenezuela\b', r'\bestados\s+unidos\b', r'\busa\b', r'\bu\.s\.\b',
            r'\bcanad[aá]\b', r'\blondres\b', r'\bpar[ií]s\b', r'\bmadrid\b',
        ]
    
    def is_from_mexico(self, text: str) -> bool:
        """
        Verifica si la noticia es de México.
        
        Args:
            text: Texto de la noticia
            
        Returns:
            True si menciona México o sus estados, False si menciona otros países
        """
        if not text or not isinstance(text, str):
            return False
            
        text_lower = text.lower()
        
        # Verificar si menciona otros países (excluir)
        has_other_country = self._find_matches(text_lower, self.other_countries_patterns)
        if has_other_country:
            return False
        
        # Verificar si menciona México
        has_mexico = self._find_matches(text_lower, self.mexico_patterns)
        return len(has_mexico) > 0
    
    def detect(self, text: str) -> Dict[str, any]:
        """
        Detecta si una noticia trata sobre feminicidio con vctimas indirectas NNA.
        
        Args:
            text: Texto completo de la noticia (ttulo + contenido)
            
        Returns:
            Diccionario con:
            - is_feminicide: bool - Menciona feminicidio?
            - has_children: bool - Menciona NNA?
            - has_orphans: bool - Menciona hurfanos/vctimas indirectas?
            - is_target_news: bool - Es noticia objetivo? (feminicidio + NNA)
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
        
        # Noticia objetivo: DEBE tener feminicidio + (NNA O hurfanos)
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
        """Verifica si el texto contiene patrones de exclusin."""
        return any(re.search(p, text, re.IGNORECASE) for p in self.exclusion_patterns)
    
    def _calculate_confidence(
        self, 
        is_fem: bool, has_child: bool, has_orph: bool, has_reinf: bool,
        num_fem: int, num_child: int, num_orph: int, num_reinf: int
    ) -> float:
        """
        Calcula nivel de confianza de la deteccin.
        
        Lgica:
        - Feminicidio = base 40%
        - NNA = +20%
        - Hurfanos = +30% (ms importante)
        - Reforzadores = +10%
        - Mltiples coincidencias = bonus
        """
        score = 0.0
        
        # Componente feminicidio (40% mximo)
        if is_fem:
            score += 0.30  # Base
            if num_fem >= 2:  # Mltiples menciones
                score += 0.05
            if num_fem >= 3:
                score += 0.05
        
        # Componente NNA (20% mximo)
        if has_child:
            score += 0.15
            if num_child >= 2:
                score += 0.05
        
        # Componente hurfanos/vctimas indirectas (30% mximo)
        if has_orph:
            score += 0.25  # Mayor peso
            if num_orph >= 2:
                score += 0.05
        
        # Contextos reforzadores (10% mximo)
        if has_reinf:
            score += 0.05
            if num_reinf >= 2:
                score += 0.05
        
        # Bonus por combinacin perfecta
        if is_fem and has_child and has_orph:
            score += 0.10  # Caso ideal
        
        return min(score, 1.0)  # Mximo 1.0
    
    def _calculate_priority(self, is_fem: bool, has_orph: bool, confidence: float) -> str:
        """
        Calcula prioridad de la noticia.
        
        PRIORIDAD ALTA: Solo casos individuales de feminicidio con huérfanos/NNA
        - Debe mencionar feminicidio
        - Debe mencionar huérfanos/NNA afectados
        - Alta confianza (>= 0.7)
        - NO debe ser estadística o reporte general
        
        Returns:
            'ALTA', 'MEDIA', 'BAJA', 'IRRELEVANTE'
        """
        # ALTA: Feminicidio + hurfanos + confianza alta (caso individual)
        if is_fem and has_orph and confidence >= 0.7:
            return 'ALTA'
        
        # MEDIA: Feminicidio + hurfanos pero menos confianza
        elif is_fem and has_orph:
            return 'MEDIA'
        
        # MEDIA: Feminicidio sin mencin clara de hurfanos pero relevante
        elif is_fem and confidence >= 0.5:
            return 'MEDIA'
        
        # BAJA: Feminicidio pero poca certeza
        elif is_fem:
            return 'BAJA'
        
        # IRRELEVANTE: No trata sobre feminicidio
        else:
            return 'IRRELEVANTE'  # No es feminicidio
    
    def _empty_result(self) -> Dict[str, any]:
        """Retorna resultado vaco para exclusiones."""
        return {
            'is_feminicide': False,
            'has_children': False,
            'has_orphans': False,
            'is_target_news': False,
            'confidence': 0.0,
            'matched_patterns': {},
            'priority': 'IRRELEVANTE'
        }


# Funcin de utilidad para uso directo
def detect_feminicide_news(text: str) -> Dict[str, any]:
    """
    Funcin de conveniencia para deteccin de feminicidios.
    
    Args:
        text: Texto de la noticia
        
    Returns:
        Resultado de deteccin
    """
    detector = FeminicideDetector()
    return detector.detect(text)


# Ejemplo de uso
if __name__ == "__main__":
    # Casos de prueba
    test_cases = [
        {
            'title': 'Feminicidio en Ecatepec deja tres hijos hurfanos',
            'content': 'Una mujer fue asesinada por su expareja. Los tres menores quedaron al cuidado de familiares.',
            'expected': True
        },
        {
            'title': 'Menor gana premio de matemticas',
            'content': 'Adolescente de 15 aos obtiene primer lugar en olimpiada.',
            'expected': False
        },
        {
            'title': 'Hallan muerta a madre de dos nios',
            'content': 'Fiscala investiga feminicidio. Los menores presenciaron el crimen.',
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
        
        print(f"\n Caso {idx}:")
        print(f"   Ttulo: {case['title']}")
        print(f"   Esperado: {' OBJETIVO' if case['expected'] else ' NO OBJETIVO'}")
        print(f"\n   Resultado:")
        print(f"   - Es feminicidio: {result['is_feminicide']}")
        print(f"   - Tiene NNA: {result['has_children']}")
        print(f"   - Tiene hurfanos: {result['has_orphans']}")
        print(f"   - ES OBJETIVO: {result['is_target_news']} ({'' if result['is_target_news'] else ''})")
        print(f"   - Confianza: {result['confidence']:.1%}")
        print(f"   - Prioridad: {result['priority']}")
        
        if result['is_target_news'] == case['expected']:
            print(f"    CORRECTO")
        else:
            print(f"    ERROR - Se esperaba {case['expected']}")

