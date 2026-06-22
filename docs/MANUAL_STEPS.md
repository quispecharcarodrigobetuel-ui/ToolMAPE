# Acciones manuales restantes

El pipeline, FRED, Ollama y Supabase ya funcionan. Estas acciones son necesarias únicamente para
versionar y automatizar la operación.

## 1. Reiniciar la terminal o Codex para detectar Git

Git 2.54 está instalado en:

```text
C:\Program Files\Git\cmd\git.exe
```

La sesión actual fue abierta antes de la instalación y todavía no recibió el nuevo `PATH`. Cierre y
abra nuevamente PowerShell/Codex. Compruebe:

```powershell
git --version
```

Mientras tanto puede usar la ruta completa:

```powershell
& "C:\Program Files\Git\cmd\git.exe" --version
```

## 2. Crear el repositorio

La carpeta todavía no es un repositorio Git. Cuando Git esté visible:

```powershell
cd "D:\Scraper ToolMAPE"
git init
git add .
git status
git commit -m "Implementar pipeline Toolmape"
```

Antes del commit confirme que `.env` no aparece en `git status`. Está incluido en `.gitignore`.

Para GitHub, cree manualmente un repositorio vacío y conecte su URL:

```powershell
git branch -M main
git remote add origin URL_DEL_REPOSITORIO
git push -u origin main
```

## 3. Elegir una forma de automatización

Actualmente no existe una tarea de Windows ni un runner de GitHub Actions instalado. Elija una de
estas opciones.

### Opción A — Programador de tareas de Windows

Es la opción más sencilla para este equipo. Cree una tarea que ejecute:

```powershell
powershell.exe -ExecutionPolicy Bypass -File "D:\Scraper ToolMAPE\scripts\run_local_pipeline.ps1" -Mode supabase
```

Configuración recomendada:

- lunes a viernes;
- cada hora;
- iniciar aunque el usuario no haya abierto una terminal;
- no iniciar una segunda instancia si la anterior sigue activa;
- reintentar después de 15 minutos si falla;
- despertar el equipo para ejecutar;
- guardar la contraseña de la cuenta si Windows la solicita.

La computadora debe estar encendida, conectada a internet y sin suspensión durante la ejecución.
Ollama debe arrancar con Windows o estar abierto.

### Opción B — GitHub Actions self-hosted

El workflow `.github/workflows/toolmape_pipeline.yml` requiere un runner Windows self-hosted porque
Ollama vive en esta computadora.

Pasos manuales:

1. Suba el repositorio a GitHub.
2. Abra `Settings → Actions → Runners → New self-hosted runner`.
3. Elija Windows x64.
4. Ejecute los comandos únicos mostrados por GitHub.
5. Instale el runner como servicio.
6. Agregue GitHub Secrets:
   - `FRED_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
7. Compruebe que Python, Git, Ollama y `qwen2.5:3b` estén disponibles para la cuenta del servicio.

No agregue `OPENAI_API_KEY`: Toolmape usa Ollama.

## 4. Playwright para IG — opcional

IG Commodities continúa bloqueando `requests`. Las demás fuentes producen noticias. Para activar el
fallback:

```powershell
pip install playwright
playwright install chromium
```

Después ejecute:

```powershell
python main.py news scrape --mode local
```

Playwright no garantiza acceso si el sitio aplica CAPTCHA o políticas anti-bot. Deben revisarse sus
términos de uso y `robots.txt`.

## 5. Validación humana del modelo — necesaria antes de decisiones reales

Qwen genera JSON correctamente, pero todavía no está calibrado. Antes de usar sus scores para
decidir si vender oro:

1. Seleccione al menos 100–200 noticias.
2. Etiquete manualmente relevancia, dirección e impacto.
3. Compare Qwen con esas etiquetas.
4. Mida concordancia por clase y matriz de confusión.
5. Ajuste prompt, modelo o pesos.
6. Valide el aporte predictivo con separación temporal fuera de muestra.

No interprete `confianza_gpt=0.875` como 87.5% de precisión.

## 6. Limitaciones de datos que requieren una decisión

- `BAMLH0A0HYM2` solo ofrece tres años recientes en FRED desde abril de 2026. Para completar
  2020–2023 debe obtenerse el histórico autorizado del proveedor original, reemplazar la feature o
  aceptar valores faltantes.
- CPI y FEDFUNDS se alinean inicialmente desde su fecha de observación. Para backtesting riguroso
  deben usarse fechas reales de publicación o vintages ALFRED.
- yfinance es una fuente gratuita sin SLA y representa precios financieros, no el precio físico
  pagado al minero.
- Los costos, ley del mineral, descuento del comprador, transporte e impuestos todavía no forman
  parte del precio objetivo.

## 7. Operación habitual

Ejecución local sin publicación:

```powershell
powershell -ExecutionPolicy Bypass -File "D:\Scraper ToolMAPE\scripts\run_local_pipeline.ps1" -Mode local
```

Ejecución completa con Supabase:

```powershell
powershell -ExecutionPolicy Bypass -File "D:\Scraper ToolMAPE\scripts\run_local_pipeline.ps1" -Mode supabase
```

Revisión rápida:

```powershell
python -m pytest -q
ollama list
```

Los secretos deben permanecer únicamente en `.env`, GitHub Secrets o el almacén seguro elegido.
