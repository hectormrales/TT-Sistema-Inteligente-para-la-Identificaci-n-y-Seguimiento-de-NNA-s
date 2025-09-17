#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from NLP.analyzer import find_nna_mentions, test_analyzer

# Textos de prueba
test_texts = [
    "Una mujer embarazada fue asesinada en su hogar. Tenía 25 años.",
    "El feminicidio ocurrió en presencia de sus tres hijos menores de edad.",
    "La víctima era madre de dos niños de 5 y 8 años que presenciaron el crimen.",
    "Una adolescente de 16 años fue encontrada sin vida.",
    "La mujer de 30 años no tenía hijos ni familia cercana.",
    "El sospechoso atacó a la víctima frente a sus pequeños hijos.",
    "Una estudiante universitaria fue reportada como desaparecida.",
    "La madre soltera cuidaba a sus tres bebés cuando ocurrió el ataque."
]

if __name__ == "__main__":
    print("🔍 PROBANDO EL ANALIZADOR MEJORADO DE NNA\n")
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n--- PRUEBA {i} ---")
        test_analyzer(text)
