# Ejecución completa de Toolmape — 20 de junio de 2026

## Estado general

La ejecución local y la publicación en Supabase finalizaron correctamente.

| Componente | Resultado |
|---|---:|
| Pruebas automatizadas | 10 aprobadas |
| Sesiones de mercado | 1,626 |
| Rango de mercado | 2020-01-02 a 2026-06-19 |
| Noticias normalizadas | 30 |
| Noticias enriquecidas con Ollama | 30/30 |
| Modelo local | `qwen2.5:3b` |
| Labels creados | 30 |
| Labels con retorno 1d disponible | 24 |
| Labels con retorno 3d disponible | 14 |
| Fechas con features de noticias | 11 |
| Observaciones FRED publicadas | 27,663 |
| Fechas con features macro | 8,572 |
| Dataset final | 1,626 filas × 45 columnas |

## Distribución producida por Qwen

| Variable | Distribución |
|---|---|
| Impacto esperado | 28 bajo, 2 alto |
| Sentido del oro | 20 bajista, 7 neutral, 3 alcista |
| Confianza media declarada | 0.875 |

La confianza es una autoevaluación del modelo, no exactitud calibrada. Esta distribución debe
compararse con etiquetas humanas y resultados de mercado antes de utilizarla como evidencia de
calidad predictiva.

## Supabase verificado

| Tabla | Filas |
|---|---:|
| `news_sources` | 5 |
| `news_raw` | 30 |
| `news_gpt_enriched` | 30 |
| `news_market_labels` | 30 |
| `daily_news_features` | 11 |
| `news_pipeline_runs` | 20 |
| `fred_series_metadata` | 8 |
| `fred_observations` | 27,663 |
| `daily_macro_features` | 8,572 |

Se retiraron tres features obsoletas causadas por fechas ambiguas de Rumbo Minero. El parser ahora:

- prioriza `time[datetime]`;
- reconoce meses escritos en español;
- preserva correctamente fechas ISO;
- rechaza fechas más de un día posteriores al scraping;
- actualiza metadatos aunque una URL ya estuviera deduplicada;
- reprocesa una noticia cuando cambia la huella de su entrada.

## Cobertura FRED

| Serie | Observaciones | Rango |
|---|---:|---|
| `DGS10` | 6,121 | 2003-01-01 a 2026-06-17 |
| `DGS2` | 6,121 | 2003-01-01 a 2026-06-17 |
| `DFII10` | 6,120 | 2003-01-02 a 2026-06-17 |
| `FEDFUNDS` | 281 | 2003-01-01 a 2026-05-01 |
| `CPIAUCSL` | 281 | 2003-01-01 a 2026-05-01 |
| `DTWEXBGS` | 5,335 | 2006-01-02 a 2026-06-12 |
| `SP500` | 2,609 | 2016-06-20 a 2026-06-18 |
| `BAMLH0A0HYM2` | 795 | 2023-06-19 a 2026-06-17 |

Desde abril de 2026, FRED limita `BAMLH0A0HYM2` a tres años de observaciones. Por ello,
`high_yield_spread` tiene 871 valores faltantes dentro del dataset de mercado 2020–2026. No es un
fallo de descarga. El `macro_stress_score` puede calcularse con los demás componentes porque usa la
media de los z-scores disponibles.

## Archivos resultantes

- `data/market/market_prices.csv`
- `data/news/enriched/latest.jsonl`
- `data/news/labeled/latest.jsonl`
- `data/news/features/daily_news_features.csv`
- `data/macro/processed/fred_macro_dataset.csv`
- `data/macro/processed/daily_macro_features.csv`
- `data/model/toolmape_features.csv`
- `logs/news/news_pipeline_runs.jsonl`
- `logs/macro/fred_pipeline_runs.jsonl`

## Tiempos observados

Qwen procesó 30 noticias en aproximadamente 21 minutos. Tres noticias reprocesadas después de
corregir sus fechas tardaron unos 136 segundos. El tiempo depende de la carga del equipo y de que el
modelo ya esté cargado en memoria.
