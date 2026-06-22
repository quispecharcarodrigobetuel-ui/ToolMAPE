# Diccionario de métricas de Toolmape

Este documento define las variables calculadas por el sistema. Salvo indicación contraria, los
retornos se almacenan como fracción decimal: `0.01 = 1 %`.

## 1. Precio objetivo de mercado

| Campo | Fórmula | Unidad | Interpretación |
|---|---|---|---|
| `precio_oro_usd_oz` | Precio de cierre de `GC=F` | USD por onza troy | Proxy del precio internacional del oro |
| `tipo_cambio_usd_pen` | Precio de cierre de `PEN=X` | PEN por USD | Soles requeridos para comprar un dólar |
| `precio_oro_soles_gramo` | `(precio_oro_usd_oz / 31.1035) × tipo_cambio_usd_pen` | PEN por gramo | Variable objetivo de Toolmape |

`31.1035` es la cantidad aproximada de gramos en una onza troy. Los datos de Yahoo Finance son
proxies de mercado y pueden diferir del precio físico local, costos de refinación, ley del mineral,
descuentos comerciales e impuestos.

## 2. Labels observados de noticias

Para una noticia se toma como referencia la primera sesión de mercado disponible en su fecha de
publicación o posteriormente. `P0` es ese precio; `P1` y `P3` son los precios una y tres sesiones
de mercado después.

| Campo | Fórmula |
|---|---|
| `return_1d` | `P1 / P0 - 1` |
| `return_3d` | `P3 / P0 - 1` |
| `direction_1d`, `direction_3d` | Clasificación del retorno con umbral configurable |
| `impact_class_1d`, `impact_class_3d` | Clasificación de la magnitud absoluta del retorno |

Dirección predeterminada:

- `bajista`: retorno menor que `-0.003`.
- `neutral`: retorno entre `-0.003` y `0.003`, inclusive.
- `alcista`: retorno mayor que `0.003`.

Impacto predeterminado según `abs(retorno)`:

| Clase | Intervalo |
|---|---|
| `nulo` | `< 0.003` |
| `bajo` | `0.003 ≤ x < 0.007` |
| `medio` | `0.007 ≤ x < 0.015` |
| `alto` | `0.015 ≤ x < 0.025` |
| `muy_alto` | `≥ 0.025` |

Los umbrales viven en `config/news_pipeline.yaml`.

## 3. Clasificación local de noticias

Ollama o, opcionalmente, OpenAI generan estas variables cualitativas:

| Campo | Dominio o significado |
|---|---|
| `tipo_activo` | Activo o grupo económico principal |
| `subtipo_evento` | Tipo de evento macro, minero o geopolítico |
| `pais_region` | Regiones mencionadas o afectadas |
| `sentido_oro` | `alcista`, `bajista`, `neutral`, `mixto` o `incierto` |
| `sentido_dolar` | Dirección esperada del dólar |
| `sentido_usd_pen` | Dirección esperada del tipo de cambio USD/PEN |
| `sentido_precio_oro_soles` | Efecto combinado esperado sobre oro en PEN/gramo |
| `impacto_esperado` | `nulo`, `bajo`, `medio`, `alto` o `muy_alto` |
| `horizonte_probable` | `inmediato`, `1d`, `3d`, `semanas`, `largo_plazo` o `incierto` |
| `confianza_gpt` | Autoevaluación del modelo entre 0 y 1 |

`confianza_gpt` conserva su nombre histórico aunque el proveedor sea Ollama. No es una probabilidad
calibrada ni una precisión observada. Debe validarse posteriormente contra los labels de mercado.
El proveedor y modelo reales se guardan en `provider` y `model`.

Los campos de escenarios y razonamiento son explicativos, no métricas cuantitativas ni
recomendaciones financieras.

## 4. Features diarias de noticias

Se usa:

```text
impacto_numérico = nulo:0, bajo:1, medio:2, alto:3, muy_alto:4
peso_noticia = reliability_weight × confianza_gpt
aporte_ponderado = peso_noticia × impacto_numérico
```

`reliability_weight` se configura por fuente. También es una ponderación heurística, no una medida
estadística de veracidad.

| Campo | Cálculo |
|---|---|
| `news_count_total` | Número de noticias enriquecidas con éxito en la fecha |
| `news_count_gold` | Conteo detectado por palabras relacionadas con oro |
| `news_count_dollar` | Conteo detectado por palabras relacionadas con dólar/USD |
| `news_count_fed` | Conteo detectado por Fed/FOMC |
| `news_count_geopolitics` | Conteo detectado por términos geopolíticos |
| `news_count_mining_peru` | Conteo con términos de minería y Perú |
| `gold_bullish_score` | Suma de aportes ponderados con `sentido_oro=alcista` |
| `gold_bearish_score` | Suma de aportes ponderados con `sentido_oro=bajista` |
| `dollar_bullish_score` | Suma de aportes ponderados con `sentido_dolar=alcista` |
| `dollar_bearish_score` | Suma de aportes ponderados con `sentido_dolar=bajista` |
| `fed_hawkish_score` | Suma de aportes con términos hawkish/tasas altas |
| `fed_dovish_score` | Suma de aportes con términos dovish/recortes |
| `geopolitical_risk_score` | Suma de aportes en noticias geopolíticas |
| `avg_impact_expected` | Media del impacto numérico de 0 a 4 |
| `max_impact_expected` | Máximo impacto numérico de 0 a 4 |
| `avg_confidence_gpt` | Media de la autoevaluación del modelo |
| `news_conflict_score` | `2 × min(A, B) / (A + B)` |

