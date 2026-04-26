# src/database/models_noticias.py — Esquema relacional normalizado PostgreSQL
"""
OE-3: Migración de almacenamiento CSV a PostgreSQL.

Esquema relacional normalizado con 4 tablas principales:

  ┌──────────────┐    ┌──────────────────┐
  │   noticias    │───→│   detecciones    │
  │ (artículos)   │    │ (scores/labels)  │
  └──────┬───────┘    └──────────────────┘
         │
         │ M:1
  ┌──────┴───────┐    ┌──────────────────┐
  │   clusters    │    │    entidades     │
  │ (semánticos)  │    │ (NER extraídas)  │
  └──────────────┘    └──────────────────┘

Características PostgreSQL aprovechadas:
  - tsvector/tsquery para Full-Text Search (FTS) en español
  - GIN indices para búsqueda eficiente de texto
  - B-tree indices para consultas por fecha y score
  - Trigger automático para actualizar tsvector
  - Consultas con ranking ts_rank para relevancia FTS

Índices para rendimiento < 100ms:
  - idx_noticias_fts: GIN sobre tsvector (FTS)
  - idx_noticias_fecha: B-tree sobre fecha
  - idx_noticias_score: B-tree sobre score_compuesto DESC
  - idx_noticias_cluster: B-tree sobre cluster_id
  - idx_detecciones_nna: B-tree filtrado sobre menores_identificados
  - idx_entidades_tipo: B-tree sobre tipo de entidad
"""

from datetime import datetime, timezone

from app.models import db


class Noticia(db.Model):
    """
    Modelo de noticia almacenada en PostgreSQL.

    El campo `busqueda_fts` es un tsvector generado automáticamente
    a partir de título y contenido usando la configuración 'spanish'
    de PostgreSQL, que incluye:
      - Stemming (reducción a raíz: "feminicidios" → "feminicid")
      - Stop words en español
      - Normalización de acentos
      - Ranking por posición y frecuencia
    """

    __tablename__ = "noticias"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Contenido
    titulo = db.Column(db.String(500), nullable=False, index=True)
    contenido = db.Column(db.Text, nullable=False)
    enlace = db.Column(db.String(2000), unique=True, nullable=True)
    fuente = db.Column(db.String(300), nullable=True, index=True)
    fecha = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    # Scores de relevancia (eje dual)
    score_feminicidio = db.Column(db.Float, default=0.0)
    score_nna = db.Column(db.Float, default=0.0)
    score_compuesto = db.Column(db.Float, default=0.0, index=True)
    relevancia_final = db.Column(db.Float, default=0.0)
    clasificacion = db.Column(db.String(20), default="No relevante", index=True)
    clasificacion_final = db.Column(db.String(20), default="No relevante")

    # Score semántico (OE-1)
    score_semantico = db.Column(db.Float, nullable=True)
    modo_deteccion = db.Column(
        db.String(30), nullable=True,
        comment="zero_shot | finetuned | hybrid | heuristico",
    )

    # Clustering (OE-4)
    cluster_id = db.Column(
        db.Integer, db.ForeignKey("clusters_semanticos.id"), nullable=True
    )
    topic_id = db.Column(db.Integer, nullable=True)
    topic_description = db.Column(db.String(200), nullable=True)

    # Similitud / dedup
    max_similarity = db.Column(db.Float, default=0.0)
    content_hash = db.Column(db.String(64), nullable=True, index=True)

    # Metadatos scraping
    scrape_method = db.Column(
        db.String(30), nullable=True,
        comment="rss | html | sitemap | google_news_historical | wayback_machine",
    )
    menores_identificados = db.Column(db.String(5), default="No")
    batch_id = db.Column(
        db.String(50), nullable=True, index=True,
        comment="ID de la ejecución/búsqueda",
    )

    # Investigación profunda (LLM)
    investigacion_json = db.Column(db.JSON, nullable=True)

    # Full-Text Search vector (tsvector)
    # Se puebla via trigger SQL o al insertar
    # La columna real se crea con init_fts_schema() en repository.py
    # SQLAlchemy la ignora (no la manda en INSERT/UPDATE)

    # Timestamps
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relaciones
    cluster = db.relationship(
        "ClusterSemantico", backref=db.backref("noticias", lazy="dynamic")
    )
    deteccion = db.relationship(
        "Deteccion", backref="noticia", uselist=False, cascade="all, delete-orphan"
    )
    entidades = db.relationship(
        "Entidad", backref="noticia", lazy="dynamic", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "titulo": self.titulo,
            "contenido": self.contenido[:200] + "..." if self.contenido and len(self.contenido) > 200 else self.contenido,
            "enlace": self.enlace,
            "fuente": self.fuente,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "score_feminicidio": self.score_feminicidio,
            "score_nna": self.score_nna,
            "score_compuesto": self.score_compuesto,
            "relevancia_final": self.relevancia_final,
            "clasificacion": self.clasificacion,
            "clasificacion_final": self.clasificacion_final,
            "score_semantico": self.score_semantico,
            "cluster_id": self.cluster_id,
            "topic_id": self.topic_id,
            "menores_identificados": self.menores_identificados,
            "scrape_method": self.scrape_method,
            "batch_id": self.batch_id,
            "investigacion_json": self.investigacion_json,
        }

    def __repr__(self):
        return f"<Noticia {self.id}: {self.titulo[:50]}>"


