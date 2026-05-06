import os
import pandas as pd
from datetime import datetime
from src.collection.collector import score_relevance
from src.analysis.analyzer import SimplifiedNewsAnalyzer
from app import create_app

def reanalizar():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("=== MODO REANÁLISIS DE DATOS EXISTENTES ===")
        print("=" * 60)
        
        raw_path = "data/noticias_raw.csv"
        alt_path = "data/noticias_analyzed_simplified.csv"
        
        if os.path.exists(raw_path):
            target_path = raw_path
        elif os.path.exists(alt_path):
            target_path = alt_path
        else:
            print(f"Error: No se encontró ningún archivo CSV base en data/. Necesitas hacer una recolección completa al menos una vez.")
            return

        print(f"Cargando noticias base desde {target_path}...")
        df_raw = pd.read_csv(target_path)
        print(f"Cargadas {len(df_raw)} noticias.")
        
        # 1. Re-aplicar el scoring heurístico
        print("\n1. Re-evaluando scores heurísticos (aplicando reglas de collector.py)...")
        nuevos_scores = []
        for i, row in df_raw.iterrows():
            score = score_relevance(str(row.get('titulo', '')), str(row.get('contenido', '')))
            nuevos_scores.append(score)
            
        scores_df = pd.DataFrame(nuevos_scores)
        
        # Actualizar columnas en df_raw
        for col in scores_df.columns:
            df_raw[col] = scores_df[col]
            
        alta = (df_raw['clasificacion'] == 'Alta').sum()
        media = (df_raw['clasificacion'] == 'Media').sum()
        print(f"Resultados heurísticos: {alta} Alta, {media} Media.")
        
        # 2. Re-correr el pipeline de análisis
        print("\n2. Iniciando pipeline de análisis (BETO, Clustering, etc.)...")
        analyzer = SimplifiedNewsAnalyzer()
        analyzer.df_original = df_raw
        analyzer.current_batch_id = datetime.now().strftime("REANALYSIS_%Y%m%d_%H%M%S")
        
        try:
            analyzer.step_3_vectorize_text()
            analyzer.step_4_topic_modeling(num_topics=6)
            # step_5 (K-Means) desactivado: redundante con BERTopic
            analyzer.step_6_similarity_analysis()
            analyzer.step_7_tfidf_rescore()
            analyzer.step_8_enhanced_search_setup()
            
            # BERTopic ANTES de BETO (necesita volumen, da contexto de clúster)
            try:
                analyzer.step_10_bertopic_clustering()
            except Exception as e:
                print(f"BERTopic omitido o falló: {e}")
            
            analyzer.step_9_semantic_detection()
                
            analyzer.save_final_results()
            analyzer.step_11_persist_to_postgres()
            
            print("\n" + "=" * 60)
            print("¡Reanálisis completado con éxito!")
            print("Los datos se han guardado en la base de datos y en CSV.")
            print("Refresca el dashboard (F5) para ver los nuevos resultados.")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n[!] Error durante el análisis: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    reanalizar()
