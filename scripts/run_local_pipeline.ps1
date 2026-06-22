param(
    [ValidateSet("local", "supabase")]
    [string]$Mode = "local"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

try {
    Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5 | Out-Null
}
catch {
    throw "Ollama no responde en http://localhost:11434. Abra Ollama antes de ejecutar el pipeline."
}

& $Python main.py all --mode $Mode
if ($LASTEXITCODE -ne 0) {
    throw "Toolmape terminó con código $LASTEXITCODE"
}
