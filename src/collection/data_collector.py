# src/collection/data_collector.py
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from email.utils import parsedate_to_datetime
from unicodedata import normalize
import config

def collect_news_from_rss(rss_url):
    """Recolecta noticias desde un feed RSS."""
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
                
                articles.append({ 
                    'titulo': title.text.strip(),
                    'contenido': desc_text,
                    'enlace': link.text.strip() if link else '',
                    'fuente': rss_url,
                    'fecha': dt.isoformat(),
                    'cluster': 0, #Se asignará luego del análisis
                    'menores_identificados': 'No determinado' #Se asignará luego del análisis
                })

        return articles
    
    except Exception as e:
        print(f"Error recolectando noticias de {rss_url}: {e}")
        return []

def collect_all_news():
    """Recolecta noticias de todas las fuentes configuradas."""
    all_articles = []
    
    for rss_feed in config.RSS_FEEDS:
        print(f"Recolectando noticias de: {rss_feed}")
        articles = collect_news_from_rss(rss_feed)
        all_articles.extend(articles)
    
    return pd.DataFrame(all_articles)

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