# src/analysis/topic_analyzer.py
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from gensim import corpora, models
from gensim.models import LdaModel
import gensim
from collections import defaultdict

class TopicAnalyzer:
    """Clase para análisis de tópicos y similitud de documentos."""
    
    def __init__(self):
        self.lda_model = None
        self.dictionary = None
        self.corpus = None
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        self.processed_texts = []
    
    def preprocess_for_lda(self, texts: List[str]) -> List[List[str]]:
        """Preprocesa textos para LDA dividiendo en tokens."""
        processed = []
        for text in texts:
            if not isinstance(text, str):
                text = str(text)
            # Tokenización simple (puedes mejorarla con spaCy)
            tokens = text.lower().split()
            # Filtrar tokens muy cortos
            tokens = [token for token in tokens if len(token) > 2]
            processed.append(tokens)
        return processed
    
    def train_lda_model(self, texts: List[str], num_topics: int = 10, 
                       passes: int = 20, alpha: str = 'auto') -> Dict:
        """
        Entrena un modelo LDA para descubrir tópicos en los textos.
        
        Args:
            texts: Lista de textos a analizar
            num_topics: Número de tópicos a descubrir
            passes: Número de pasadas del algoritmo
            alpha: Parámetro alpha para LDA
            
        Returns:
            Diccionario con información del modelo y tópicos
        """
        # Preprocesar textos
        self.processed_texts = self.preprocess_for_lda(texts)
        
        # Crear diccionario y corpus
        self.dictionary = corpora.Dictionary(self.processed_texts)
        # Filtrar palabras muy frecuentes o muy raras
        self.dictionary.filter_extremes(no_below=2, no_above=0.8)
        
        # Crear corpus (representación vectorial)
        self.corpus = [self.dictionary.doc2bow(text) for text in self.processed_texts]
        
        # Entrenar modelo LDA
        self.lda_model = LdaModel(
            corpus=self.corpus,
            id2word=self.dictionary,
            num_topics=num_topics,
            random_state=42,
            passes=passes,
            alpha=alpha,
            per_word_topics=True
        )
        
        # Extraer tópicos
        topics_info = self._extract_topics_info(num_topics)
        
        return {
            'model': self.lda_model,
            'topics': topics_info,
            'coherence': self._calculate_coherence(),
            'num_topics': num_topics
        }
    
    def _extract_topics_info(self, num_topics: int) -> List[Dict]:
        """Extrae información legible de los tópicos."""
        topics_info = []
        for topic_id in range(num_topics):
            # Obtener las palabras más importantes del tópico
            topic_words = self.lda_model.show_topic(topic_id, topn=10)
            words = [word for word, prob in topic_words]
            probabilities = [prob for word, prob in topic_words]
            
            topics_info.append({
                'topic_id': topic_id,
                'words': words,
                'probabilities': probabilities,
                'description': ' '.join(words[:5])  # Descripción simple
            })
        
        return topics_info
    
    def _calculate_coherence(self) -> float:
        """Calcula la coherencia del modelo LDA."""
        try:
            from gensim.models import CoherenceModel
            coherence_model = CoherenceModel(
                model=self.lda_model,
                texts=self.processed_texts,
                dictionary=self.dictionary,
                coherence='c_v'
            )
            return coherence_model.get_coherence()
        except Exception as e:
            print(f"Error calculando coherencia: {e}")
            return 0.0
    
    def assign_topics_to_documents(self, texts: List[str]) -> List[Dict]:
        """
        Asigna tópicos a documentos nuevos o existentes.
        
        Returns:
            Lista de diccionarios con topic_id y probabilidad para cada documento
        """
        if not self.lda_model or not self.dictionary:
            raise ValueError("Debe entrenar el modelo LDA primero")
        
        results = []
        processed_texts = self.preprocess_for_lda(texts)
        
        for i, tokens in enumerate(processed_texts):
            # Convertir a representación bow
            bow = self.dictionary.doc2bow(tokens)
            
            # Obtener distribución de tópicos para este documento
            topic_probs = self.lda_model.get_document_topics(bow)
            
            if topic_probs:
                # Tópico dominante
                dominant_topic = max(topic_probs, key=lambda x: x[1])
                topic_id, probability = dominant_topic
                
                results.append({
                    'doc_index': i,
                    'dominant_topic': topic_id,
                    'probability': probability,
                    'all_topics': dict(topic_probs)
                })
            else:
                results.append({
                    'doc_index': i,
                    'dominant_topic': -1,
                    'probability': 0.0,
                    'all_topics': {}
                })
        
        return results

