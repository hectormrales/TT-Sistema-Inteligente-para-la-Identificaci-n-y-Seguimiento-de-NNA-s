# Implementación de Modelos de Lenguaje Pre-entrenados en el Sistema NNA
## Integración de BETO para Búsqueda Semántica Avanzada

### Arquitectura Propuesta

#### Componente Actual vs Mejorado

**ACTUAL (Diccionarios):**
```
Usuario busca "violencia" → Diccionario estático → ["agresión", "maltrato"] → Búsqueda literal
```

**PROPUESTO (BETO):**
```
Usuario busca "violencia" → BETO genera embedding → Similitud semántica → Encuentra "daño psicológico", "coerción", "intimidación"
```

### Implementación Técnica

#### 1. Nuevas Dependencias Requeridas

```python
# requirements_advanced.txt
transformers==4.35.0
torch==2.1.0
sentence-transformers==2.2.2
datasets==2.14.0
accelerate==0.24.0
```

#### 2. Nueva Clase: Analizador Semántico

```python
# src/analysis/semantic_analyzer.py
from transformers import AutoTokenizer, AutoModel, Trainer, TrainingArguments
from sentence_transformers import SentenceTransformer
import torch
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
from typing import List, Tuple

class BETOSemanticAnalyzer:
    def __init__(self):
        # Cargar BETO pre-entrenado
        self.model_name = "dccuchile/bert-base-spanish-wwm-uncased"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)
        
        # Para embeddings más eficientes
        self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Cache de embeddings para optimización
        self.embeddings_cache = {}
        self.corpus_embeddings = None
        
    def prepare_corpus_for_training(self, df_noticias: pd.DataFrame) -> List[str]:
        """
        Prepara el corpus de noticias para fine-tuning
        """
        # Filtrar solo noticias con menciones NNA para corpus especializado
        nna_noticias = df_noticias[df_noticias['menores_identificados'] == 'Si']
        
        # Combinar título y contenido
        corpus = []
        for _, row in nna_noticias.iterrows():
            texto_completo = f"{row['titulo']} {row['contenido']}"
            corpus.append(texto_completo)
        
        return corpus
    
    def create_training_dataset(self, corpus: List[str]):
        """
        Crea dataset de entrenamiento para fine-tuning
        """
        # Tokenizar el corpus
        tokens = self.tokenizer(
            corpus, 
            padding=True, 
            truncation=True, 
            max_length=512,
            return_tensors="pt"
        )
        
        return tokens
    
    def fine_tune_beto(self, corpus: List[str], output_dir: str = "models/beto-nna-finetuned"):
        """
        Fine-tunea BETO con el corpus de noticias NNA
        """
        print("Iniciando fine-tuning de BETO...")
        
        # Preparar datos de entrenamiento
        dataset = self.create_training_dataset(corpus)
        
        # Configurar entrenamiento
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=3,
            per_device_train_batch_size=8,
            warmup_steps=500,
            weight_decay=0.01,
            logging_dir='./logs',
            save_steps=1000,
            eval_steps=1000,
        )
        
        # Crear trainer (simplificado para MLM - Masked Language Modeling)
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=dataset,
            tokenizer=self.tokenizer,
        )
        
        # Entrenar
        trainer.train()
        
        # Guardar modelo afinado
        trainer.save_model()
        print(f"Modelo afinado guardado en: {output_dir}")
    
    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Genera embeddings usando el modelo (fine-tuned si está disponible)
        """
        embeddings = []
        
        for text in texts:
            # Usar cache si está disponible
            if text in self.embeddings_cache:
                embeddings.append(self.embeddings_cache[text])
                continue
            
            # Tokenizar y generar embedding
            inputs = self.tokenizer(
                text, 
                return_tensors="pt", 
                padding=True, 
                truncation=True, 
                max_length=512
            )
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                # Usar el [CLS] token como representación de la oración
                embedding = outputs.last_hidden_state[:, 0, :].numpy().flatten()
                
            embeddings.append(embedding)
            self.embeddings_cache[text] = embedding
        
        return np.array(embeddings)
    
    def build_semantic_index(self, df_noticias: pd.DataFrame):
        """
        Construye índice semántico de todas las noticias
        """
        print("Construyendo índice semántico...")
        
        # Preparar textos
        textos = []
        for _, row in df_noticias.iterrows():
            texto_completo = f"{row['titulo']} {row['contenido']}"
            textos.append(texto_completo)
        
        # Generar embeddings
        self.corpus_embeddings = self.generate_embeddings(textos)
        
        print(f"Índice semántico creado para {len(textos)} noticias")
    
    def semantic_search(self, query: str, df_noticias: pd.DataFrame, top_k: int = 10) -> pd.DataFrame:
        """
        Búsqueda semántica usando similaridad de embeddings
        """
        if self.corpus_embeddings is None:
            self.build_semantic_index(df_noticias)
        
        # Generar embedding de la consulta
        query_embedding = self.generate_embeddings([query])
        
        # Calcular similitudes
        similarities = cosine_similarity(query_embedding, self.corpus_embeddings)[0]
        
        # Obtener índices de los más similares
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # Crear DataFrame con resultados
        resultados = df_noticias.iloc[top_indices].copy()
        resultados['similitud_semantica'] = similarities[top_indices]
        
        return resultados.sort_values('similitud_semantica', ascending=False)
    
    def detect_nna_semantic(self, text: str, threshold: float = 0.7) -> bool:
        """
        Detección semántica de menciones NNA usando embeddings
        """
        # Términos de referencia para NNA
        nna_references = [
            "niños huérfanos por violencia",
            "menores afectados por feminicidio", 
            "hijos de víctimas de violencia de género",
            "niñas en situación de orfandad",
            "adolescentes víctimas indirectas"
        ]
        
        # Generar embeddings
        text_embedding = self.generate_embeddings([text])
        ref_embeddings = self.generate_embeddings(nna_references)
        
        # Calcular similitud máxima
        max_similarity = np.max(cosine_similarity(text_embedding, ref_embeddings))
        
        return max_similarity > threshold
```

