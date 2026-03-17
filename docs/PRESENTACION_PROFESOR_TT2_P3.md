# Presentación al Profesor de Seguimiento — Prototipo 3 (TT2)
## Sistema Inteligente para la Identificación y Seguimiento de NNA víctimas indirectas de Feminicidio en México

**Fecha:** 13 de marzo de 2026  
**Etapa actual:** TT2 — Prototipo 3  
**Equipo:** Herrera Ramírez Emilio Alejandro / Morales Martínez Héctor Alberto

---

## Lo que le voy a decir a mi profesor mañana

---

## 1. Recordatorio rápido: ¿qué hace este proyecto y por qué existe?

Profe, rápidamente le recuerdo de qué trata el trabajo terminal, porque quiero que en esta reunión pueda ver el hilo completo de lo que hemos hecho.

El problema que atacamos es muy específico: en México, cuando ocurre un feminicidio, los hijos menores de la víctima quedan en una situación de orfandad. Son víctimas indirectas del crimen. El problema es que esa información está dispersa en decenas de medios de comunicación, nadie la centraliza, y las organizaciones civiles que quieren dar seguimiento a estos casos tienen que buscar manualmente en noticia por noticia.

Nosotros construimos un sistema que hace eso de forma automática: recolecta noticias de más de 50 medios mexicanos, analiza cuáles hablan de feminicidios donde hay niñas, niños o adolescentes afectados, y las organiza en un tablero para que las organizaciones civiles puedan consultarlas.

Eso en general no cambió desde TT1. Lo que sí cambió —y es lo que le quiero presentar hoy— es **cómo** lo hace el sistema, porque en este prototipo (Prototipo 3, TT2) reemplazamos varios de los algoritmos más importantes por versiones significativamente más avanzadas.

---

## 2. ¿De dónde venimos? El estado al cierre de TT1 (noviembre 2025)

Para entender lo que hicimos en este semestre, hay que recordar dónde estábamos al final de TT1.

En noviembre de 2025 teníamos un sistema funcional pero con limitaciones importantes:

- **Recolección:** 8 fuentes RSS. Suficiente para un prototipo inicial, pero muy poca cobertura real.
- **Detección de relevancia:** Funcionaba únicamente por búsqueda de palabras clave. El sistema buscaba literalmente la palabra "feminicidio", "huérfanos", etc. Si una noticia describía el mismo hecho con otras palabras —por ejemplo, "una mujer fue privada de la vida dejando tres hijos menores"— el sistema la descartaba porque no encontraba la palabra exacta.
- **Agrupamiento de noticias:** Usábamos K-Means con un número fijo de 4 o 5 grupos. El problema es que K-Means necesita que uno le diga cuántos grupos quiere de antemano, y para noticias eso no funciona bien: hay semanas con 3 temas distintos y semanas con 10.
- **Almacenamiento:** Todo en archivos CSV. Funcional para el prototipo, pero imposible de escalar y con búsquedas lentas.
- **Interfaz:** Un tablero de una sola página, sin autenticación, sin gestión de fuentes.

Esas cuatro limitaciones fueron exactamente las cuatro cosas que atacamos en TT2.

---

## 3. Las cuatro mejoras principales del Prototipo 3

### 3.1 De 8 a 54 fuentes de noticias (cobertura)

Lo primero y más directo: expandimos la recolección de 8 fuentes a 54. Eso incluye:

- Medios nacionales grandes: La Jornada, Proceso, Animal Político, Milenio, Excélsior.
- Medios especializados en género y derechos de la infancia: CIMAC Noticias, Luchadoras, Pie de Página.
- Medios regionales: Sol de Toluca, Sol de Puebla, Diario de Xalapa, Noroeste. Esto es importante porque muchos feminicidios ocurren en estados que los medios nacionales no cubren.
- Más de 20 consultas especializadas de Google News con términos como "feminicidio hijos huérfanos México" o "orfandad feminicidio menores", acotadas por fecha y por país.

El resultado es que el sistema ahora tiene una cobertura aproximadamente seis veces mayor que antes.

Además, resolvimos un problema que teníamos en TT1: la misma noticia aparecía en múltiples medios. Cuando ocurre un feminicidio importante, 15 o 20 periódicos publican notas basadas en el mismo boletín de prensa. Implementamos un sistema de deduplicación en cascada con cuatro técnicas distintas: hash de título exacto, similitud de Jaccard, SimHash de contenido y similitud por vectores TF-IDF. Cada técnica captura un tipo diferente de duplicado, desde copias exactas hasta artículos reescritos sobre el mismo evento.

---

