# ejemplo_uso.py
"""
Ejemplo paso a paso de cómo usar cada componente del análisis.
Perfecto para entender el funcionamiento de cada etapa.
"""

import os
import sys
import pandas as pd

# Agregar el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def ejemplo_basico():
    """Ejemplo básico usando componentes individuales."""
    print("🔬 EJEMPLO DE USO - COMPONENTES INDIVIDUALES")
    print("=" * 60)
    
    # Datos de ejemplo para demostración
    noticias_ejemplo = [
        {
            'titulo': 'Feminicidio en Ciudad de México deja dos hijos huérfanos',
            'contenido': 'Una mujer de 35 años fue asesinada por su expareja en la Ciudad de México. Los hijos de la víctima, de 8 y 12 años, quedan en orfandad tras este feminicidio que conmociona a la comunidad.',
            'fecha': '2024-01-15',
            'fuente': 'ejemplo_rss_1'
        },
        {
            'titulo': 'Manifestación por justicia tras muerte violenta de mujer',
            'contenido': 'Cientos de personas marcharon exigiendo justicia por el asesinato de una joven madre. La víctima tenía dos niños pequeños que ahora están bajo cuidado de familiares.',
            'fecha': '2024-01-16', 
            'fuente': 'ejemplo_rss_2'
        },
        {
            'titulo': 'Programa de apoyo a menores en situación de vulnerabilidad',
            'contenido': 'El gobierno lanza un nuevo programa para apoyar a niños y adolescentes en situación de riesgo. El programa incluye asistencia psicológica y educativa para NNA afectados por violencia.',
            'fecha': '2024-01-17',
            'fuente': 'ejemplo_rss_3'
        },
        {
            'titulo': 'Detención por violencia doméstica salva a tres menores',
            'contenido': 'Las autoridades detuvieron a un hombre por violencia familiar. Los tres hijos de la pareja, de 5, 7 y 10 años, fueron puestos bajo protección de servicios sociales.',
            'fecha': '2024-01-18',
            'fuente': 'ejemplo_rss_4'
        }
    ]
    
    df_ejemplo = pd.DataFrame(noticias_ejemplo)
    
    print(f"📰 Trabajando con {len(df_ejemplo)} noticias de ejemplo")
    print()
    
    # 1. Demostrar detección de NNA
    print("🎯 PASO 1: DETECCIÓN DE MENCIONES A NNA")
    print("-" * 40)
    
    try:
        from src.collection.data_collector import detect_children_mentions
        
        df_ejemplo['menores_identificados'] = df_ejemplo['contenido'].apply(detect_children_mentions)
        
        nna_detectadas = df_ejemplo[df_ejemplo['menores_identificados'] == 'Si']
        print(f"✅ {len(nna_detectadas)} noticias con menciones a NNA detectadas")
        
        for idx, row in nna_detectadas.iterrows():
            print(f"   • {row['titulo'][:50]}...")
        print()
        
    except ImportError as e:
        print(f"❌ Error importando detector de NNA: {e}")
        print()
    
    # 2. Demostrar limpieza de texto
    print("🧹 PASO 2: LIMPIEZA Y NORMALIZACIÓN DE TEXTO")
    print("-" * 40)
    
    try:
        from src.processing.text_processor import clean_and_lemmatize_series
        
        df_ejemplo['titulo_limpio'] = clean_and_lemmatize_series(df_ejemplo['titulo'])
        df_ejemplo['contenido_limpio'] = clean_and_lemmatize_series(df_ejemplo['contenido'])
        
        print("✅ Texto limpio y normalizado")
        print("Ejemplo de limpieza:")
        print(f"   Original: {df_ejemplo['titulo'].iloc[0]}")
        print(f"   Limpio:   {df_ejemplo['titulo_limpio'].iloc[0]}")
        print()
        
    except ImportError as e:
        print(f"❌ Error importando procesador de texto: {e}")
        print()
    
    # 3. Demostrar diccionario de sinónimos
    print("📚 PASO 3: DICCIONARIO DE SINÓNIMOS")
    print("-" * 40)
    
    try:
        from src.analysis.synonym_dictionary import SynonymDictionary
        
        synonym_dict = SynonymDictionary()
        
        # Probar algunos términos
        terminos_prueba = ['feminicidio', 'niños', 'violencia', 'huérfanos']
        
        for termino in terminos_prueba:
            sinonimos = synonym_dict.get_synonyms(termino)
            print(f"'{termino}' → {', '.join(list(sinonimos)[:5])}")
        
        # Expandir una consulta
        consulta = "feminicidio niños"
        consulta_expandida = synonym_dict.expand_search_query(consulta)
        print(f"\nConsulta expandida:")
        print(f"   Original: '{consulta}'")
        print(f"   Expandida: '{consulta_expandida}'")
        print()
        
    except ImportError as e:
        print(f"❌ Error importando diccionario de sinónimos: {e}")
        print()
    
    # 4. Demostrar clustering básico (si está disponible)
    print("🔗 PASO 4: CLUSTERING BÁSICO")
    print("-" * 40)
    
    try:
        from src.analysis.news_analyzer import cluster_dataframe
        
        if len(df_ejemplo) >= 3:  # Mínimo para clustering
            df_clustered, cluster_info = cluster_dataframe(
                df_ejemplo, 
                n_clusters=2,  # Pocos clusters para el ejemplo
                max_features=100  # Pocas características para el ejemplo
            )
            
            print("✅ Clustering completado")
            print(f"📈 Silhouette score: {cluster_info['silhouette']:.3f}")
            
            # Mostrar distribución
            cluster_counts = df_clustered['cluster'].value_counts()
            print("Distribución de clusters:")
            for cluster_id, count in cluster_counts.items():
                print(f"   Cluster {cluster_id}: {count} noticias")
            print()
            
        else:
            print("⚠️  Necesita más noticias para clustering")
            print()
            
    except ImportError as e:
        print(f"❌ Error importando clustering: {e}")
        print()
    except Exception as e:
        print(f"⚠️  No se pudo ejecutar clustering: {e}")
        print()
    
    # 5. Guardar resultados del ejemplo
    print("💾 GUARDANDO RESULTADOS DEL EJEMPLO")
    print("-" * 40)
    
    # Crear directorio data si no existe
    os.makedirs('data', exist_ok=True)
    
    # Guardar datos de ejemplo
    ejemplo_path = 'data/ejemplo_analisis.csv'
    df_ejemplo.to_csv(ejemplo_path, index=False, encoding='utf-8')
    
    print(f"✅ Ejemplo guardado en: {ejemplo_path}")
    print(f"📊 Columnas disponibles: {list(df_ejemplo.columns)}")
    print()
    
    return df_ejemplo