#### 3. Integración en el Analizador Principal

```python
# Modificación en simplified_analyzer.py
from src.analysis.semantic_analyzer import BETOSemanticAnalyzer

class SimplifiedNewsAnalyzer:
    def __init__(self):
        # Código existente...
        
        # Nuevo: Analizador semántico
        self.semantic_analyzer = BETOSemanticAnalyzer()
        self.use_semantic_search = True
        
    def step_8_semantic_enhancement(self) -> pd.DataFrame:
        """
        NUEVA ETAPA: Mejora semántica con BETO
        """
        print("=== PASO 8: ANÁLISIS SEMÁNTICO CON BETO ===")
        
        # Fine-tune con nuestro corpus si no existe modelo
        corpus = self.semantic_analyzer.prepare_corpus_for_training(self.df_processed)
        
        if len(corpus) > 50:  # Mínimo de noticias para fine-tuning
            print("Realizando fine-tuning de BETO...")
            self.semantic_analyzer.fine_tune_beto(corpus)
        
        # Construir índice semántico
        self.semantic_analyzer.build_semantic_index(self.df_processed)
        
        # Re-evaluar detección NNA con semántica
        print("Re-evaluando detección NNA con análisis semántico...")
        semantic_nna = []
        for _, row in self.df_processed.iterrows():
            texto = f"{row['titulo']} {row['contenido']}"
            is_nna_semantic = self.semantic_analyzer.detect_nna_semantic(texto)
            semantic_nna.append('Si' if is_nna_semantic else 'No')
        
        self.df_processed['nna_semantico'] = semantic_nna
        
        # Combinar detección tradicional y semántica
        self.df_processed['deteccion_combinada'] = self.df_processed.apply(
            lambda row: 'Si' if (row['menores_identificados'] == 'Si' or 
                                row['nna_semantico'] == 'Si') else 'No',
            axis=1
        )
        
        print(f"Detección tradicional: {(self.df_processed['menores_identificados'] == 'Si').sum()} casos")
        print(f"Detección semántica: {(self.df_processed['nna_semantico'] == 'Si').sum()} casos")
        print(f"Detección combinada: {(self.df_processed['deteccion_combinada'] == 'Si').sum()} casos")
        
        return self.df_processed
    
    def search_semantic_enhanced(self, query: str, max_results: int = 10) -> pd.DataFrame:
        """
        Búsqueda mejorada con análisis semántico
        """
        if self.use_semantic_search and hasattr(self, 'semantic_analyzer'):
            return self.semantic_analyzer.semantic_search(query, self.df_processed, max_results)
        else:
            # Fallback a búsqueda tradicional
            return self.search_enhanced(query, max_results)
```

