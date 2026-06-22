# Toolmape — noticias y macroeconomía para oro en soles

El sistema recolecta titulares económicos y mineros, los clasifica con un modelo local de Ollama
(o, opcionalmente, OpenAI) y los complementa con
series macroeconómicas oficiales de FRED. Ambos pipelines producen señales diarias que se unen con
los precios de mercado y pueden publicarse en Supabase.

El objetivo de mercado es:

```text
precio_oro_soles_gramo = (precio_oro_usd_oz / 31.1035) * tipo_cambio_usd_pen
```

## Instalación

Requiere Python 3.11 o superior.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` a `.env` y complete solo las credenciales que vaya a usar:

```dotenv
# Opcional: solo si NEWS_LLM_PROVIDER=openai
OPENAI_API_KEY=
FRED_API_KEY=...
SUPABASE_URL=https://....supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
NEWS_PIPELINE_MODE=local
MACRO_PIPELINE_MODE=local
NEWS_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:latest
NEWS_MARKET_PRICES_PATH=data/market/market_prices.csv
```

Nunca exponga `SUPABASE_SERVICE_ROLE_KEY` en frontend, repositorios o logs. Con Ollama no necesita
una clave de OpenAI ni presupuesto por noticia.

## Comandos

```bash
python main.py news scrape
python main.py news enrich
python main.py news label
python main.py news features
python main.py news publish
python main.py news all
```

Pipeline FRED:

```bash
python main.py macro fred-download
python main.py macro fred-features
python main.py macro fred-publish
python main.py macro fred-all
```

Pipeline integrado:

```bash
python main.py all
```

Este último actualiza FRED, ejecuta noticias, vuelve a generar las features macro y construye el
dataset combinado. Si existe el pipeline de mercado configurado, el orden lógico resultante es
mercado + macro FRED + noticias. El entrenamiento de modelos no se ejecuta automáticamente porque
no forma parte aún de este repositorio.

`news all` intenta todas las etapas. En modo local no publica. Si falta una clave de OpenAI o el
archivo de mercado, registra el problema y continúa con las etapas que sí pueden ejecutarse.

También puede sobrescribirse el modo:

```bash
python main.py news all --mode local
python main.py news publish --mode supabase
```

## Configuración

- `config/news_sources.yaml`: URL, idioma, confiabilidad, frecuencia, selectores y fallbacks.
- `config/news_pipeline.yaml`: modelo GPT, timeouts, rutas y umbrales.
- `config/macro_fred.yaml`: series FRED, fechas, ventana incremental, modo y rutas.

Los umbrales predeterminados de dirección son ±0.3 %. Las clases de impacto se separan en 0.3 %,
0.7 %, 1.5 % y 2.5 %. Los valores viven en YAML y no están fijados dentro de la lógica.

## Artefactos locales

- `data/news/raw/`: resultados normalizados de cada extracción.
- `data/news/processed/latest.jsonl`: noticias únicas acumuladas.
- `data/news/enriched/latest.jsonl`: estado y clasificación GPT.
- `data/news/labeled/latest.jsonl`: retornos y labels 1d/3d.
- `data/news/features/daily_news_features.csv`: features agregadas por fecha.
- `logs/news/news_pipeline_runs.jsonl`: auditoría de cada etapa.

FRED genera:

- `data/macro/raw/{SERIE}.csv`: histórico raw conservando fechas de tiempo real.
- `data/macro/processed/fred_macro_dataset.csv`: niveles alineados diariamente.
- `data/macro/processed/daily_macro_features.csv`: features listas para modelado.
- `data/model/toolmape_features.csv`: unión por fecha de mercado, macro y noticias.
- `logs/macro/fred_pipeline_runs.jsonl`: auditoría de descargas y procesamiento.
- `reports/macro/fred_macro_report.md`: cobertura, faltantes y limitaciones.

Cada archivo de corrida usa un UUID. Los snapshots `latest` se actualizan por clave estable.

## Enriquecimiento local con Ollama

La configuración predeterminada usa `llama3:latest`, instalado localmente:

```bash
ollama list
ollama serve
python main.py news enrich
```

Ollama escucha normalmente en `http://localhost:11434`. El clasificador envía el JSON Schema
generado por Pydantic a `/api/chat`, usa temperatura 0 y valida nuevamente la respuesta antes de
guardarla. Si el servicio no está activo, la noticia queda `pending` para reintento.

