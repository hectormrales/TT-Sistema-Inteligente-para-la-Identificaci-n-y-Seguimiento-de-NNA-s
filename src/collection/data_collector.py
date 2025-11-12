# src/collection/data_collector.py
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from email.utils import parsedate_to_datetime
from unicodedata import normalize
import config
from .feminicide_detector import FeminicideDetector

def collect_news_from_rss(rss_url):
    """Recolecta noticias desde un feed RSS y aplica detección de feminicidios."""
    # Inicializar detector de feminicidios
    detector = FeminicideDetector()
    
    try:
        #Usar headers para evitar bloqueos
        headers = getattr(config, 'HTTP_HEADERS', {})
        response = requests.get(rss_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'xml')
        
        articles = []
        for item in soup.find_all('item'):
            title = item.find('title')
            description = item.find('description')
            link = item.find('link')
            pub_date = item.find('pubDate')
            #Wordpress sule incluir <content:encoded> con cuerpo completo
            content_encoded = item.find('content:encoded')
            
            if title and description:
                #Quitar HTML de la descripción
                desc_html = content_encoded.text if content_encoded else description.text
                desc_text = BeautifulSoup(desc_html, 'html.parser').get_text(" ", strip=True)

                #Normalizar fecha a ISO 8601
                if pub_date and pub_date.text.strip():
                    try:
                        dt = parsedate_to_datetime(pub_date.text.strip())
                    except Exception:
                        dt = datetime.utcnow()
                else:
                    dt = datetime.utcnow()
                
                # === NUEVA DETECCIÓN ESPECIALIZADA ===
                # Combinar título y contenido para análisis completo
                full_text = f"{title.text.strip()} {desc_text}"
                detection = detector.detect(full_text)
                
                # Mantener compatibilidad con código anterior
                menores_identificados = 'Si' if detection['has_children'] else 'No'
                
                articles.append({ 
                    'titulo': title.text.strip(),
                    'contenido': desc_text,
                    'enlace': link.text.strip() if link else '',
                    'fuente': rss_url,
                    'fecha': dt.isoformat(),
                    'cluster': 0, #Se asignará luego del análisis
                    
                    # === CAMPOS NUEVOS DE DETECCIÓN ESPECIALIZADA ===
                    'es_feminicidio': detection['is_feminicide'],
                    'tiene_nna': detection['has_children'],
                    'tiene_huerfanos': detection['has_orphans'],
                    'es_objetivo': detection['is_target_news'],  # ← CAMPO PRINCIPAL
                    'confianza': detection['confidence'],
                    'prioridad': detection['priority'],
                    
                    # Mantener compatibilidad con código anterior
                    'menores_identificados': menores_identificados
                })

        return articles
    
    except Exception as e:
        print(f"Error recolectando noticias de {rss_url}: {e}")
        return []

def collect_all_news():
    """Recolecta noticias de todas las fuentes configuradas."""
    all_articles = []
    
    print("="*80)
    print("INICIANDO RECOLECCIÓN DE NOTICIAS CON DETECCIÓN ESPECIALIZADA")
    print("="*80)
    
    for rss_feed in config.RSS_FEEDS:
        print(f"\n📡 Recolectando de: {rss_feed}")
        articles = collect_news_from_rss(rss_feed)
        print(f"   ✅ {len(articles)} noticias recolectadas")
        all_articles.extend(articles)
    
    # Convertir a DataFrame
    df = pd.DataFrame(all_articles)
    
    if len(df) > 0:
        # Estadísticas de recolección
        total = len(df)
        feminicides = df['es_feminicidio'].sum() if 'es_feminicidio' in df.columns else 0
        target_news = df['es_objetivo'].sum() if 'es_objetivo' in df.columns else 0
        high_priority = len(df[df['prioridad'] == 'ALTA']) if 'prioridad' in df.columns else 0
        
        print("\n" + "="*80)
        print("RESUMEN DE RECOLECCIÓN")
        print("="*80)
        print(f"\n📊 Total de noticias recolectadas: {total}")
        print(f"📰 Noticias de feminicidio: {feminicides} ({feminicides/total*100:.1f}%)")
        print(f"🎯 Noticias OBJETIVO (feminicidio+NNA): {target_news} ({target_news/total*100:.1f}%)")
        print(f"⭐ Prioridad ALTA: {high_priority} ({high_priority/total*100:.1f}%)")
        
        # Advertencia si no hay suficientes noticias objetivo
        if target_news / total < 0.30:  # Menos del 30%
            print(f"\n⚠️  ADVERTENCIA: Solo {target_news/total*100:.1f}% son noticias objetivo")
            print("   Se esperaba >50% de noticias sobre feminicidios con NNA")
            print("   Considera agregar más fuentes especializadas en género/feminicidios")
        else:
            print(f"\n✅ Porcentaje de noticias objetivo aceptable: {target_news/total*100:.1f}%")
    
    return df

def detect_children_mentions(text):
    """Detecta menciones de menores de edad en el texto."""
    if not isinstance(text, str):
        return 'No'
    #Normalizar minusculas y eliminar acentos
    t = normalize('NFKD', text.lower()).encode('ASCII', 'ignore').decode('ascii')
    #Palabras clave y patrones comunes
    keywords = [
        r'\bhij[oa]s?\b', r'\bmenor(?:es)?(?:\s+de\s+edad)?\b', r'\bniñ?[oa]s?\b',
        r'\badolescentes?\b', r'\bhu(erf|erf)an[oa]s?\b', r'\binfant(e|il|es)\b',
        r'\bbebes?\b', r'\breci[e|e]n\s+nacid[oa]s?\b', r'\bNNA\b'
    ]
    #Edades explicitas
    age_patterns = [
        r'\b\d{1,2}\s*(anos|mes(?:es)?)\b', r'\bde\s+\d{1,2}\s*(anos|mes(?:es)?)\b'
    ]

    import re
    for pat in keywords + age_patterns:
        if re.search(pat, t, re.IGNORECASE):
            return 'Si'
    return 'No'