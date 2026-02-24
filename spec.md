# Proyecto: secop-monitor-mvp1
MVP 1 = Monitoreo de procesos/convocatorias por keywords + scoring + dedupe + alertas + auditoría.

## 0) Objetivo
Construir un sistema que, de forma periódica, recolecte procesos de SECOP (o una fuente compatible), evalúe relevancia contra consultas configurables (keywords/frases/filtros), deduzca duplicados, persista resultados y envíe notificaciones de nuevos hallazgos con explicación (“por qué matcheó”).

## 1) Restricciones y supuestos
- Python 3.11+
- Persistencia: SQLite por defecto (archivo local). Debe poder migrarse a Postgres sin reescribir lógica (usar SQLAlchemy).
- Scheduler: ejecución por CLI (para cron/GitHub Actions). NO construir UI en MVP.
- Fuente SECOP: implementar como “collector” pluggable:
  - Implementar `FixtureCollector` que lee JSON local para desarrollo/testing.
  - Dejar interfaz lista para `SecopApiCollector` (sin asumir endpoints exactos). Si se provee un endpoint luego, se implementa el adaptador.
- Canal de notificación: implementar 1 (Slack webhook recomendado) + modo “stdout” (imprime alertas).

## 2) Alcance (IN)
- Configuración declarativa en `config.yaml`
- Ingesta de items de procesos (mínimo: id, title, description, entity, dates, url, budget si existe)
- Normalización de texto (lowercase, quitar acentos, colapsar espacios)
- Matching por reglas (keywords_any, keywords_all, keywords_not, phrases) con scoring 0..1
- Deduplicación:
  - primaria: por `process_id` (idempotencia)
  - secundaria: fingerprint (title+entity+published_at) con similitud simple (ratio) para detectar re-publicaciones
- Persistencia: tabla opportunities + runs
- Notificación: enviar solo nuevos items por arriba de threshold con explicación
- Auditoría: registrar cada ejecución (run) con conteos y errores

## 3) Fuera de alcance (OUT)
- Descarga y análisis de pliegos (MVP 2)
- Embeddings/vector DB
- UI web

## 4) Entradas: Configuración (config.yaml)
Ejemplo de estructura requerida:

app:
  db_url: "sqlite:///./secop.db"
  timezone: "America/Bogota"
  notifier: "slack"   # slack|stdout
  score_threshold: 0.65
  max_items_per_run: 500

source:
  collector: "fixture" # fixture|secop_api
  fixture_path: "./data/fixtures/secop_items.json"
  # secop_api:
  #   base_url: ""
  #   auth: { ... }

filters:
  published_within_days: 14
  min_budget: 0
  entity_allowlist: []
  entity_blocklist: []
  location_allowlist: []
  modality_allowlist: []

queries:
  - name: "IA-LLM-RAG"
    keywords_any: ["inteligencia artificial", "IA", "LLM", "chatbot", "RAG", "modelo de lenguaje"]
    keywords_all: []
    keywords_not: ["mantenimiento", "aseo", "vigilancia"]
    phrases: ["modelo de lenguaje", "retrieval augmented generation"]
    synonyms:
      "IA": ["inteligencia artificial"]
  - name: "Analítica de Datos"
    keywords_any: ["analítica", "data warehouse", "bi", "etl", "lakehouse"]
    keywords_all: []
    keywords_not: []
    phrases: []
    synonyms: {}

notifications:
  slack:
    webhook_env_var: "SLACK_WEBHOOK_URL"
    username: "secop-monitor"
    max_alerts_per_run: 20

## 5) Modelo de datos (SQLAlchemy)
### opportunities
- id (PK int)
- source_system (str)  # "SECOP"
- process_id (str, unique index)
- title (str)
- entity_name (str)
- description (str)
- published_at (datetime, nullable)
- closing_at (datetime, nullable)
- budget (float, nullable)
- location (str, nullable)
- url (str)
- query_match (str)     # nombre de query que disparó (puede ser múltiple; para MVP guardar la mejor)
- score (float)
- match_explain (json str) # hits: phrases, keywords_all, keywords_any, keywords_not
- status (str)          # new|notified|dismissed|saved
- fingerprint (str)     # para dedupe secundario
- created_at (datetime)
- updated_at (datetime)

### runs
- id (PK int)
- started_at (datetime)
- finished_at (datetime)
- collector (str)
- items_collected (int)
- items_after_filters (int)
- items_new (int)
- items_notified (int)
- errors (json str, nullable)

## 6) Arquitectura / Módulos
- src/secop_monitor/
  - main.py                # CLI entrypoints
  - config.py              # cargar/validar config.yaml (pydantic)
  - collectors/
    - base.py              # interface Collector
    - fixture.py           # FixtureCollector
    - secop_api.py         # stub con TODO (raise NotImplementedError)
  - normalize.py           # normalización texto
  - matcher.py             # lógica de match + scoring + explicación
  - dedupe.py              # fingerprint + similitud secundaria
  - repository.py          # CRUD DB (SQLAlchemy)
  - notifier/
    - base.py
    - stdout.py
    - slack.py
  - logging_setup.py
  - models.py              # SQLAlchemy models
  - schemas.py             # dataclasses/pydantic para items
