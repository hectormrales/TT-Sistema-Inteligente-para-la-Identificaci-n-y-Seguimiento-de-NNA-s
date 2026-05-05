import sys
from src.collection.scraper import StealthSession
from bs4 import BeautifulSoup

def test_google():
    session = StealthSession()
    url = "https://www.google.com/search?q=feminicidio+mexico+deja+ni%C3%B1o+facebook&hl=es"
    response = session.get(url)
    print("Status:", response.status_code)
    
    soup = BeautifulSoup(response.text, 'html.parser')
    results = soup.find_all('div', class_='g')
    print(f"Found {len(results)} results")
    for r in results[:3]:
        title = r.find('h3')
        a = r.find('a')
        if title and a:
            print("-", title.text)
            print("  ", a['href'])

if __name__ == "__main__":
    test_google()
