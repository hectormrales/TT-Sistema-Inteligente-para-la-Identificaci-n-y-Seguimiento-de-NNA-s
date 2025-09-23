# src/collection/data_collector.py
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import config

def collect_news_from_rss(rss_url):
    """Recolecta noticias desde un feed RSS."""
    try:
        response = requests.get(rss_url, timeout=10)
        soup = BeautifulSoup(response.content, 'xml')
        
        articles = []
        for item in soup.find_all('item'):
            title = item.find('title')
            description = item.find('description')
            link = item.find('link')
            pub_date = item.find('pubDate')
            
            if title and description:
                articles.append({
                    'titulo': title.text.strip(),
                    'contenido': description.text.strip(),
                    'fuente': rss_url,
                    'fecha': pub_date.text.strip() if pub_date else str(datetime.now()),
                    'cluster': 0,  # Se asignará después del análisis
                    'menores_identificados': 'No determinado'  # Se analizará después
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
    keywords = [
        'hijo', 'hija', 'hijos', 'hijas', 'menor', 'menores', 
        'niño', 'niña', 'niños', 'niñas', 'adolescente', 'adolescentes',
        'huérfano', 'huérfanos', 'huérfana', 'huérfanas',
        'menor de edad', 'menores de edad'
    ]
    
    text_lower = text.lower()
    for keyword in keywords:
        if keyword in text_lower:
            return 'Sí'
    
    return 'No'