En `news_conflict_score`, `A` y `B` son los conteos direccionales alcistas y bajistas para oro;
neutrales/mixtos no participan. Vale `0` cuando domina una sola dirección y `1` cuando ambos
conteos están equilibrados. Los conteos temáticos y hawkish/dovish usan reglas de palabras clave,
por lo que pueden tener falsos positivos o negativos.

## 5. Niveles macroeconómicos FRED

| Campo | Serie | Unidad habitual |
|---|---|---|
| `us_10y_yield` | `DGS10` | Porcentaje anual |
| `us_2y_yield` | `DGS2` | Porcentaje anual |
| `us_10y_real_yield` | `DFII10` | Porcentaje anual |
| `fed_funds_rate` | `FEDFUNDS` | Porcentaje anual |
| `us_cpi` | `CPIAUCSL` | Índice |
| `broad_usd_index` | `DTWEXBGS` | Índice |
| `sp500` | `SP500` | Puntos de índice |
| `high_yield_spread` | `BAMLH0A0HYM2` | Puntos porcentuales |

Desde abril de 2026, FRED publica únicamente tres años recientes de `BAMLH0A0HYM2`. Los períodos
anteriores quedan como faltantes salvo que se incorpore otra fuente autorizada.

Las series mensuales se calculan en frecuencia mensual y luego se propagan hacia adelante. No se
usa `backfill`. La fecha de observación no siempre coincide con la fecha real de publicación:
esta limitación debe corregirse con calendarios de publicación o ALFRED antes de un backtest
riguroso.

## 6. Features macroeconómicas

Las diferencias de rendimientos/spreads están expresadas en puntos porcentuales. Los retornos e
inflación se almacenan como fracciones decimales.

| Campo | Fórmula |
|---|---|
| `yield_curve_10y_2y` | `us_10y_yield - us_2y_yield` |
| `real_yield_change_1d` | `real_yield[t] - real_yield[t-1]` |
| `real_yield_change_5d` | `real_yield[t] - real_yield[t-5]` |
| `real_yield_change_20d` | `real_yield[t] - real_yield[t-20]` |
| `nominal_10y_change_1d` | `yield10y[t] - yield10y[t-1]` |
| `nominal_10y_change_5d` | `yield10y[t] - yield10y[t-5]` |
| `broad_usd_return_1d` | `usd_index[t] / usd_index[t-1] - 1` |
| `broad_usd_return_5d` | `usd_index[t] / usd_index[t-5] - 1` |
| `sp500_return_1d` | `sp500[t] / sp500[t-1] - 1` |
| `sp500_return_5d` | `sp500[t] / sp500[t-5] - 1` |
| `credit_stress_change_1d` | `HY_spread[t] - HY_spread[t-1]` |
| `credit_stress_change_5d` | `HY_spread[t] - HY_spread[t-5]` |
| `cpi_yoy` | `CPI[m] / CPI[m-12] - 1` |
| `cpi_mom` | `CPI[m] / CPI[m-1] - 1` |
| `fed_funds_change` | `FedFunds[m] - FedFunds[m-1]` |

Las ventanas `1d`, `5d` y `20d` usan filas del calendario diario alineado. Como los niveles se
propagan en fines de semana y días sin observación, significan días calendario, no necesariamente
sesiones bursátiles. En cambio, los labels de noticias a 1d/3d sí usan sesiones de mercado.

### `macro_stress_score`

Componentes:

```text
C = credit_stress_change_5d
E = -sp500_return_5d
U = broad_usd_return_5d
R = real_yield_change_5d
```

Cada componente se estandariza con media y desviación móvil de 252 días, usando un mínimo de 20:

```text
z_X[t] = (X[t] - media_móvil_252(X)[t]) / desviación_móvil_252(X)[t]
macro_stress_score[t] = media(z_C[t], z_E[t], z_U[t], z_R[t])
```

Solo usa pasado y presente. Un valor positivo indica más estrés relativo a la historia reciente.
No tiene unidad y no posee umbrales universales. Es una feature experimental, no un índice
económico oficial.

## 7. Métricas operativas

Los logs registran conteos de noticias encontradas, nuevas, duplicadas y enriquecidas; series FRED
exitosas/fallidas; observaciones descargadas; features generadas; errores y duración en segundos.
Son métricas de salud del pipeline, no variables predictivas.

## 8. Reglas de validación

- Toda fórmula o umbral nuevo debe añadirse aquí y a su archivo YAML cuando sea configurable.
- Ninguna confianza declarada por un LLM debe presentarse como probabilidad calibrada.
- Las evaluaciones del modelo deben separar entrenamiento y prueba temporalmente.
- Las features no deben usar `backfill` ni valores futuros.
- Los cambios de definición requieren versionar el dataset o registrar la fecha de cambio.
