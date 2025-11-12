# -*- coding: utf-8 -*-
"""
Test simplificado: buscar solo en Google News (más rápido)
"""

import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

import requests
from bs4 import BeautifulSoup
from src.collection.feminicide_detector import FeminicideDetector
from datetime import datetime

def test_google_news_feminicide():
    """Buscar en Google News noticias de feminicidios con hijos/huerfanos."""
    
    print("="*80)
    print("BUSQUEDA EN GOOGLE NEWS: Feminicidios + Huerfanos")
    print("="*80)
    
    detector = FeminicideDetector()
    
    # Buscar en Google News RSS
    query = "feminicidio hijos huerfanos mexico"
    url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=es-MX&gl=MX&ceid=MX:es-419"
    
    print(f"\nBuscando: {query}")
    print(f"URL: {url}\n")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            return
        
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')
        
        print(f"Articulos encontrados: {len(items)}")
        print("="*80)
        
        feminicidios = 0
        objetivo = 0
        
        for item in items[:20]:  # Primeros 20
            title = item.find('title')
            if not title:
                continue
            
            title_text = title.get_text(strip=True)
            
            # Aplicar detector
            detection = detector.detect(title_text)
            
            if detection['is_feminicide']:
                feminicidios += 1
                
                status = "OBJETIVO" if detection['is_target_news'] else "FEMINICIDIO"
                print(f"\n[{status}] Confianza: {detection['confidence']:.0%}")
                print(f"Titulo: {title_text}")
                print(f"  Feminicidio: {detection['is_feminicide']}")
                print(f"  NNA: {detection['has_children']}")
                print(f"  Huerfanos: {detection['has_orphans']}")
                print(f"  Prioridad: {detection['priority']}")
                
                if detection['is_target_news']:
                    objetivo += 1
        
        print("\n" + "="*80)
        print("RESUMEN:")
        print(f"  Feminicidios detectados: {feminicidios}")
        print(f"  Noticias OBJETIVO: {objetivo}")
        print("="*80)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_google_news_feminicide()