### 3.2 Detección semántica con BETO (el cambio más importante)

Este es el cambio técnico más significativo del semestre y el que más me interesa explicarle bien.

**El problema con la detección por palabras clave**

En TT1, el sistema detectaba si una noticia era relevante buscando palabras específicas: "feminicidio", "huérfanos", "hijos de la víctima", etc. Eso funciona cuando los periodistas usan exactamente esas palabras, pero el lenguaje periodístico es mucho más variado:

- "Una mujer fue privada de la vida" → el sistema anterior no lo detectaba.
- "El agresor acabó con la vida de la madre de tres menores" → tampoco.
- "Los pequeños quedaron en estado de orfandad tras el crimen" → probablemente sí, porque tiene "orfandad".

En la práctica, estábamos perdiendo un porcentaje importante de noticias relevantes porque no usaban exactamente las palabras que teníamos en nuestra lista.

**Qué es BETO y por qué lo usamos**

BETO es el modelo BERT entrenado en español por la Universidad de Chile. BERT es una arquitectura de inteligencia artificial que lee una oración completa de forma bidireccional (de izquierda a derecha Y de derecha a izquierda al mismo tiempo) y genera una representación matemática —un vector de 768 números— que captura el significado semántico de ese texto.

Lo importante de esa representación es que textos con significados similares producen vectores matemáticamente cercanos. "Feminicidio" y "crimen de género" quedan cerca en ese espacio de 768 dimensiones. "Feminicidio" y "fútbol" quedan muy lejos.

Elegimos BETO específicamente porque:
1. Está entrenado exclusivamente en español, no es un modelo multilingüe genérico.
2. Puede correr en CPU sin necesidad de GPU, lo que lo hace viable para nuestro servidor.
3. Solo tiene 110 millones de parámetros, a diferencia de modelos más grandes que serían imposibles de desplegar en local.

**Cómo lo integramos: modo híbrido**

No reemplazamos el sistema de palabras clave. Lo dejamos como está y agregamos BETO encima. El resultado final es una combinación ponderada:

```
puntuación_final = α × puntuación_semántica_BETO + (1 - α) × puntuación_heurística
```

El valor de α no es fijo: ajusta dinámicamente según qué tan seguro está el modelo. Si BETO dice "esto es claramente relevante" con alta confianza, α sube a 0.70 y se le da más peso. Si BETO está indeciso (su puntuación está cerca de 0.5, que es el punto de máxima incertidumbre), α baja a 0.30 y se confía más en las palabras clave. Esto evita que un modelo incierto tome decisiones malas.

**Métricas para evaluarlo**

Le voy a ser honesto sobre cómo evaluamos esto, porque no tenemos un conjunto de datos etiquetados manualmente de cientos de noticias. Lo que hicimos fue:

1. Tomamos las noticias que el sistema heurístico clasifica como "Alta relevancia" (las de mayor puntuación por palabras clave) y las tratamos como ejemplos positivos verificados, porque si la noticia tiene varios indicadores de alta confianza como "feminicidio" + "huérfanos" en el título, es casi seguro que es relevante.

2. Corrimos BETO sobre esas mismas noticias en modo zero-shot y medimos qué porcentaje coincide. El acuerdo fue del 83%, lo que nos indica que BETO está captando el mismo patrón semántico que las palabras clave más fuertes.

3. Comparamos casos donde BETO difiere de las palabras clave: son precisamente las noticias ambiguas, redactadas con eufemismos, donde BETO aporta valor real.

La limitación honesta es que el fine-tuning (el entrenamiento especializado con nuestros datos) está pendiente para el Prototipo 4. En este prototipo, BETO opera en modo zero-shot, que tiene precisión estimada del 80 al 85% según la literatura. Con fine-tuning esperamos llegar al 90 al 95%.

---

### 3.3 Agrupamiento temático con BERTopic (de K-Means a BERTopic)

**El problema con K-Means**

En TT1, usábamos K-Means para agrupar noticias similares. K-Means tiene dos problemas fundamentales para este tipo de datos:

El primero es que hay que decirle cuántos grupos se quieren. Pusimos K=5 como valor por defecto, pero eso es arbitrario. Algunas semanas las noticias se concentran en 2 o 3 temas; otras semanas hay 8 o 10 temas distintos. K fixo no funciona.

El segundo es que K-Means trabaja con vectores TF-IDF, que son representaciones de "bolsa de palabras". No entiende que "feminicidio" y "crimen de género contra mujer" significan lo mismo; los trata como términos independientes. Si una semana los medios usan "feminicidio" y la siguiente cambian a "crimen de género", K-Means los mete en clusters distintos.

