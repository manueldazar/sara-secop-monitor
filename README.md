# SARA (Sistema de Análisis de Regulación Automatizado) - MVP 1

SARA es un motor determinista y escalable de **extracción, matcheo y alerta temprana** construido para encontrar oportunidades en el SECOP (Sistema Electrónico de Contratación Pública) según especificaciones altamente customizables (queries de negocio). 

Está diseñado bajo una filosofía de ligereza, con un motor de scoring explícito (*explainable*), persistencia agnóstica a SQLite y preparado para escalar a Postgres.

### Por qué este proyecto es importante

La monitorización de la contratación pública requiere:

- Filtrado determinista
- Puntuación explicable
- Ingesta idempotente
- Garantías transaccionales seguras
- Deduplicación secundaria para republicaciones

SARA resuelve estos desafíos de ingeniería sin depender de LLM.

![Tests](https://github.com/manueldazar/sara-secop-monitor/actions/workflows/tests.yml/badge.svg)

## 🏗 Arquitectura del Sistema (ETL)
El ciclo de vida de un documento SECOP dentro de SARA fluye linealmente garantizando idempotencia en cada paso.

```mermaid
flowchart TD
    A[Collector (SECOP API / Fixture)] -->|RawItems| B[Normalize]
    B -->|Title / Desc Normalizados\n+ SHA-256 Fingerprint| C[Matcher Engine]
    C -->|Score + Explainability JSON| D[Dedupe Secundario]
    D -->|Status: new / dismissed / saved| E[(Repository / SQLite)]
    E -->|Pendientes>Threshold| F[Notifier (Slack / Stdout)]
```

### Decisiones Técnicas Clave
Demostrando un criterio de ingeniería robusto, SARA se asienta sobre las siguientes decisiones implementadas en este MVP:

- **Deterministic Scoring `(0.35/0.35/0.30)`**: El sistema de *weights* penaliza ausencias pero no infla hiper-frecuencias (Cap estadístico en *Keywords Any*). No se requiere inferencia LLM (reduce costos a cero).
- **Hard Exclude Policy**: Las `keywords_not` apagan el `Score = 0.0` instantáneamente ahorrando notificaciones ruidosas (ejemplo: "mantenimiento" en consultorías).
- **Secondary Dedupe via `Similarity > 0.90`**: Previene el fenómeno de "republicación con diferente ID" de la plataforma origen comparando la similitud estructural del título anterior normalizado (además de usar el Fingerprint base).
- **UTC Storage Strategy**: Absolutamente todas las fechas leídas (ingenuas o foráneas) se localizan a la Timezone de configuración y se mutan a `datetime.timezone.utc` antes de persistir, evitando *drift* y problemas de consultas cruzadas internacionales.
- **Single-run Audit Invariant & Idempotent Guarantee**: Mitigación del *N+1 Query Issue* al filtrar process IDs en memoria temporal pre-inserción. Si el *batch run* falla (ej: Red), el DB Transaction hace rollback preservando el estatus de error nativo en el mismo `run_id` (`[errors]`).

---

## 🚀 Setup Rápido (Local)

**1) Clona el repositorio e instala requerimientos (Make):**
```bash
make setup
```

**2) Inicializa la Base de Datos (SQLite) con las tablas:**
```bash
make init-db
```

**3) Corre un proceso de orquestación ETL completo:**
```bash
make run
```

### Resultados y Logs (Ejemplo Real)
Cuando SARA pesca una oportunidad y esta supera el Score configurado, te devuelve el siguiente *Explain* en consola de por qué lo seleccionó:

```text
2026-02-24 16:54:16,074 [INFO]  --- [STDOUT NOTIFIER] 1 NUEVAS ALERTAS --- 

[0.82] Adquisición de software de inteligencia artificial para validación de datos
  Query: IA-LLM-RAG
  Entidad: Ministerio TIC
  URL: https://secop.gov.co/001
  Explain: {'query_name': 'IA-LLM-RAG', 'phrases_hit': ['modelo de lenguaje'], 'keywords_all_hit': [], 'keywords_all_miss': [], 'keywords_any_hit': ['inteligencia artificial', 'ia', 'llm', 'chatbot', 'modelo de lenguaje'], 'excluded_by': [], 'component_scores': {'phrases': 0.175, 'all': 0.35, 'any': 0.3}}

2026-02-24 16:54:16,087 [INFO] Pipeline finalizado satisfactoriamente.
```

---

## 🧠 Estructura de Queries

La magia de SARA se controla en tu archivo `config.yaml`.
Puedes agregar docenas de *queries* especializadas. SARA calculará contra todas y tomará el Match que brinde mejor Score (límite 1.0 por oportunidad).

```yaml
queries:
  - name: "IA-LLM-RAG"
    # (Weight 0.35) Busca encontrar todas las frases definidas.
    phrases: ["modelo de lenguaje", "retrieval augmented"]
    
    # (Weight 0.35) Acierta SOLO si todos estos terminos aparecen (Penaliza si fallas).
    keywords_all: ["software"]
    
    # (Weight 0.30) Acierta si alguna aparece (Cap en 3 hits p/max score).
    keywords_any: ["inteligencia artificial", "IA"]
    
    # (HARD EXCLUDE). Si cualquiera de estas aparece, Score = 0 instantáneo.
    keywords_not: ["mantenimiento", "aseo"]
    
    # Expansión SIMÉTRICA (No importa cual se use, se buscan todas incluyendose a sí misma y cruzando keys)
    synonyms:
      "ia": ["inteligencia artificial"]
```

## Limitaciones de esta Versión

- **Pliegos Externos**: El proceso no descarga aún el contenido de los links del SECOP para leer documentos anexos; solo trabaja con `title` y `description`.
- **Actualización Fija**: SARA corre exclusivamente por batch (demanda CLI), por tanto depende idealmente de un sistema CronJob ó GitHub Actions corriendo todos los días a media noche.
