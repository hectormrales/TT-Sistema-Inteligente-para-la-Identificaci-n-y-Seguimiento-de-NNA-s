import requests
from bs4 import BeautifulSoup
import re

def scrape_news_article(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Lanza un error si la petición falla
        soup = BeautifulSoup(response.text, 'html.parser')

        # Estrategia múltiple para encontrar el título
        title = extract_title(soup)
        if not title:
            print(f"No se pudo extraer el título de {url}")
            return None

        # Estrategia múltiple para encontrar el contenido
        content = extract_content(soup)
        if not content:
            print(f"No se pudo extraer el contenido de {url}")
            return None
        
        print(f"Noticia extraída: {title[:100]}...")
        return {'title': title, 'content': content, 'url': url}
    except requests.RequestException as e:
        print(f"Error al hacer la petición a {url}: {e}")
        return None
    except Exception as e:
        print(f"Error al procesar la página {url}: {e}")
        return None

def extract_title(soup):
    """Extrae el título usando múltiples estrategias"""
    # Lista de selectores comunes para títulos
    title_selectors = [
        'h1',  # Más genérico
        'h1.main-title',
        'h1.article-title',
        'h1.entry-title',
        'h1.post-title',
        '.headline',
        '.title',
        '[data-testid="headline"]',
        '.article-headline'
    ]
    
    for selector in title_selectors:
        title_element = soup.select_one(selector)
        if title_element:
            title = title_element.get_text(strip=True)
            if title:
                return title
    
    # Fallback: buscar en meta tags
    meta_title = soup.select_one('meta[property="og:title"]')
    if meta_title:
        return meta_title.get('content', '').strip()
    
    # Último fallback: título de la página
    page_title = soup.select_one('title')
    if page_title:
        return page_title.get_text(strip=True)
    
    return None

def extract_content(soup):
    """Extrae el contenido del artículo usando múltiples estrategias"""
    # Lista de selectores comunes para contenido
    content_selectors = [
        '.article-body',
        '.entry-content',
        '.post-content',
        '.content',
        '.article-content',
        '[data-testid="article-body"]',
        '.story-body',
        '.main-content'
    ]
    
    for selector in content_selectors:
        content_element = soup.select_one(selector)
        if content_element:
            content = content_element.get_text(strip=True, separator=' ')
            if len(content) > 100:  # Asegurar que tiene contenido sustancial
                return clean_content(content)
    
    # Fallback: buscar párrafos dentro del artículo
    paragraphs = soup.select('article p, .article p, .story p, main p')
    if paragraphs:
        content = ' '.join([p.get_text(strip=True) for p in paragraphs])
        if len(content) > 100:
            return clean_content(content)
    
    # Último fallback: todos los párrafos de la página
    all_paragraphs = soup.select('p')
    if all_paragraphs and len(all_paragraphs) > 2:
        content = ' '.join([p.get_text(strip=True) for p in all_paragraphs])
        return clean_content(content)
    
    return None

def clean_content(content):
    """Limpia el contenido del artículo"""
    # Remover espacios extra y caracteres de control
    content = re.sub(r'\s+', ' ', content)
    content = content.strip()
    
    # Remover texto común no deseado (puedes agregar más patrones)
    unwanted_patterns = [
        r'Suscr[ií]bete.*?newsletter',
        r'Compartir en.*?Twitter',
        r'Seguir leyendo:',
        r'LEE TAMBIÉN:',
        r'TAMBIÉN TE PUEDE INTERESAR:'
    ]
    
    for pattern in unwanted_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    return content.strip()