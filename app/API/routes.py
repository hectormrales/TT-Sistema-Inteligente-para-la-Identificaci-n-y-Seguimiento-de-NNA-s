from flask import Blueprint, jsonify
from Scraper.scraper import scrape_news_article
from NLP.analyzer import find_nna_mentions
from Models.case import db, FemicideCase
import traceback

api_bp = Blueprint('api', __name__)

@api_bp.route('/process-url/<path:url>')
def process_url(url):
    try:
        print(f"Procesando URL: {url}")
        
        # 1. Scrapea la URL
        article_data = scrape_news_article(url)
        if not article_data:
            return jsonify({
                "error": "No se pudo extraer la noticia",
                "details": "El scraper no pudo obtener título o contenido de la página"
            }), 400

        print(f"Título extraído: {article_data['title'][:50]}...")
        print(f"Contenido extraído: {len(article_data['content'])} caracteres")

        # 2. Analiza con PLN
        mentions_found = find_nna_mentions(article_data['content'])
        print(f"Menciones de NNA encontradas: {mentions_found}")

        # 3. Verifica si ya existe en la base de datos
        existing_case = FemicideCase.query.filter_by(url=url).first()
        if existing_case:
            return jsonify({
                "message": "Esta noticia ya fue procesada anteriormente.",
                "case_id": existing_case.id,
                "nna_mention_found": existing_case.has_nna_mention
            }), 200

        # 4. Guarda en la base de datos
        new_case = FemicideCase(
            title=article_data['title'],
            url=article_data['url'],
            content=article_data['content'],
            has_nna_mention=mentions_found
        )
        db.session.add(new_case)
        db.session.commit()

        return jsonify({
            "message": "Noticia procesada y guardada exitosamente.",
            "case_id": new_case.id,
            "nna_mention_found": mentions_found,
            "title": article_data['title'],
            "content_length": len(article_data['content'])
        }), 201

    except Exception as e:
        print(f"Error procesando URL {url}: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            "error": "Error interno del servidor",
            "details": str(e)
        }), 500

@api_bp.route('/cases')
def get_cases():
    """Obtiene todos los casos almacenados"""
    try:
        cases = FemicideCase.query.all()
        return jsonify({
            "cases": [{
                "id": case.id,
                "title": case.title,
                "url": case.url,
                "has_nna_mention": case.has_nna_mention,
                "is_validated": case.is_validated,
                "scraped_at": case.scraped_at.isoformat()
            } for case in cases],
            "total": len(cases)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/health')
def health_check():
    """Verificación de salud de la API"""
    return jsonify({"status": "ok", "message": "API funcionando correctamente"}), 200