- tests/
  - test_normalize.py
  - test_matcher.py
  - test_dedupe.py
  - test_pipeline_fixture.py

## 7) Contratos de interfaces
### Collector
- method: `collect(since: datetime, limit: int) -> list[RawItem]`
RawItem debe incluir al menos:
- process_id, title, description, entity_name, published_at, closing_at, budget, location, url

### Matcher
- `match(item: NormalizedItem, query: QueryConfig) -> MatchResult`
MatchResult:
- score: float
- explain: dict
- matched: bool (score >= threshold y pasa reglas mínimas)

## 8) Lógica de scoring (determinista)
Requerimiento:
- score en [0, 1]
- fórmula base (ajustable):
  - phrases: +0.35 total (distribuido por #phrases encontradas)
  - keywords_all: +0.35 si todos aparecen (o proporcional si no hay)
  - keywords_any: +0.30 proporcional por hits / total
  - keywords_not: si aparece cualquiera => matched=False (o penalización fuerte); para MVP: hard exclude
- Guardar hits exactos en `match_explain`.

## 9) Pipeline por ejecución
1) Load config
2) Determine `since = now - published_within_days`
3) Collector.collect(since, max_items_per_run)
4) Normalize + apply filters (budget/entity/location/modality si el item trae el campo)
5) For each item:
   - compute fingerprint
   - if process_id ya existe: skip
   - else: dedupe secundario (si fingerprint muy parecido a uno reciente, marcar status=dismissed o keep con flag; MVP: keep pero no notificar)
   - compute best query_match (máximo score)
   - persist opportunity con status=new
6) Notifier: seleccionar status=new con score>=threshold, limitar a max_alerts_per_run
7) Enviar mensajes y marcar status=notified
8) Registrar run con conteos

## 10) CLI
- `python -m secop_monitor run --config ./config.yaml`
- `python -m secop_monitor init-db --config ./config.yaml`
- `python -m secop_monitor show-latest --n 20`

## 11) Observabilidad
- Logging JSON a stdout
- Cada run debe loggear:
  - since, collected, after_filters, new, notified, duration_ms
  - top 5 alerts (process_id, score, query)

## 12) Criterios de aceptación (DoD)
Funcional:
- [ ] `init-db` crea DB y tablas
- [ ] `run` con FixtureCollector ingiere items y guarda oportunidades
- [ ] Matching produce score y explicación consistente
- [ ] Dedup primario por process_id funciona (idempotente)
- [ ] Notifier (stdout o slack) envía solo los nuevos por umbral
- [ ] Runs quedan auditados con conteos

Calidad:
- [ ] Tests unitarios pasan (`pytest`)
- [ ] README con: setup, config, ejecución local, ejemplo de output
- [ ] Linter/format (ruff/black) configurado
- [ ] Type hints y mypy básico (opcional pero recomendado)

## 13) Datos de fixture
- `data/fixtures/secop_items.json` con ~50 items variados:
  - algunos relevantes, otros ruido
  - incluir duplicados con títulos similares
- `data/fixtures/labels.csv` opcional para evaluar precision@N (no obligatorio en MVP, pero dejar preparado)

## 14) Entregables
- Repo completo + instrucciones
- Ejemplo de ejecución y salida de alertas
- Captura/log de un run exitoso

## 15) Data Source Contract
1) Fuente primaria

Plataforma: datos.gov.co

Dataset específico: SECOP II – Procesos de Contratación (y/o SECOP I si decides incluirlo)

Tipo API: Socrata / OData

Formato: JSON

Actualización esperada: diaria

2) Endpoint base

URL base del dataset

Parámetros:

$limit

$offset

$where

$order

3) Campos requeridos (mapa obligatorio)

Definir explícitamente:

Campo dataset	Campo interno
id_proceso	process_id
nombre_proceso	title
entidad	entity_name
descripcion	description
fecha_publicacion	published_at
fecha_cierre	closing_at
valor	budget
url_proceso	url

Si algún campo es opcional, marcarlo como nullable.

4) Estrategia de paginación

$limit=1000

Loop con $offset

Stop condition: batch < limit

5) Estrategia incremental

Filtro por fecha_publicacion >= now - X días

Guardar last_run_timestamp

Permitir re-ejecución idempotente

6) Rate limit y resiliencia

Retry exponencial

Timeout

Manejo de HTTP != 200

Registro de errores en tabla runs

7) Validación de integridad

Si campos críticos faltan → descartar item

Loggear % de registros incompletos

## 16 Time handling

All datetimes are stored in UTC.

Incoming naive datetimes are localized to app.timezone then converted to UTC.

Internal comparisons use UTC.