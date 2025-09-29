# install_dependencies.py
"""
Script para instalar las dependencias necesarias para el análisis completo.
Instala las librerías de ML y PLN requeridas.
"""

import subprocess
import sys
import os

def install_package(package):
    """Instala un paquete usando pip."""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error instalando {package}: {e}")
        return False

def main():
    """Instala todas las dependencias necesarias."""
    print("🔧 INSTALADOR DE DEPENDENCIAS")
    print("Sistema Inteligente para Identificación y Seguimiento de NNA")
    print("=" * 60)
    
    # Lista de paquetes necesarios
    packages = [
        "pandas==2.2.2",
        "numpy>=1.21.0",
        "scikit-learn>=1.3,<1.6",
        "gensim==4.3.2",
        "nltk==3.8.1",
        "requests==2.31.0",
        "beautifulsoup4==4.12.2",
        "lxml>=4.9.3,<6",
        "Flask==2.3.3",
        "Flask-SQLAlchemy==3.1.1",
        "spacy>=3.8.0"
    ]
    
    print("📦 Paquetes a instalar:")
    for package in packages:
        print(f"   • {package}")
    print()
    
    # Actualizar pip primero
    print("🔄 Actualizando pip...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        print("✅ pip actualizado")
    except subprocess.CalledProcessError:
        print("⚠️  No se pudo actualizar pip, continuando...")
    
    print()
    
    # Instalar paquetes
    failed_packages = []
    successful_packages = []
    
    for package in packages:
        package_name = package.split("==")[0].split(">=")[0].split("<")[0]
        print(f"📥 Instalando {package_name}...")
        
        if install_package(package):
            print(f"✅ {package_name} instalado correctamente")
            successful_packages.append(package_name)
        else:
            print(f"❌ Error instalando {package_name}")
            failed_packages.append(package_name)
        print()
    
    # Descargar modelo de spaCy en español (si spacy se instaló correctamente)
    if "spacy" in successful_packages:
        print("📥 Descargando modelo de spaCy en español...")
        try:
            subprocess.check_call([sys.executable, "-m", "spacy", "download", "es_core_news_sm"])
            print("✅ Modelo de spaCy en español descargado")
        except subprocess.CalledProcessError:
            print("⚠️  No se pudo descargar el modelo de spaCy, se puede hacer manualmente después")
    
    # Descargar datos de NLTK
    if "nltk" in successful_packages:
        print("📥 Descargando datos de NLTK...")
        try:
            import nltk
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
            nltk.download('wordnet', quiet=True)
            print("✅ Datos de NLTK descargados")
        except Exception as e:
            print(f"⚠️  Error descargando datos de NLTK: {e}")
    
    # Resumen final
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE INSTALACIÓN")
    print("=" * 60)
    
    print(f"✅ Paquetes instalados exitosamente: {len(successful_packages)}")
    for pkg in successful_packages:
        print(f"   • {pkg}")
    
    if failed_packages:
        print(f"\n❌ Paquetes que fallaron: {len(failed_packages)}")
        for pkg in failed_packages:
            print(f"   • {pkg}")
        
        print("\n💡 Para instalar manualmente los paquetes fallidos:")
        for pkg in failed_packages:
            print(f"   pip install {pkg}")
    else:
        print("\n🎉 ¡Todas las dependencias se instalaron correctamente!")
    
    print("\n🚀 ¿Qué hacer ahora?")
    print("   1. Ejecutar el demo: python demo_analysis.py")
    print("   2. Revisar la configuración: config.py")
    print("   3. Leer la documentación: README_ANALISIS.md")
    
    # Verificar instalación
    print("\n🔍 Verificando instalación...")
    verification_passed = True
    
    test_imports = [
        ("pandas", "import pandas as pd"),
        ("numpy", "import numpy as np"),
        ("sklearn", "from sklearn.feature_extraction.text import TfidfVectorizer"),
        ("gensim", "from gensim import corpora"),
        ("requests", "import requests"),
        ("bs4", "from bs4 import BeautifulSoup")
    ]
    
    for pkg_name, import_stmt in test_imports:
        try:
            exec(import_stmt)
            print(f"✅ {pkg_name}")
        except ImportError:
            print(f"❌ {pkg_name}")
            verification_passed = False
    
    if verification_passed:
        print("\n🎉 ¡Verificación exitosa! El sistema está listo para usar.")
    else:
        print("\n⚠️  Algunos paquetes no se importaron correctamente.")
        print("   Revise los errores y vuelva a intentar la instalación.")

if __name__ == "__main__":
    main()