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
import hashlib
import re
from unicodedata import normalize

from app.models import db


# Estados oficiales del flujo de trabajo de la Asociación (ONG)
ESTADOS_SEGUIMIENTO_VALIDOS = (
    "detectado",              # Detectado automáticamente por el monitor
    "en_verificacion",        # En verificación de datos por la asociación
    "contacto_dif_fiscalia",  # En gestión/contacto con DIF, Fiscalía o familiares
    "en_acompanamiento",      # En acompañamiento jurídico/psicológico/social activo
    "archivado",              # Caso cerrado o descartado
)

_GENERIC_VICTIM_WORDS = {
    "no", "especificada", "especificado", "desconocida", "desconocido",
    "identificada", "identificado", "mujer", "madre", "joven", "victima",
    "fémina", "femina", "esposa", "pareja", "fallecida", "occisa", "una",
    "dos", "mujeres", "sin", "nombre", "anonima", "anónima", "n",
    "vendedora", "comerciante", "empresaria", "maestra", "conductora",
    "trabajadora", "estudiante", "enfermera", "doctora", "policia",
    "abuela", "hija", "hermana", "tia", "vecina", "ciudadana", "persona",
    "adulta", "menor", "nina", "anos", "edad", "llamada", "como", "quien",
}


def _slugify_key(text: str) -> str:
    """Normaliza un texto a ascii minúsculas separado por guiones para claves de expediente."""
    if not text or not isinstance(text, str):
        return ""
    norm = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    norm = re.sub(r"[^a-z0-9]+", "-", norm).strip("-")
    return norm


def _extract_primary_victim_slug(victimas_str: str) -> str:
    """
    Extrae el primer nombre propio significativo de la víctima mortal.
    Si el campo dice 'No especificada' o 'Mujer vendedora de 30 años', retorna cadena vacía.
    """
    if not victimas_str or not isinstance(victimas_str, str):
        return ""
    low = normalize("NFKD", victimas_str).encode("ascii", "ignore").decode("ascii").lower()
    if "no especificad" in low or "sin identificar" in low or "no identificad" in low:
        return ""

    # Buscar primero palabras con inicial mayúscula (nombres propios en español)
    tokens = re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñü]{2,}\b", victimas_str)
    if not tokens:
        tokens = re.findall(r"[a-záéíóúñü]{3,}", victimas_str.lower())

    meaningful = []
    for tok in tokens:
        clean_tok = normalize("NFKD", tok.lower()).encode("ascii", "ignore").decode("ascii")
        if clean_tok in _GENERIC_VICTIM_WORDS:
            continue
        meaningful.append(clean_tok)
        if len(meaningful) >= 2:
            break

    return "-".join(meaningful)


def generar_clave_expediente(
    investigacion_json: dict | None,
    titulo: str = "",
    fecha: datetime | str | None = None,
) -> str:
    """
    Genera una clave determinista (`clave_dedup`) para agrupar múltiples noticias
    que hablan del mismo caso de feminicidio con NNA en orfandad.

    Jerarquía de agrupación:
      1. Si hay Estado + Nombre de la víctima mortal (ej. 'Estado de México' + 'Cindy'):
         `vic:<estado>:<nombre_victima>` → Agrupa todas las notas de distintos medios
         sobre esa misma víctima en ese estado.
      2. Si no se publicó el nombre de la víctima pero hay Estado + Municipio específico:
         `mun:<estado>:<municipio>:nna-<ninos>:<YYYY-MM>`
      3. Fallback seguro basado en hash del título normalizado para no mezclar casos distintos.
    """
    inv = investigacion_json if isinstance(investigacion_json, dict) else {}

    estado_raw = str(inv.get("estado") or "").strip()
    municipio_raw = str(inv.get("municipio") or "").strip()
    ubicacion_raw = str(inv.get("ubicacion") or "").strip()

    # Si no vienen separados estado/municipio, intentar inferirlos de ubicacion ("Cuautitlán, Estado de México")
    if (not estado_raw or "no especificad" in estado_raw.lower()) and "," in ubicacion_raw:
        parts = [p.strip() for p in ubicacion_raw.split(",") if p.strip()]
        if len(parts) >= 2:
            municipio_raw = municipio_raw or parts[0]
            estado_raw = parts[-1]
    elif not estado_raw and ubicacion_raw and "no especificad" not in ubicacion_raw.lower():
        estado_raw = ubicacion_raw

    estado_slug = _slugify_key(estado_raw)
    if estado_slug in ("no-especificado", "no-especificada", "mexico", ""):
        estado_slug = "mx"

    municipio_slug = _slugify_key(municipio_raw)
    if municipio_slug in ("no-especificado", "no-especificada", estado_slug):
        municipio_slug = ""

    victim_slug = _extract_primary_victim_slug(str(inv.get("victimas") or ""))

    # Nivel 1: Víctima con nombre propio + Estado
    if victim_slug and estado_slug != "mx":
        return f"vic:{estado_slug}:{victim_slug}"[:120]
    if victim_slug and municipio_slug:
        return f"vic:{municipio_slug}:{victim_slug}"[:120]

    # Determinar año-mes para acotar casos sin nombre propio
    ym = datetime.now(timezone.utc).strftime("%Y-%m")
    if isinstance(fecha, datetime):
        ym = fecha.strftime("%Y-%m")
    elif isinstance(fecha, str) and len(fecha) >= 7 and re.match(r"^\d{4}-\d{2}", fecha):
        ym = fecha[:7]

    # Nivel 2: Estado + Municipio específico + número de NNA + mes
    if estado_slug != "mx" and municipio_slug:
        ninos_raw = str(inv.get("ninos_afectados") or "").strip()
        m_num = re.search(r"\d+", ninos_raw)
        ninos_tag = m_num.group(0) if m_num else "x"
        return f"mun:{estado_slug}:{municipio_slug}:nna-{ninos_tag}:{ym}"[:120]

    # Nivel 3: Fallback por hash de título limpio (sin el nombre del periódico tras ' - ')
    clean_title = re.sub(r"\s+[-|]\s+[^-|]+$", "", (titulo or "").strip())
    title_slug = _slugify_key(clean_title)
    digest = hashlib.md5(title_slug.encode("utf-8")).hexdigest()[:12]
    return f"nota:{estado_slug}:{digest}"[:120]