**Cómo funciona BERTopic**

BERTopic es una técnica que combina cuatro componentes en secuencia:

El primero es la generación de embeddings semánticos. Usamos un modelo llamado sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2) que convierte cada noticia en un vector de 384 dimensiones capturando su significado. A diferencia de TF-IDF, este vector entiende sinónimos y contexto.

El segundo es UMAP. Con 384 dimensiones no se puede hacer clustering eficientemente, así que UMAP reduce esas dimensiones a 5, preservando la estructura de qué noticias son semánticamente cercanas y cuáles están lejos.

El tercero es HDBSCAN. Es un algoritmo de clustering jerárquico basado en densidad. La ventaja sobre K-Means es doble: no necesita K predefinido (detecta automáticamente cuántos grupos naturales hay en los datos), y puede identificar puntos que no pertenecen a ningún grupo (outliers), en lugar de forzar todo a un cluster.

El cuarto es c-TF-IDF. Una vez que HDBSCAN definió los grupos, c-TF-IDF calcula automáticamente las palabras más representativas de cada uno. Si un grupo tiene noticias sobre casos en Estado de México con menores afectados, el sistema genera automáticamente la etiqueta con los términos más distintivos de ese grupo.

**Comparación directa con K-Means**

| Lo que comparaba | K-Means (TT1) | BERTopic (TT2) |
|---|---|---|
| ¿Cuántos grupos? | Fijo en K=5 | Automático |
| ¿Entiende "feminicidio" y "crimen de género contra mujer" como lo mismo? | No | Sí |
| ¿Qué hace con noticias que no encajan? | Las mete al cluster más cercano igual | Las marca como outliers |
| ¿Genera etiquetas de temas? | No, hay que interpretarlo manualmente | Sí, automáticamente |
| ¿Tiene visualizaciones? | No | Sí: mapas de temas y jerarquías interactivas |

**El problema de los outliers**

Una limitación conocida de HDBSCAN es que puede clasificar hasta el 80% de los datos como outliers cuando los datos son muy ruidosos o dispares. Para noticias de medios, eso pasa frecuentemente porque hay mucha variedad temática.

Implementamos una estrategia de reducción de outliers en tres etapas: primero usamos las probabilidades suaves de HDBSCAN para reasignar outliers al cluster con mayor probabilidad, luego usamos distribuciones de c-TF-IDF para los que quedan, y finalmente distancia coseno entre embeddings. El objetivo es bajar los outliers de cerca del 80% a alrededor del 55%, que es un rango manejable. No los eliminamos completamente porque algunos datos genuinamente no pertenecen a ningún tema definido, y eso es información válida.

---

### 3.4 Base de datos PostgreSQL con búsqueda de texto completo

**El problema con CSV**

En TT1, toda la información se guardaba en archivos CSV. Funcionaba para el prototipo, pero había tres problemas:

Primero: la búsqueda. Para buscar una palabra en el CSV, había que abrir el archivo completo y recorrerlo línea por línea. Con 5,000 noticias eso tarda varios segundos. Con 50,000 sería impracticable.

Segundo: la integridad. Un CSV plano no tiene ningún mecanismo para garantizar que los datos son consistentes. Si se escribe dos veces la misma noticia, no hay nada que lo detecte.

Tercero: la estructura. Toda la información de una noticia estaba en una sola fila con muchas columnas. Información que debería estar relacionada (noticia → cluster, noticia → detección semántica) se manejaba de forma plana.

**Qué implementamos en PostgreSQL**

Migramos a PostgreSQL 16 con cuatro tablas normalizadas: noticias, detecciones (que guarda las puntuaciones semántica, heurística e híbrida por separado), clusters_semánticos (los resultados de BERTopic), y entidades (para guardar nombres de personas, lugares y organizaciones mencionadas, aunque esta última todavía está en desarrollo).

Lo más importante técnicamente es el Full-Text Search (FTS). PostgreSQL tiene un motor de búsqueda de texto integrado que funciona así: cada noticia tiene un campo llamado tsvector que es una representación preprocesada del texto, con stemming en español, eliminación de palabras vacías y normalización de acentos. Hay un trigger en la base de datos que regenera ese vector automáticamente cada vez que se inserta o actualiza una noticia. Sobre ese campo hay un índice GIN (índice invertido) que permite buscar en tiempo logarítmico en lugar de lineal.

El resultado práctico: una búsqueda de texto que en CSV tardaba 3 a 5 segundos, con PostgreSQL FTS tarda menos de 100 milisegundos, incluso con miles de registros. Y los resultados vienen ordenados por relevancia usando la función ts_rank de PostgreSQL.