Para usar OpenAI de forma opcional:

```dotenv
NEWS_LLM_PROVIDER=openai
OPENAI_API_KEY=...
```

Ambos proveedores usan salida estructurada basada en un modelo Pydantic estricto. No se aceptan
campos extra. El prompt limita el análisis al título, resumen, fuente, fecha y categoría
recibidos, sin navegación ni datos inventados. Una llamada fallida queda en estado `pending` para
ser reintentada en la próxima ejecución.

El proveedor, modelo, timeout, semilla y temperatura se definen en `config/news_pipeline.yaml`.

### Automatización local

GitHub Actions no puede conectarse al Ollama de su PC. Para mantener el procesamiento realmente
local, use el Programador de tareas de Windows o un runner self-hosted que tenga Ollama y el modelo
instalados. Instalar y descargar 4.7 GB en un runner nuevo cada hora no es recomendable.

## Diccionario de métricas

Todas las variables calculadas, fórmulas, unidades, ventanas, umbrales y limitaciones están
documentadas en [docs/METRICS.md](docs/METRICS.md). La regla del proyecto es actualizar ese
documento cada vez que se agregue o modifique una métrica.

La comparación de modelos locales, tiempos medidos y opciones de automatización está en
[docs/LOCAL_AI.md](docs/LOCAL_AI.md).

Las acciones manuales de Git, automatización, Playwright y validación están en
[docs/MANUAL_STEPS.md](docs/MANUAL_STEPS.md). El último resultado verificado está en
[reports/PIPELINE_EXECUTION_2026-06-20.md](reports/PIPELINE_EXECUTION_2026-06-20.md).

## Precios y labeling

El CSV de mercado debe contener:

```csv
date,precio_oro_soles_gramo
2026-06-15,401.25
```

Alternativamente puede contener:

```csv
date,precio_oro_usd_oz,tipo_cambio_usd_pen
2026-06-15,3300.10,3.72
```

Para cada noticia con fecha, el labeler usa la primera sesión disponible en esa fecha o después,
y compara contra una y tres sesiones posteriores. Si todavía no existen suficientes sesiones, los
campos futuros permanecen nulos y podrán completarse en una corrida posterior.

Para una descarga auxiliar con Yahoo Finance, cambie `download_market_if_missing` a `true`. En
producción es preferible alimentar el archivo desde el pipeline de mercado ya existente para
mantener una sola fuente de verdad.

## Supabase

Ejecute `sql/news_schema.sql` una vez en el SQL Editor de Supabase. El script crea:

1. `news_sources`
2. `news_raw`
3. `news_gpt_enriched`
4. `news_market_labels`
5. `daily_news_features`
6. `news_pipeline_runs`

Ejecute también `sql/fred_schema.sql`, que crea:

1. `fred_series_metadata`
2. `fred_observations`
3. `daily_macro_features`

La publicación usa `upsert` con claves primarias o únicas explícitas. Las noticias usan un UUID v5
derivado de la URL canónica, además de restricciones únicas para URL y hash de contenido.

FRED usa `(series_id, observation_date)` como restricción única y `feature_date` como clave primaria.

Después configure `.env`:

```dotenv
NEWS_PIPELINE_MODE=supabase
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
```

Y ejecute:

```bash
python main.py news all
```

## Fuentes y tolerancia a fallos

Las fuentes iniciales son Kitco, IG Commodities, La República Colombia y dos tags de Rumbo Minero.
Cada colector intenta:

1. HTML con `requests`.
2. RSS/Atom configurado, si existe.
3. Playwright opcional, si está instalado.