def _is_empty_or_unspecified(val: object) -> bool:
    """Retorna True si el valor está vacío o contiene un placeholder 'No especificada'."""
    if val is None:
        return True
    s = str(val).strip().lower()
    return (
        not s
        or s in ("0", "none", "null", "n/a")
        or "no especificad" in s
        or "sin especificar" in s
        or "desconocid" in s
    )


def consolidar_datos_expediente(actual: dict, nuevo: dict) -> dict:
    """
    Fusiona la información de una nueva noticia dentro de un expediente existente,
    reemplazando campos 'No especificada' con datos concretos cuando una nueva
    fuente periodística aporta más detalles (ej. edades, nombres, resguardo DIF).
    """
    resultado = dict(actual)
    campos_enriquecibles = (
        "ubicacion",
        "estado",
        "municipio",
        "victimas",
        "ninos_afectados",
        "edades",
        "situacion_actual",
        "medios_contacto",
        "cita_textual_evidencia",
    )
    for campo in campos_enriquecibles:
        val_actual = resultado.get(campo)
        val_nuevo = nuevo.get(campo)
        if _is_empty_or_unspecified(val_actual) and not _is_empty_or_unspecified(val_nuevo):
            resultado[campo] = val_nuevo
        elif (
            campo in ("situacion_actual", "edades", "victimas", "cita_textual_evidencia")
            and not _is_empty_or_unspecified(val_nuevo)
            and not _is_empty_or_unspecified(val_actual)
            and len(str(val_nuevo)) > len(str(val_actual)) + 5
        ):
            resultado[campo] = val_nuevo

    # Resumen: conservar el más completo
    res_actual = str(resultado.get("resumen") or "")
    res_nuevo = str(nuevo.get("resumen") or "")
    if (_is_empty_or_unspecified(res_actual) or "resumen preliminar" in res_actual.lower()) and not _is_empty_or_unspecified(res_nuevo):
        resultado["resumen"] = res_nuevo

    # Consolidar lista de fuentes únicas
    fuentes_actuales = list(resultado.get("fuentes") or [])
    for f in (nuevo.get("fuentes") or []):
        if f and f not in fuentes_actuales:
            fuentes_actuales.append(f)
    resultado["fuentes"] = fuentes_actuales

    return resultado