class Deteccion(db.Model):
    """
    Resultado detallado de la detección para cada noticia.

    Almacena tanto el resultado heurístico como el semántico
    para auditoría y comparación de rendimiento.
    """

    __tablename__ = "detecciones"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    noticia_id = db.Column(
        db.Integer, db.ForeignKey("noticias.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    # Detección heurística (sistema actual)
    score_heuristico = db.Column(db.Float, nullable=True)
    clasificacion_heuristica = db.Column(db.String(20), nullable=True)
    keywords_feminicidio = db.Column(db.JSON, nullable=True)
    keywords_nna = db.Column(db.JSON, nullable=True)

    # Detección semántica (OE-1 BETO)
    score_semantico = db.Column(db.Float, nullable=True)
    confianza_semantica = db.Column(db.String(10), nullable=True)
    modo_semantico = db.Column(db.String(20), nullable=True)

    # Resultado híbrido
    score_hibrido = db.Column(db.Float, nullable=True)
    alpha_usado = db.Column(db.Float, nullable=True)
    clasificacion_hibrida = db.Column(db.String(20), nullable=True)

    # NNA
    menores_identificados = db.Column(db.Boolean, default=False)
    num_menores_mencionados = db.Column(db.Integer, default=0)
    edades_mencionadas = db.Column(db.JSON, nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<Deteccion noticia={self.noticia_id}>"


class ClusterSemantico(db.Model):
    """
    Cluster semántico generado por BERTopic (OE-4).

    Cada cluster tiene:
      - Etiqueta semántica generada automáticamente
      - Términos representativos (c-TF-IDF)
      - Número de documentos
      - Score de cohesión interna
    """

    __tablename__ = "clusters_semanticos"

    id = db.Column(db.Integer, primary_key=True)
    etiqueta = db.Column(db.String(200), nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    terminos_principales = db.Column(db.JSON, nullable=True)
    num_documentos = db.Column(db.Integer, default=0)
    cohesion = db.Column(db.Float, nullable=True)
    es_outlier = db.Column(
        db.Boolean, default=False,
        comment="True si es el cluster de outliers (-1 en HDBSCAN)",
    )

    # Metadatos del modelo
    modelo_version = db.Column(db.String(50), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "etiqueta": self.etiqueta,
            "descripcion": self.descripcion,
            "terminos_principales": self.terminos_principales,
            "num_documentos": self.num_documentos,
            "cohesion": self.cohesion,
            "es_outlier": self.es_outlier,
        }

    def __repr__(self):
        return f"<Cluster {self.id}: {self.etiqueta}>"


class Entidad(db.Model):
    """
    Entidad nombrada extraída de una noticia mediante NER.

    Tipos de entidades relevantes:
      - PER: Personas (víctimas, agresores)
      - LOC: Ubicaciones (estados, ciudades)
      - ORG: Organizaciones (DIF, fiscalía)
      - MISC: Otras (leyes, programas)
    """

    __tablename__ = "entidades"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    noticia_id = db.Column(
        db.Integer, db.ForeignKey("noticias.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    texto = db.Column(db.String(200), nullable=False)
    tipo = db.Column(
        db.String(20), nullable=False, index=True,
        comment="PER | LOC | ORG | MISC",
    )
    posicion_inicio = db.Column(db.Integer, nullable=True)
    posicion_fin = db.Column(db.Integer, nullable=True)
    confianza = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return f"<Entidad {self.tipo}: {self.texto}>"
