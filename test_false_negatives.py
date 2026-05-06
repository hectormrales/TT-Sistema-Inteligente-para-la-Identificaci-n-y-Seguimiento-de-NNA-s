"""
Diagnóstico de Falsos Negativos — Traza por ejemplo.

Ejecutar con: python test_false_negatives.py

Para cada noticia que debería ser "Alta" pero está en "Media",
imprime:
  - score_feminicidio
  - score_victima_indirecta
  - score_caso
  - score_compuesto (del collector)
  - keywords de oro: ¿match?
  - qué regla del analyzer lo bajaría
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Minimal config stub
class _cfg:
    RELEVANCE_THRESHOLD = 0.25
    TITLE_BOOST = 3.0
    RELEVANCE_WEIGHT_FEMINICIDIO = 0.55
    RELEVANCE_WEIGHT_NNA = 0.45
    RSS_FEEDS = []

sys.modules.setdefault('config', _cfg)
import config

from src.collection.collector import (
    score_relevance, _check_keywords_de_oro, _normalize_text, KEYWORDS_DE_ORO,
    VICTIMA_INDIRECTA_NNA_KEYWORDS, _score_axis,
)

FALSOS_NEGATIVOS = [
    ('"Mi papá es malo": revelan testimonio de niño que presenció feminicidio de su mamá y abuela en Cuautitlán',
     'Infobae'),
    ('Capturan a Eric Antonio "N" por el feminicidio de Teresita y Cindy en Cuautitlán; hijo de 6 años narró el crimen',
     'TV Azteca'),
    ('Fiscalía de Michoacán ofrece recompensa de 100 mil pesos, por localización de René García, quien es acusado del feminicidio de su ex pareja Ana Gabriela y también de sustraer a su hijo de 2 años',
     'facebook.com'),
    ('Moisés "N" asesinó a su esposa y llamó a su hijo para contarle detalles del feminicidio que cometió en calles de la CDMX',
     'El Heraldo de México'),
    ('Cronología del doble feminicidio en Cuautitlán, Eric Antonio "N" las mató a pisadas dijo el hijo de Cindy',
     'Eje Central'),
    ('En Chiapas, mujer es asesinada a balazos por su pareja frente a sus tres hijos',
     'Milenio'),
    ('Mujer es asesinada cuando iba a dejar a sus hijos a la escuela en Tochimilco | Puebla',
     'e-consulta.com'),
    ('Feminicidio de Cindy en Cuautitlán: lo que se sabe del doble asesinato que dejó a dos menores en orfandad',
     'Serendipia - Periodismo de Datos'),
    ('¡Frente a su hijo de 5 años! Mariana es asesinada a balazos dentro de su carro en Naucalpan; iba con su pareja',
     'Telediario México'),
    ('Asesinan a Mujer Vendedora de Frituras en Irapuato, Guanajuato; Era Madre de Dos Hijos',
     'N+'),
    ('"Sus hijos están solos", familiar de Lina Alejandra revela que la empresaria asesinada era madre de 4 niños',
     'El Heraldo de México'),
    ('Familiares de Ángela Louise Birkenbach protestan frente al DIF Nacional en Benito Juárez: exigen justicia por su feminicidio y protección para sus hijos',
     'primeralinea.mx'),
]


print("=" * 90)
print("DIAGNÓSTICO DE FALSOS NEGATIVOS")
print("=" * 90)

for title, source in FALSOS_NEGATIVOS:
    title_norm = _normalize_text(title)
    combined_norm = _normalize_text(f"{title} {source}")
    
    # Score del collector
    rel = score_relevance(title, source)  # content = source (minimal)
    
    # Desglose manual de víctima indirecta
    v_ind_raw = _score_axis(title_norm, VICTIMA_INDIRECTA_NNA_KEYWORDS)
    
    # Golden keywords check
    has_gold = _check_keywords_de_oro(combined_norm)
    
    # Which golden keywords match?
    import re
    gold_matches = []
    for p in KEYWORDS_DE_ORO:
        if re.search(p, combined_norm, re.IGNORECASE):
            gold_matches.append(p[:60])
    
    print(f"\n{'─' * 90}")
    print(f"📰 {title[:80]}...")
    print(f"   score_fem={rel['score_feminicidio']:.4f}  "
          f"score_nna={rel['score_nna']:.4f}  "
          f"score_v_ind={rel.get('score_victima_indirecta', 0):.4f}  "
          f"score_caso={rel.get('score_caso', 0):.4f}")
    print(f"   score_compuesto={rel['score_compuesto']:.4f}  "
          f"clasificacion={rel['clasificacion']}")
    print(f"   v_ind_raw (solo título)={v_ind_raw:.4f}")
    print(f"   🔑 Keywords de Oro: {'✅ SÍ' if has_gold else '❌ NO'}")
    if gold_matches:
        for m in gold_matches:
            print(f"      → {m}")
    
    # Simular lógica del analyzer (NIVEL 1, 2, 3)
    sv = rel.get('score_victima_indirecta', 0)
    sf = rel['score_feminicidio']
    sc = rel.get('score_caso', 0)
    
    # NIVEL 1: Bypass de Oro
    bypass = sv >= 0.80
    # Vía Rápida
    via_rapida = sv > 0.60 and sf > 0.15
    # Alta estricta (asumiendo BETO=0.50)
    beto_sim = 0.50  # Score BETO simulado conservador
    alta_estricta = sf > 0.15 and sv > 0.25 and sc > 0.15 and beto_sim > 0.50
    
    if bypass:
        analyzer_result = "ALTA (Bypass de Oro)"
    elif via_rapida:
        analyzer_result = "ALTA (Vía Rápida)"
    elif alta_estricta:
        analyzer_result = "ALTA (Estricta)"
    else:
        analyzer_result = "MEDIA (ninguna ruta a Alta)"
        reasons = []
        if sv <= 0.60:
            reasons.append(f"v_ind={sv:.2f} ≤ 0.60 (Vía Rápida necesita >0.60)")
        if sv <= 0.25:
            reasons.append(f"v_ind={sv:.2f} ≤ 0.25 (Alta estricta necesita >0.25)")
        if sf <= 0.15:
            reasons.append(f"fem={sf:.2f} ≤ 0.15")
        if sc <= 0.15:
            reasons.append(f"caso={sc:.2f} ≤ 0.15")
        for r in reasons:
            print(f"      ⚠️ {r}")
    
    print(f"   🎯 Analyzer simularía: {analyzer_result}")

print(f"\n{'=' * 90}")