#### 4. API Mejorada con Búsqueda Semántica

```python
# Modificación en app_docker.py
@app.route('/api/search/semantic', methods=['GET'])
def search_semantic():
    try:
        query = request.args.get('q', '')
        max_results = int(request.args.get('limit', 10))
        
        if not query:
            return jsonify({'error': 'Query parameter required'}), 400
        
        # Búsqueda semántica
        resultados = analyzer.search_semantic_enhanced(query, max_results)
        
        # Formatear resultados
        noticias = []
        for _, row in resultados.iterrows():
            noticia = {
                'titulo': row['titulo'],
                'contenido': row['contenido'][:200] + '...',
                'fecha': row['fecha'],
                'fuente': row['fuente'],
                'similitud_semantica': float(row.get('similitud_semantica', 0)),
                'cluster': int(row.get('cluster', 0)),
                'topic_id': int(row.get('topic_id', 0))
            }
            noticias.append(noticia)
        
        return jsonify({
            'query': query,
            'resultados': len(noticias),
            'noticias': noticias,
            'tipo_busqueda': 'semantica'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Ventajas de esta Implementación

#### 1. Mejora Significativa en Detección
- **Antes**: "hijo" → solo encuentra "hijo"
- **Después**: "hijo" → encuentra "menor", "descendiente", "vástago", "progenie"

#### 2. Contexto Semántico
- Entiende que "quedó huérfana" está relacionado con casos NNA
- Detecta "menor de edad afectada" aunque no use palabras clave exactas

#### 3. Búsqueda Inteligente
- Usuario busca "violencia doméstica" → encuentra "maltrato familiar", "agresión en el hogar"
- Consulta "niños afectados" → localiza "menores impactados", "infantes perjudicados"

### Plan de Implementación Gradual

#### Fase 1: Preparación (2-3 días)
1. Actualizar requirements.txt con nuevas dependencias
2. Crear el módulo semantic_analyzer.py
3. Probar carga de BETO básico

#### Fase 2: Integración (3-5 días)  
1. Integrar en el pipeline principal como Etapa 8
2. Implementar API endpoint para búsqueda semántica
3. Crear interfaz web con opción "Búsqueda Semántica"

#### Fase 3: Fine-tuning (5-7 días)
1. Acumular corpus suficiente (200+ noticias NNA)
2. Ejecutar fine-tuning de BETO
3. Validar mejoras en precisión de detección

#### Fase 4: Optimización (3-5 días)
1. Implementar cache de embeddings para velocidad
2. Optimizar modelos para uso en Docker
3. Documentar nuevas capacidades

### Consideraciones de Recursos

#### Computacionales
- **RAM**: Mínimo 8GB (BETO requiere ~2-3GB)
- **Almacenamiento**: +2GB para modelos pre-entrenados
- **CPU**: Procesamiento más lento sin GPU (aceptable para prototipo)

#### Docker
```dockerfile
# Dockerfile modificado
FROM python:3.11-slim

# Instalar dependencias de PyTorch
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Resto de la instalación...
```

### Comparación: Diccionarios vs BETO

| Aspecto | Diccionarios Actuales | BETO Semántico |
|---------|----------------------|-----------------|
| **Precisión** | ~34.7% detección | ~50-60% estimado |
| **Flexibilidad** | Lista fija | Comprensión contextual |
| **Mantenimiento** | Manual | Auto-aprendizaje |
| **Recursos** | Mínimos | Moderados (2-3GB RAM) |
| **Latencia** | <1ms | ~100-500ms |
| **Escalabilidad** | Limitada | Alta |

### Impacto Esperado en tu Sistema

#### Detección Mejorada
- Pasarías de ~50 casos detectados a ~80-100 casos por ciclo
- Reducción significativa de falsos negativos
- Mejor identificación de casos sutiles o implícitos

#### Búsqueda Inteligente
- Consultas más naturales: "niños que perdieron a su madre"
- Resultados más relevantes y contextuales
- Capacidad de encontrar patrones ocultos

#### Diferenciación Competitiva
- Tu sistema sería pionero en uso de IA avanzada para detección NNA
- Base sólida para publicaciones académicas
- Prototipo con capacidades de nivel investigación

Esta implementación transformaría tu sistema de un buen detector basado en reglas a un analizador inteligente con comprensión semántica real del lenguaje especializado en violencia de género y casos NNA.

