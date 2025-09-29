#!/usr/bin/env python3
"""
Demo simplificado para contenedor Docker
Sistema Inteligente para Identificación y Seguimiento de NNA
"""

import os
import sys
import time
import schedule
from datetime import datetime

# Agregar el directorio src al path
sys.path.append('/app/src')

from analysis.simplified_analyzer import SimplifiedNewsAnalyzer
from collection.data_collector import collect_all_news
import pandas as pd

class DockerDemo:
    def __init__(self):
        self.analyzer = SimplifiedNewsAnalyzer()
        self.data_file = "/app/data/noticias.csv"
        
    def log(self, message):
        """Log con timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def collect_news(self):
        """Recolecta noticias nuevas"""
        try:
            self.log("🔍 Iniciando recolección de noticias...")
            
            # Recolectar noticias
            df_noticias = collect_all_news()
            noticias = df_noticias.to_dict('records') if not df_noticias.empty else []
            
            if noticias:
                self.log(f"✅ Recolectadas {len(noticias)} noticias")
                
                # Guardar en CSV
                df = pd.DataFrame(noticias)
                
                # Si el archivo existe, agregar las nuevas
                if os.path.exists(self.data_file):
                    df_existing = pd.read_csv(self.data_file)
                    df = pd.concat([df_existing, df], ignore_index=True)
                    df = df.drop_duplicates(subset=['titulo', 'contenido'], keep='last')
                
                df.to_csv(self.data_file, index=False)
                self.log(f"💾 Datos guardados en {self.data_file}")
                
            else:
                self.log("⚠️  No se recolectaron noticias nuevas")
                
        except Exception as e:
            self.log(f"❌ Error en recolección: {str(e)}")
    
    def analyze_news(self):
        """Ejecuta análisis completo"""
        try:
            if not os.path.exists(self.data_file):
                self.log("⚠️  No hay datos para analizar")
                return
                
            self.log("🔬 Iniciando análisis completo...")
            
            # Leer datos
            df = pd.read_csv(self.data_file)
            self.log(f"📊 Analizando {len(df)} noticias")
            
            # Ejecutar análisis
            df_analyzed = self.analyzer.analyze_news(df)
            
            # Guardar resultados
            df_analyzed.to_csv(self.data_file, index=False)
            
            # Estadísticas
            nna_count = len(df_analyzed[df_analyzed['menores_identificados'] == 'Si'])
            nna_percentage = (nna_count / len(df_analyzed) * 100) if len(df_analyzed) > 0 else 0
            
            self.log(f"✅ Análisis completado:")
            self.log(f"   📰 Total noticias: {len(df_analyzed)}")
            self.log(f"   👶 Casos NNA: {nna_count} ({nna_percentage:.1f}%)")
            self.log(f"   🏷️  Clusters: {df_analyzed['cluster'].nunique()}")
            self.log(f"   🎯 Tópicos: {df_analyzed['topic_id'].nunique()}")
            
        except Exception as e:
            self.log(f"❌ Error en análisis: {str(e)}")
    
    def run_full_cycle(self):
        """Ejecuta un ciclo completo: recolección + análisis"""
        self.log("🚀 Iniciando ciclo completo")
        self.collect_news()
        time.sleep(2)  # Pausa entre operaciones
        self.analyze_news()
        self.log("✅ Ciclo completo terminado")
    
    def start_scheduler(self):
        """Inicia el planificador automático"""
        self.log("⏰ Iniciando planificador automático")
        
        # Programar tareas
        schedule.every(6).hours.do(self.collect_news)  # Cada 6 horas recolectar
        schedule.every(12).hours.do(self.analyze_news)  # Cada 12 horas analizar
        
        # Ejecutar una vez al inicio
        self.run_full_cycle()
        
        # Loop infinito
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Verificar cada minuto
            except KeyboardInterrupt:
                self.log("🛑 Deteniendo planificador...")
                break
            except Exception as e:
                self.log(f"❌ Error en planificador: {str(e)}")
                time.sleep(60)

def main():
    """Función principal"""
    demo = DockerDemo()
    
    # Verificar argumentos
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "collect":
            demo.collect_news()
        elif command == "analyze":
            demo.analyze_news()
        elif command == "full":
            demo.run_full_cycle()
        elif command == "schedule":
            demo.start_scheduler()
        else:
            demo.log(f"❌ Comando desconocido: {command}")
            demo.log("💡 Comandos disponibles: collect, analyze, full, schedule")
    else:
        # Por defecto, iniciar planificador
        demo.start_scheduler()

if __name__ == "__main__":
    main()