class SimilarityAnalyzer:
    """Clase para análisis de similitud entre documentos."""
    
    def __init__(self):
        self.vectorizer = None
        self.tfidf_matrix = None
        self.documents = []
    
    def fit_tfidf(self, documents: List[str], max_features: int = 5000) -> None:
        """
        Ajusta el vectorizador TF-IDF con los documentos.
        
        Args:
            documents: Lista de documentos de texto
            max_features: Número máximo de características
        """
        self.documents = documents
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            stop_words=None,  # Puedes agregar stop words en español
            lowercase=True,
            ngram_range=(1, 2)  # Incluye bigramas
        )
        
        self.tfidf_matrix = self.vectorizer.fit_transform(documents)
    
    def calculate_similarity_matrix(self) -> np.ndarray:
        """
        Calcula la matriz de similitud coseno entre todos los documentos.
        
        Returns:
            Matriz de similitud (n_docs x n_docs)
        """
        if self.tfidf_matrix is None:
            raise ValueError("Debe ajustar TF-IDF primero con fit_tfidf()")
        
        return cosine_similarity(self.tfidf_matrix)
    
    def find_similar_documents(self, query_text: str, top_k: int = 5) -> List[Dict]:
        """
        Encuentra los documentos más similares a un texto de consulta.
        
        Args:
            query_text: Texto de consulta
            top_k: Número de documentos similares a devolver
            
        Returns:
            Lista de diccionarios con índice, similitud y texto
        """
        if self.vectorizer is None:
            raise ValueError("Debe ajustar TF-IDF primero con fit_tfidf()")
        
        # Vectorizar la consulta
        query_vector = self.vectorizer.transform([query_text])
        
        # Calcular similitudes
        similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
        
        # Obtener los top_k más similares
        top_indices = similarities.argsort()[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if similarities[idx] > 0:  # Solo incluir si hay alguna similitud
                results.append({
                    'index': int(idx),
                    'similarity': float(similarities[idx]),
                    'text': self.documents[idx][:200] + "..." if len(self.documents[idx]) > 200 else self.documents[idx]
                })
        
        return results
    
    def find_document_similarities(self, doc_index: int, top_k: int = 5) -> List[Dict]:
        """
        Encuentra documentos similares a un documento específico por su índice.
        
        Args:
            doc_index: Índice del documento de referencia
            top_k: Número de documentos similares a devolver
            
        Returns:
            Lista de documentos similares
        """
        if self.tfidf_matrix is None:
            raise ValueError("Debe ajustar TF-IDF primero con fit_tfidf()")
        
        if doc_index >= len(self.documents):
            raise ValueError(f"Índice {doc_index} fuera de rango")
        
        # Calcular similitudes con todos los documentos
        similarities = cosine_similarity(
            self.tfidf_matrix[doc_index:doc_index+1],
            self.tfidf_matrix
        ).flatten()
        
        # Obtener los top_k más similares (excluyendo el mismo documento)
        top_indices = similarities.argsort()[::-1][1:top_k+1]
        
        results = []
        for idx in top_indices:
            if similarities[idx] > 0.1:  # Umbral mínimo de similitud
                results.append({
                    'index': int(idx),
                    'similarity': float(similarities[idx]),
                    'text': self.documents[idx][:200] + "..." if len(self.documents[idx]) > 200 else self.documents[idx]
                })
        
        return results

# Funciones de utilidad para integrar con el DataFrame existente

def analyze_topics_in_dataframe(df: pd.DataFrame, text_column: str = 'contenido_limpio',
                               num_topics: int = 8) -> Tuple[pd.DataFrame, Dict]:
    """
    Analiza tópicos en un DataFrame y agrega información de tópicos.
    
    Args:
        df: DataFrame con noticias
        text_column: Nombre de la columna con texto
        num_topics: Número de tópicos a descubrir
        
    Returns:
        DataFrame con columnas de tópicos y diccionario con información del modelo
    """
    if text_column not in df.columns:
        raise ValueError(f"Columna '{text_column}' no encontrada en el DataFrame")
    
    # Inicializar analizador
    topic_analyzer = TopicAnalyzer()
    
    # Entrenar modelo
    texts = df[text_column].fillna('').astype(str).tolist()
    model_info = topic_analyzer.train_lda_model(texts, num_topics=num_topics)
    
    # Asignar tópicos a documentos
    topic_assignments = topic_analyzer.assign_topics_to_documents(texts)
    
    # Agregar información al DataFrame
    df_result = df.copy()
    df_result['topic_id'] = [assignment['dominant_topic'] for assignment in topic_assignments]
    df_result['topic_probability'] = [assignment['probability'] for assignment in topic_assignments]
    
    # Agregar descripción del tópico
    topic_descriptions = {topic['topic_id']: topic['description'] 
                         for topic in model_info['topics']}
    df_result['topic_description'] = df_result['topic_id'].map(topic_descriptions)
    
    return df_result, model_info

def calculate_document_similarities(df: pd.DataFrame, text_column: str = 'contenido_limpio') -> pd.DataFrame:
    """
    Calcula similitudes entre documentos y agrega información al DataFrame.
    
    Args:
        df: DataFrame con noticias
        text_column: Nombre de la columna con texto
        
    Returns:
        DataFrame con información de similitudes
    """
    if text_column not in df.columns:
        raise ValueError(f"Columna '{text_column}' no encontrada en el DataFrame")
    
    # Inicializar analizador de similitud
    similarity_analyzer = SimilarityAnalyzer()
    
    # Ajustar TF-IDF
    texts = df[text_column].fillna('').astype(str).tolist()
    similarity_analyzer.fit_tfidf(texts)
    
    # Calcular matriz de similitud
    similarity_matrix = similarity_analyzer.calculate_similarity_matrix()
    
    # Agregar información al DataFrame
    df_result = df.copy()
    
    # Para cada documento, encontrar el más similar
    for i in range(len(df_result)):
        similarities = similarity_matrix[i]
        # Encontrar el índice del documento más similar (excluyendo el mismo)
        similarities[i] = 0  # Excluir el mismo documento
        most_similar_idx = similarities.argmax()
        max_similarity = similarities[most_similar_idx]
        
        df_result.loc[i, 'most_similar_doc_idx'] = most_similar_idx
        df_result.loc[i, 'max_similarity'] = max_similarity
    
    return df_result