class ExpedienteCaso(db.Model):
    """
    Expediente consolidado de un caso de feminicidio con NNA en orfandad.

    Agrupa múltiples noticias de distintos medios que cubren el mismo evento
    y gestiona el flujo de seguimiento operativo de la Asociación (ONG).
    """

    __tablename__ = "expedientes_casos"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    folio = db.Column(db.String(50), unique=True, nullable=False, index=True)
    clave_dedup = db.Column(db.String(120), unique=True, nullable=False, index=True)

    # Datos estructurados del caso
    titulo_caso = db.Column(db.String(350), nullable=False)
    ubicacion = db.Column(db.String(200), default="No especificada")
    estado = db.Column(db.String(100), default="No especificado", index=True)
    municipio = db.Column(db.String(100), default="No especificado", index=True)
    victimas = db.Column(db.String(300), default="No especificada")
    ninos_afectados = db.Column(db.String(50), default="No especificado")
    edades = db.Column(db.String(150), default="No especificadas")
    situacion_actual = db.Column(db.String(300), default="No especificada")
    medios_contacto = db.Column(db.String(500), default="DIF / Fiscalía Estatal")
    cita_textual_evidencia = db.Column(db.Text, nullable=True)
    resumen = db.Column(db.Text, nullable=True)

    # Seguimiento operativo de la ONG
    estado_seguimiento = db.Column(
        db.String(40), default="detectado", nullable=False, index=True,
    )
    en_seguimiento = db.Column(db.Boolean, default=False, nullable=False, index=True)
    notas_seguimiento = db.Column(db.JSON, default=list)

    # Métricas y fuentes consolidadas
    num_noticias = db.Column(db.Integer, default=1, nullable=False)
    relevancia_maxima = db.Column(db.Float, default=0.0)
    clasificacion = db.Column(db.String(20), default="Alta", index=True)
    fuentes_json = db.Column(db.JSON, default=list)

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
    sesion_id = db.Column(
        db.Integer, db.ForeignKey("sesiones_busqueda.id"), nullable=True, index=True
    )

    def to_dict(self) -> dict:
        fuentes = self.fuentes_json or []
        fecha_iso = self.created_at.isoformat() if self.created_at else None
        inv_compat = {
            "expediente_id": self.id,
            "folio_expediente": self.folio,
            "ubicacion": self.ubicacion,
            "estado": self.estado,
            "municipio": self.municipio,
            "victimas": self.victimas,
            "ninos_afectados": self.ninos_afectados,
            "nna_afectados": self.ninos_afectados,
            "edades": self.edades,
            "edades_nna": self.edades,
            "situacion_actual": self.situacion_actual,
            "medios_contacto": self.medios_contacto,
            "cita_textual_evidencia": self.cita_textual_evidencia,
            "resumen": self.resumen,
            "fuentes": fuentes,
            "en_seguimiento": self.en_seguimiento,
            "estado_seguimiento": self.estado_seguimiento,
            "notas_seguimiento": self.notas_seguimiento or [],
        }
        return {
            "id": self.id,
            "expediente_id": self.id,
            "folio": self.folio,
            "clave_caso": self.folio,
            "clave_dedup": self.clave_dedup,
            "titulo_caso": self.titulo_caso,
            "titulo": self.titulo_caso,
            "ubicacion": self.ubicacion,
            "estado": self.estado,
            "municipio": self.municipio,
            "victimas": self.victimas,
            "ninos_afectados": self.ninos_afectados,
            "nna_afectados": self.ninos_afectados,
            "edades": self.edades,
            "edades_nna": self.edades,
            "situacion_actual": self.situacion_actual,
            "medios_contacto": self.medios_contacto,
            "cita_textual_evidencia": self.cita_textual_evidencia,
            "resumen": self.resumen,
            "estado_seguimiento": self.estado_seguimiento,
            "en_seguimiento": self.en_seguimiento,
            "notas_seguimiento": self.notas_seguimiento or [],
            "num_noticias": self.num_noticias,
            "num_fuentes": self.num_noticias,
            "relevancia_maxima": self.relevancia_maxima,
            "score_compuesto": self.relevancia_maxima,
            "clasificacion": self.clasificacion,
            "fuentes": fuentes,
            "fuentes_json": fuentes,
            "enlace": fuentes[0] if fuentes else "",
            "fecha": fecha_iso,
            "created_at": fecha_iso,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "sesion_id": self.sesion_id,
            "investigacion_json": inv_compat,
        }

    def __repr__(self):
        return f"<ExpedienteCaso {self.folio}: {self.titulo_caso[:50]}>"



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
    
    # Aislamiento de datos y vínculo a Expediente de Caso
    sesion_id = db.Column(
        db.Integer, db.ForeignKey('sesiones_busqueda.id'), nullable=True, index=True
    )
    expediente_id = db.Column(
        db.Integer,
        db.ForeignKey('expedientes_casos.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    # Relaciones
    expediente = db.relationship(
        "ExpedienteCaso", backref=db.backref("noticias", lazy="dynamic")
    )
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
            "sesion_id": self.sesion_id,
            "expediente_id": self.expediente_id,
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
    
    # Aislamiento de datos
    sesion_id = db.Column(
        db.Integer, db.ForeignKey('sesiones_busqueda.id'), nullable=True, index=True
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
