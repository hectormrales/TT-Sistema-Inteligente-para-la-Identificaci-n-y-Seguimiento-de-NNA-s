"""Verify that the 2 remaining titles match AFTER the latest code changes."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

class _cfg:
    RELEVANCE_THRESHOLD = 0.25
    TITLE_BOOST = 3.0
    RELEVANCE_WEIGHT_FEMINICIDIO = 0.55
    RELEVANCE_WEIGHT_NNA = 0.45
    RSS_FEEDS = []
sys.modules['config'] = _cfg

# Force fresh import after code changes
import importlib
if 'src.collection.collector' in sys.modules:
    importlib.reload(sys.modules['src.collection.collector'])
from src.collection.collector import (
    score_relevance, _check_keywords_de_oro, _normalize_text, KEYWORDS_DE_ORO, _COMPILED_KEYWORDS_DE_ORO,
)
import re

remaining = [
    '"Mi papa es malo": revelan testimonio de nino que presencio feminicidio de su mama y abuela en Cuautitlan - Infobae',
    'Capturan a Eric Antonio "N" por el feminicidio de Teresita y Cindy en Cuautitlan; hijo de 6 anios narro el crimen - TV Azteca',
]

print(f"Total KEYWORDS_DE_ORO: {len(KEYWORDS_DE_ORO)}")
print(f"Total _COMPILED: {len(_COMPILED_KEYWORDS_DE_ORO)}")

for title in remaining:
    combined = _normalize_text(title)
    print(f"\nTITLE: {title[:80]}")
    print(f"NORM:  {combined[:80]}")
    print(f"_check_keywords_de_oro: {_check_keywords_de_oro(combined)}")
    
    # Check each pattern
    for i, p in enumerate(KEYWORDS_DE_ORO):
        if re.search(p, combined, re.IGNORECASE):
            print(f"  MATCH pattern[{i}]: {p[:70]}")
    
    # Full scoring
    rel = score_relevance(title, '')
    print(f"  score_v_ind={rel.get('score_victima_indirecta', 0):.4f}")
    print(f"  score_compuesto={rel['score_compuesto']:.4f}")
    print(f"  clasificacion={rel['clasificacion']}")