Una fuente bloqueada queda registrada con su error y no detiene las demás. Para activar Playwright:

```bash
pip install playwright
playwright install chromium
```

Los sitios pueden cambiar selectores, bloquear bots o exigir consentimiento. El pipeline extrae
solo información visible del listado y JSON-LD; no descarga artículos completos. Antes de aumentar
frecuencia o profundidad, revise robots.txt, términos de uso y límites de cada fuente.

## Automatización con GitHub Actions

`.github/workflows/toolmape_pipeline.yml` corre cada hora de lunes a viernes y también manualmente.
El cron de GitHub usa UTC. Agregue estos GitHub Secrets:

- `FRED_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

`OPENAI_API_KEY` es opcional y solo se agrega si se selecciona OpenAI. El workflow usa un runner
Windows self-hosted para acceder al Ollama local; alternativamente se programa
`scripts/run_local_pipeline.ps1` directamente con el Programador de tareas.

## Series macroeconómicas FRED

| Serie | Variable | Uso |
|---|---|---|
| `DGS10` | `us_10y_yield` | Rendimiento Treasury estadounidense a 10 años |
| `DGS2` | `us_2y_yield` | Rendimiento Treasury estadounidense a 2 años |
| `DFII10` | `us_10y_real_yield` | Rendimiento real Treasury a 10 años |
| `FEDFUNDS` | `fed_funds_rate` | Tasa efectiva de fondos federales |
| `CPIAUCSL` | `us_cpi` | Índice de precios al consumidor de Estados Unidos |
| `DTWEXBGS` | `broad_usd_index` | Índice amplio nominal del dólar |
| `SP500` | `sp500` | Proxy del mercado accionario estadounidense |
| `BAMLH0A0HYM2` | `high_yield_spread` | Proxy de estrés crediticio |

La primera descarga comienza en `2003-01-01`. Las posteriores descargan nuevamente una ventana
reciente —400 días por defecto— y hacen merge por serie/fecha. Esto captura revisiones sin volver a
solicitar todo el histórico.

Los valores `"."` de FRED se convierten en `NaN`. Las series se alinean a calendario diario usando
solo `forward fill`; nunca se usa `backfill`. CPI interanual/mensual y cambios de FEDFUNDS se
calculan en su frecuencia mensual nativa antes de propagarse.

### Features macro

Se generan curva 10y–2y, cambios de rendimientos a 1/5/20 días, retornos de dólar y S&P 500,
cambios del spread high yield, inflación interanual/mensual, cambio de Fed Funds y un
`macro_stress_score`.

El score de estrés es una primera versión: promedio de z-scores móviles de subida del spread high
yield, caída del S&P 500, subida del dólar y subida del rendimiento real. Usa únicamente datos
presentes y pasados y está aislado en `src/macro/fred_features.py` para facilitar su calibración.

### Advertencia temporal

FRED identifica observaciones por el período económico al que pertenecen. En esta primera versión,
CPI y FEDFUNDS quedan disponibles desde la fecha de observación, no desde la fecha real de
publicación. Esto puede producir look-ahead respecto al mundo real en backtests mensuales. Antes de
entrenar un modelo de producción deben incorporarse calendarios de publicación o vintages ALFRED.

## Pruebas

```bash
pytest -q
```

Las pruebas cubren deduplicación, labels, features de noticias, transformación de faltantes FRED,
forward fill mensual y features macro sin consumir APIs.

## Próximos pasos

- Añadir tests de contrato con fixtures HTML versionados por fuente.
- Integrar directamente el dataset del pipeline Random Forest.
- Sustituir la simplificación de fecha mensual por fechas reales de publicación/ALFRED.
- Medir precisión del GPT contra labels observados y calibrar `confianza_gpt`.
- Añadir monitoreo de cambios de layout y alertas por fuentes sin resultados.
- Incorporar scraping profundo solo cuando exista permiso y una necesidad demostrada.
