# -*- coding: utf-8 -*-
"""Análisis de categorías de falsos positivos."""
import pandas as pd
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

df = pd.read_csv('data/noticias_analyzed_simplified.csv')
fp = df[(df['clasificacion_final'] == 'Alta') & (df['etiqueta_corregida'] == 0)]

categories = {
    'MENOR_VICTIMA_DIRECTA': [],
    'FEMINICIDIO_SIN_NNA_ORFANDAD': [],
    'ESTADISTICAS_LEYES_OPINION': [],
    'ASESINATO_INVERTIDO': [],  # hijo mata a madre, mujer mata a esposo, etc.
    'MENOR_AGRESOR_O_DETENIDO': [],
    'ABUSO_SEXUAL_EXPLOTACION': [],
    'ORFANDAD_TEMATICO': [],  # artículo temático, no caso fáctico
    'OTRO': []
}

for i, row in fp.iterrows():
    t = str(row['titulo']).lower()
    
    # 1) Hijo/hija mata a madre/padre (roles invertidos)
    if any(x in t for x in ['hijo la mat', 'hijo presuntamente mata', 'hijo la habría',
        'hijo que mató', 'hijo la asesinó', 'hija de 8 año', 'feminicidio de su hija',
        'asesina a su hija', 'mujer por la muerte de su hijo', 'olvidarlo 12 horas',
        'asesina a su esposo', 'asesina a su comadre', 'su hijo la habría asesinado',
        'hijo habría matado', 'hijo en el auto', 'hijo para contarle', 
        'maestra es asesinada', 'hija y su yerno fueron detenidos',
        'su hijo la mat', 'patricia le reclam']):
        categories['ASESINATO_INVERTIDO'].append(i)
    # 2) Menor como víctima directa (asesinado, no huérfano)
    elif any(x in t for x in ['menor asesinada', 'menor asesinado', 'menor víctima de feminicidio',
        'menor de 15', 'feminicidio de jovencita', 'menor desaparecida encontrada sin vida',
        'niña asesinada', 'muerte de una mujer y un beb', 'mueren en ataque',
        'britany', 'ayla fernanda', 'menor que fue exhibida',
        'identifican a menor asesinad', 'hijo de 3 años al olvidarlo',
        'mesero en restaurante', 'pareja de tercera edad', 'hombre mientras recogía',
        'asesinan a colombiano', 'balazos a hombre', 'matan a hombre',
        'hijo de el candela', 'matan a madre e hijo cuando intentaban',
        'ataque armado en parque infantil']):
        categories['MENOR_VICTIMA_DIRECTA'].append(i)
    # 3) Menor como agresor / detenido
    elif any(x in t for x in ['detienen a menor', 'adolescente por feminicidio',
        'formulan imputación a adolescente', 'menor por feminicidio',
        'la diabla', 'detienen a 5 relacionados', 'menor de 17 años',
        'justicia para adolescentes', 'menor en corral']):
        categories['MENOR_AGRESOR_O_DETENIDO'].append(i)
    # 4) Estadísticas, leyes, opinión
    elif any(x in t for x in ['estadístic', 'cifra', 'lugar en', 'tercer lugar',
        'séptimo lugar', '8 de cada 10', '884 niñas', 'murieron asesinados',
        'se disparó 30%', 'resultados de 2025', 'se recrudece',
        'quinto en corrupción']):
        categories['ESTADISTICAS_LEYES_OPINION'].append(i)
    # 5) Orfandad como tema genérico / legislativo
    elif any(x in t for x in ['orfandad', 'registro de orfandad', 'visibilizar la orfandad',
        'obligará al estado', 'congreso de campeche', 'incrementa recursos',
        'sentencia coidh', 'corte idh', 'niñas sin ley', 'deuda que empezó',
        'edomex incrementa']):
        categories['ORFANDAD_TEMATICO'].append(i)
    # 6) Abuso sexual / explotación (no feminicidio)
    elif any(x in t for x in ['abuso sexual', 'abuso a menores', 'corrupción de menores',
        'extorsión a mujeres', 'el abuso sexual no se calla',
        'cuidar lo que ven sus hijos']):
        categories['ABUSO_SEXUAL_EXPLOTACION'].append(i)
    # 7) Otros irrelevantes
    elif any(x in t for x in ['beca rita cetina', 'kristina vladímirovna',
        'acoso y rechaza amenazas', 'norma andrade', 'supuesta carta']):
        categories['OTRO'].append(i)
    else:
        categories['FEMINICIDIO_SIN_NNA_ORFANDAD'].append(i)

print('=== CLASIFICACIÓN DE 127 FALSOS POSITIVOS ===\n')
total = 0
for cat, indices in categories.items():
    total += len(indices)
    print(f'{cat}: {len(indices)} noticias')
    for idx in indices[:3]:
        titulo = str(df.loc[idx, 'titulo'])[:110]
        print(f'  [{idx}] {titulo}')
    if len(indices) > 3:
        print(f'  ... y {len(indices)-3} más')
    print()
print(f'TOTAL clasificados: {total} / {len(fp)}')

# También analizar scores de VP vs FP
print('\n=== SCORE DISTRIBUTIONS ===')
vp = df[df['etiqueta_corregida'] == 1]
print(f'VP scores: mean={vp["score_semantico"].mean():.4f}, min={vp["score_semantico"].min():.4f}, max={vp["score_semantico"].max():.4f}')
print(f'FP scores: mean={fp["score_semantico"].mean():.4f}, min={fp["score_semantico"].min():.4f}, max={fp["score_semantico"].max():.4f}')
print(f'\nVP con score > 0: {len(vp[vp["score_semantico"] > 0])}')
print(f'VP con score = 0: {len(vp[vp["score_semantico"] == 0])}')