def ejemplo_busqueda():
    """Ejemplo de búsqueda con sinónimos."""
    print("🔍 EJEMPLO DE BÚSQUEDA MEJORADA")
    print("=" * 60)
    
    try:
        # Cargar datos de ejemplo si existen
        ejemplo_path = 'data/ejemplo_analisis.csv'
        if os.path.exists(ejemplo_path):
            df = pd.read_csv(ejemplo_path)
        else:
            print("⚠️  Ejecute ejemplo_basico() primero")
            return
        
        from src.analysis.synonym_dictionary import enhanced_search
        
        # Pruebas de búsqueda
        consultas = [
            "feminicidio",
            "niños",
            "violencia",
            "huérfanos", 
            "menores"
        ]
        
        for consulta in consultas:
            print(f"\n🔍 Búsqueda: '{consulta}'")
            resultados = enhanced_search(df, consulta, ['titulo', 'contenido'])
            
            if len(resultados) > 0:
                print(f"   ✅ {len(resultados)} resultados encontrados")
                for idx, row in resultados.iterrows():
                    titulo = row['titulo'][:60] + "..." if len(row['titulo']) > 60 else row['titulo']
                    print(f"      • {titulo}")
            else:
                print("   ❌ Sin resultados")
        
        print("\n✅ Demostración de búsqueda completada")
        
    except ImportError as e:
        print(f"❌ Error en búsqueda: {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

def ejemplo_completo():
    """Ejecuta todos los ejemplos."""
    print("🚀 DEMO COMPLETO - ANÁLISIS DE NOTICIAS NNA")
    print("Sistema Inteligente para Identificación y Seguimiento")
    print("=" * 60)
    
    try:
        # Verificar que podemos importar pandas
        import pandas as pd
        print("✅ Pandas disponible")
        
        # Ejecutar ejemplos paso a paso
        df_resultado = ejemplo_basico()
        
        print("\n" + "=" * 60)
        
        ejemplo_busqueda()
        
        print("\n" + "=" * 60)
        print("🎉 DEMO COMPLETADO EXITOSAMENTE")
        print("💡 Para análisis completo con datos reales:")
        print("   1. Configure RSS feeds en config.py")
        print("   2. Instale dependencias: python install_dependencies.py") 
        print("   3. Ejecute análisis: python demo_analysis.py")
        print("=" * 60)
        
        return df_resultado
        
    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        print("\n💡 Instale las dependencias primero:")
        print("   python install_dependencies.py")
        
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        print(f"📍 Tipo: {type(e).__name__}")

if __name__ == "__main__":
    ejemplo_completo()