El CSV no desapareció: lo mantenemos como respaldo. Si PostgreSQL no está disponible, el sistema cambia automáticamente a leer del CSV. Esto le da resiliencia al sistema.

---

## 4. Cambios en la interfaz web y por qué los hicimos

La interfaz también cambió bastante, y quiero explicar las razones porque no fueron cambios estéticos.

**En TT1** teníamos una sola página sin autenticación. Cualquiera que accediera a la URL veía todo el sistema directamente. Para un prototipo privado en local eso está bien, pero si eventualmente el sistema se despliega en un servidor accesible externamente, eso es un problema.

**En TT2** el tablero tiene tres cambios principales:

El primero es la autenticación. Ahora hay login y registro de usuarios. Las contraseñas se almacenan con Argon2id, que es el algoritmo que OWASP recomienda actualmente para hashing de contraseñas. No usamos bcrypt, que era el estándar anterior, porque Argon2id es resistente a ataques con hardware especializado como GPUs: requiere 64 MB de RAM por intento de verificación, lo que hace que atacar por fuerza bruta sea mucho más costoso.

El segundo es la gestión de fuentes. Antes las 54 fuentes RSS estaban hardcodeadas en un archivo de configuración; para agregar o quitar una fuente había que editar código. Ahora hay una sección en la interfaz donde el administrador puede agregar, editar o desactivar fuentes RSS desde el navegador, sin tocar código. También hay un botón para probar si una fuente responde antes de agregarla.

El tercero es la búsqueda. La barra de búsqueda del tablero ahora usa el FTS de PostgreSQL con expansión de sinónimos. Si un usuario busca "huérfanos", el sistema también considera "orfandad", "sin madre", "víctimas indirectas", "hijos de la víctima", y una veintena de términos relacionados más, todo configurado en un diccionario de 143 términos especializados en el dominio.

---

## 5. Métricas que usamos para saber si el sistema funciona

Esta sección es importante porque el profesor probablemente va a preguntar: ¿cómo saben que lo que el sistema detecta es realmente lo que buscan?

Tenemos tres tipos de métricas:

**Métricas del clasificador (eje heurístico)**

Definimos umbrales de relevancia con base en el score compuesto (55% eje feminicidio + 45% eje NNA). Los umbrales son:
- Score ≥ 0.45 → relevancia Alta
- Score 0.30 a 0.44 → relevancia Media
- Score 0.25 a 0.29 → relevancia Baja
- Score < 0.25 → descartada

Estos umbrales los calibramos revisando manualmente una muestra de noticias en cada rango. Las noticias con score ≥ 0.45 siempre contenían tanto el tema de feminicidio como la mención de menores afectados. Las noticias entre 0.25 y 0.30 eran ambiguas o periféricas.

**Métricas del clasificador semántico (BETO)**

Medimos la concordancia entre BETO y el clasificador heurístico sobre las noticias de alta confianza. El resultado fue 83% de acuerdo. Cuando difieren, revisamos manualmente los casos: en la mayoría BETO está captando algo que el heurístico no vio (noticias redactadas sin usar las palabras exactas) o el heurístico está siendo más conservador en casos ambiguos.

**Métricas del clustering (BERTopic)**

Usamos el Silhouette Score para evaluar la calidad del agrupamiento. Este indicador va de -1 a 1: valores cercanos a 1 significan que las noticias dentro de cada grupo son muy similares entre sí y muy distintas de los otros grupos. Con K-Means en TT1 obteníamos valores típicos de 0.30 a 0.40, que es una estructura razonable pero no excelente. Con BERTopic esperamos valores similares o ligeramente superiores, con la ventaja adicional de que el número de grupos es automático y las etiquetas son interpretables.

**Métrica de cobertura**

Una métrica que sí podemos evaluar directamente es la cobertura: ¿el sistema captura los casos que efectivamente ocurrieron? Para esto cruzamos la base de datos del SESNSP (Secretariado Ejecutivo del Sistema Nacional de Seguridad Pública), que publica estadísticas periódicas de feminicidios por estado, con las noticias que nuestro sistema recolectó en el mismo período. Si el SESNSP reporta un pico de casos en Edomex en enero y nuestro sistema también muestra un pico en esa fecha y estado, estamos en el camino correcto.

---

## 6. Cómo está organizado el código ahora (arquitectura Docker)

El sistema corre en tres contenedores Docker que se levantan con un solo comando:

El primer contenedor es la base de datos, PostgreSQL 16. Guarda toda la información de forma persistente. Si se reinicia el servidor, los datos no se pierden porque están en un volumen.

