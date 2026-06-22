# IA local para Toolmape

## Configuración activa

Toolmape usa por defecto:

```dotenv
NEWS_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:latest
```

La prueba del 20 de junio de 2026 en este equipo (Ryzen 7 4700U, 16 GB RAM, ejecución 100 % CPU)
produjo JSON válido en dos noticias. Los tiempos observados fueron aproximadamente 116 segundos
con carga inicial y 79 segundos con el modelo caliente. Son mediciones puntuales, no garantías.

## Modelos locales posibles

### `llama3:latest`

- Ya está instalado.
- Calidad razonable para comenzar.
- Tamaño local aproximado: 4.7 GB.
- En este equipo es lento y puede inferir explicaciones que no estén plenamente sustentadas por un
  titular corto. La evaluación contra labels reales es obligatoria.

### `qwen2.5:3b`

```powershell
ollama pull qwen2.5:3b
```

- Recomendación inicial si se prioriza velocidad.
- Qwen 2.5 fue diseñado con mejoras específicas para JSON estructurado y soporte multilingüe,
  incluido español.
- Menor capacidad que un modelo de 7B/8B; conviene comparar sus resultados en una muestra etiquetada.

### `qwen2.5:7b`

```powershell
ollama pull qwen2.5:7b
```

- Recomendación inicial si se prioriza adherencia a JSON y calidad en español.
- Su velocidad en CPU probablemente será similar a `llama3:latest`.

### `llama3.2:3b`

```powershell
ollama pull llama3.2:3b
```

- Modelo pequeño y multilingüe.
- Adecuado para resumir y clasificar con menor uso de memoria.
- Puede perder matices macrofinancieros frente a modelos mayores.

### `gemma3:4b`

```powershell
ollama pull gemma3:4b
```

- Alternativa compacta con soporte multilingüe.
- Debe evaluarse con el mismo conjunto de noticias antes de adoptarla.

Para cambiar de modelo:

```dotenv
OLLAMA_MODEL=qwen2.5:3b
```

No hace falta modificar el código. Toolmape detecta que cambió `provider` o `model` y vuelve a
enriquecer las noticias que habían sido procesadas con el modelo anterior.

## Alternativa sin modelo generativo

Es posible sustituir el LLM por reglas deterministas:

- diccionarios de palabras clave;
- clasificación de Fed hawkish/dovish;
- detección de oro, dólar, inflación y geopolítica;
- puntuaciones fijas por evento.

Esta opción sería rápida, reproducible y totalmente auditable, pero entendería peor la negación,
la causalidad y noticias ambiguas. Todavía no está implementada como proveedor; puede añadirse si
se necesita máxima velocidad.

## Automatización

### Programador de tareas de Windows

Es la opción más sencilla para conservar Ollama y los modelos en esta computadora. Ejecute primero:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_local_pipeline.ps1 -Mode local
```

Después cree una tarea que ejecute ese mismo comando cada hora. La computadora debe estar encendida,
Ollama activo y sin suspensión.

### GitHub Actions con runner self-hosted

El workflow incluido usa un runner Windows self-hosted. GitHub coordina la tarea, pero el trabajo y
Ollama se ejecutan en esta máquina. Deben instalarse el runner oficial de GitHub, Python, Git y
Ollama, y mantener el servicio del runner activo.

Un runner alojado por GitHub no puede conectarse a `localhost` de esta computadora. Descargar el
modelo de varios GB en cada ejecución tampoco es eficiente.

## Evaluación recomendada

Antes de elegir un modelo definitivo:

1. Seleccionar al menos 100 noticias variadas.
2. Etiquetarlas manualmente en dirección, impacto y relevancia.
3. Ejecutar cada modelo con temperatura 0 y la misma semilla.
4. Medir JSON válido, tiempo, concordancia de dirección, error de impacto y estabilidad entre corridas.
5. Elegir el modelo por calidad y tiempo, no por una sola noticia.

`confianza_gpt` es una autoevaluación del modelo y no debe usarse como exactitud hasta calibrarla
contra ese conjunto manual y los labels observados.
