"""Simulate step_9 logic on the exact titles from the screenshot."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
class _cfg:
    RELEVANCE_THRESHOLD = 0.25
    TITLE_BOOST = 3.0
    RELEVANCE_WEIGHT_FEMINICIDIO = 0.55
    RELEVANCE_WEIGHT_NNA = 0.45
    RSS_FEEDS = []
sys.modules['config'] = _cfg
from src.collection.collector import score_relevance

# From screenshot — title + source only (minimal content)
NOTICIAS = [
    ("Mujer mata a su pareja con un cuchillo frente a sus hijos en Nuevo Leon - El Heraldo de Mexico", 0.39),
    ('"Sus hijos estan solos", familiar de Lina Alejandra revela que la empresaria asesinada era madre de 4 ninos - El Heraldo de Mexico', 0.39),
    ("Feminicidio y suicidio en Sonora; tragedia familiar deja a un menor en orfandad - El Universal", 0.61),
    ("Feminicidio de Cindy en Cuautitlan: lo que se sabe del doble asesinato que dejo a dos menores en orfandad - Serendipia", 0.61),
    ("Asesinan a Mujer Vendedora de Frituras en Irapuato, Guanajuato; Era Madre de Dos Hijos - N+", 0.39),
    ("Fiscalia de Michoacan ofrece recompensa de 100 mil pesos, por localizacion de Rene Garcia, quien es acusado del feminicidio de su ex pareja Ana Gabriela y tambien de sustraer a su hijo de 2 anos", 0.39),
]

print("=" * 95)
print("SIMULACION step_9 NUEVA LOGICA")
print("=" * 95)

for title, beto_score in NOTICIAS:
    rel = score_relevance(title, '')
    h_score = rel['score_compuesto']
    score_fem = rel['score_feminicidio']
    score_v_ind = rel.get('score_victima_indirecta', 0)
    score_nna = rel.get('score_nna', 0)
    score_caso = rel.get('score_caso', 0)
    s_score = beto_score
    
    # Alpha
    distance = abs(s_score - 0.5)
    if distance > 0.3: alpha = 0.7
    elif distance > 0.15: alpha = 0.5
    else: alpha = 0.3
    score_final = alpha * s_score + (1 - alpha) * h_score

    # NIVEL 0: Bypass de Oro
    es_bypass_oro = score_v_ind >= 0.80 and score_fem > 0.10
    es_collector_alta = (h_score >= 0.70 and score_fem > 0.15 and (score_v_ind > 0.25 or score_nna > 0.25))
    
    if es_bypass_oro or es_collector_alta:
        clasificacion = "Alta"
        score_final = max(h_score, 0.85)
        via = "Bypass Oro" if es_bypass_oro else "Collector Alta"
    else:
        # Simplified outlier simulation (topic_id=-1 for worst case)
        umbral_beto_rapida = 0.50  # outlier case
        es_via_rapida = score_v_ind > 0.40 and score_fem > 0.15 and s_score > umbral_beto_rapida
        
        if es_via_rapida:
            clasificacion = "Alta"
            score_final = max(score_final, 0.65)
            via = "Via Rapida"
        elif score_final >= 0.40:
            clasificacion = "Media"
            via = "Ninguna"
        elif score_final >= 0.20:
            clasificacion = "Baja"
            via = "Ninguna"
        else:
            clasificacion = "No relevante"
            via = "Ninguna"
    
    emoji = "OK" if clasificacion == "Alta" else "FAIL"
    print(f"\n{emoji} {title[:75]}...")
    print(f"   h_score={h_score:.2f}  fem={score_fem:.2f}  v_ind={score_v_ind:.2f}  nna={score_nna:.2f}  caso={score_caso:.2f}")
    print(f"   BETO={s_score:.2f}  score_final={score_final:.2f}  → {clasificacion} (via: {via})")