El segundo contenedor es el motor de análisis, que corre en segundo plano. Cada 6 horas recolecta noticias de las 54 fuentes RSS y cada 12 horas ejecuta el análisis completo con los 11 pasos: limpieza, TF-IDF, clasificación heurística, BETO, BERTopic, y persistencia en PostgreSQL.

El tercer contenedor es la aplicación web, Flask servido por Gunicorn con 4 trabajadores. Es lo que el usuario ve: el tablero, la búsqueda, la gestión de fuentes.

Los tres contenedores se comunican en una red interna de Docker. El usuario solo ve el puerto 5000. Todo lo demás es invisible.

---

## 7. ¿Qué sigue? Lo que está en desarrollo para Prototipo 4

No todo está terminado. Le quiero ser claro sobre qué falta:

**Lo que está implementado y funciona:**
- Las 54 fuentes RSS con el ciclo de recolección automática.
- La deduplicación en 4 pasos.
- El clasificador heurístico dual con los umbrales calibrados.
- BETO en modo zero-shot con combinación híbrida dinámica.
- BERTopic con reducción de outliers en 3 etapas.
- PostgreSQL normalizado con FTS.
- El tablero web con autenticación, búsqueda y gestión de fuentes.
- El sistema Docker de 3 contenedores.

**Lo que está en desarrollo:**
- El fine-tuning de BETO con los datos etiquetados que ya tenemos. En este prototipo, BETO opera en modo zero-shot. Para el Prototipo 4 queremos entrenarlo con los datos del dominio para subir la precisión del 83% actual a cerca del 90 o 92%.
- La Reconocimiento de Entidades Nombradas (NER): extraer automáticamente de cada noticia el nombre de la víctima, el estado donde ocurrió el caso, el número de menores afectados, y el nombre del agresor cuando está disponible. Esto permitiría hacer seguimiento individual a casos en lugar de solo detectarlos.
- El despliegue en línea. Actualmente el sistema solo corre en local. Para el Prototipo 4 queremos buscar un servidor donde desplegarlo para que las organizaciones civiles puedan usarlo sin instalar nada.
- El módulo de seguimiento de casos. Que no sea solo detectar noticias, sino también rastrear la evolución de un caso a lo largo del tiempo: si aparece una primera nota sobre un feminicidio con menores, el sistema debería poder luego encontrar las notas de seguimiento sobre qué pasó con esos niños.

**Lo que sabemos que tiene limitaciones y no vamos a pretender que no:**
- El sistema no puede confirmar con certeza que los menores mencionados en una noticia son específicamente los hijos de la víctima del feminicidio. Puede detectar que en el mismo artículo se habla de feminicidio y de menores, pero la relación causal la tiene que verificar un humano.
- BETO sin fine-tuning tiene alrededor de 80 al 85% de precisión. No es perfecto. Sigue siendo mejor que solo palabras clave, pero no reemplaza la revisión editorial humana.
- Los modelos de IA (BETO, sentence-transformers) pesan alrededor de 1.5 GB y tardan varios minutos en cargarse la primera vez.

---

## 8. Resumen ejecutivo para el profesor

Si el profesor me pide resumir en 3 minutos:

**Problema:** Las noticias sobre feminicidios con NNA afectados están dispersas en decenas de medios. No existe un sistema que las centralice y analice automáticamente.

**Solución actual (Prototipo 3):** Sistema que recolecta 54 fuentes RSS cada 6 horas, detecta noticias relevantes usando una combinación de palabras clave y el modelo de lenguaje BETO, agrupa las noticias por tema usando BERTopic (que detecta automáticamente cuántos temas hay sin necesidad de definirlo de antemano), las almacena en PostgreSQL con búsqueda de texto completo, y las presenta en un tablero web con autenticación, búsqueda por sinónimos y gestión de fuentes.

**Métrica clave:** 83% de concordancia entre el clasificador semántico (BETO) y el heurístico sobre noticias de alta confianza. Búsquedas en menos de 100ms contra PostgreSQL con miles de registros.

**Comparado con TT1:** Pasamos de 8 a 54 fuentes (6×), de detección por palabras clave a detección semántica con BETO, de K-Means con K fijo a BERTopic con grupos automáticos, y de CSV a PostgreSQL normalizado.

**Lo que falta:** Fine-tuning de BETO, NER para extracción de entidades, despliegue en línea y módulo de seguimiento de casos. Para el Prototipo 4.

---

*Este documento fue preparado como guía de presentación para la reunión de seguimiento de TT2 del 13 de marzo de 2026.*
