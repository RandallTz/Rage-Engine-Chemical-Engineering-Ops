# Construye (o actualiza) la aplicacion de escritorio offline del simulador para Windows.
# Guia: empaquetado/MANTENIMIENTO.md. Plan: docs/PLAN_EJECUTABLE_WINDOWS.md.
#
# Todo ocurre FUERA del repositorio, en $Salida: venv propio con las versiones de requirements.txt, copia del
# frontend sincronizada (no se toca frontend/ ni su .next de desarrollo), build 'standalone' de Next con la API
# en 127.0.0.1:8317, PyInstaller (carpeta, sin consola), ensamblado con node.exe y la web, estampado de
# version y PRUEBA DE HUMO de la build nueva. Solo si la prueba pasa se reemplaza $Destino; la version anterior
# queda en "$Destino-anterior".
#
# Uso (PowerShell, desde la raiz del repositorio; cerrar antes la aplicacion si esta abierta):
#   powershell -ExecutionPolicy Bypass -File empaquetado\construir.ps1
#   ... -SoloEmpaquetar      reutiliza la web ya compilada (cambios solo de Python)
#   ... -SinPrueba           no ejecuta la prueba de humo (no recomendado)

param(
    [string]$Salida = "$env:USERPROFILE\Desktop\SimuladorDR_build",
    [string]$Destino = "$env:USERPROFILE\Desktop\SimuladorDR",
    [switch]$SoloEmpaquetar,
    [switch]$SinPrueba
)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Api = "http://127.0.0.1:8317"
$t0 = Get-Date
New-Item -ItemType Directory -Force $Salida | Out-Null
function Paso($m) { Write-Host "`n== $m" -ForegroundColor Cyan }

# 0. la aplicacion no debe estar abierta (puertos 3317/8317 y archivos en uso)
if (Get-Process SimuladorDR -ErrorAction SilentlyContinue) { throw "Cierra SimuladorDR antes de reconstruir." }

# 1. entorno de Python: solo se reinstala si cambia requirements.txt
Paso "Entorno de Python"
$py = "$Salida\venv\Scripts\python.exe"
if (-not (Test-Path $py)) { python -m venv "$Salida\venv" }
$hashReq = (Get-FileHash "$Repo\requirements.txt").Hash
$marca = "$Salida\venv\requirements.sha256"
if (-not (Test-Path $marca) -or (Get-Content $marca) -ne $hashReq) {
    & $py -m pip install --upgrade pip | Out-Null
    & $py -m pip install -r "$Repo\requirements.txt" pyinstaller==6.22.3 pywebview==6.2.1
    if ($LASTEXITCODE -ne 0) { throw "pip fallo" }
    Set-Content $marca $hashReq
} else { Write-Host "requirements.txt sin cambios: se reutiliza el venv" }

# 2. frontend: copia sincronizada y build 'standalone'
if (-not $SoloEmpaquetar) {
    Paso "Frontend (copia sincronizada y next build)"
    robocopy "$Repo\frontend" "$Salida\frontend" /MIR /MT:16 /NFL /NDL /NJH /NP /XD .next qa_* auditoria_* /XF *.png *.jpg *.log | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy fallo ($LASTEXITCODE)" }
    $cfg = Get-Content "$Salida\frontend\next.config.ts" -Raw
    if ($cfg -notmatch 'output:\s*"standalone"') {
        $cfg = $cfg -replace 'const nextConfig: NextConfig = \{', "const nextConfig: NextConfig = {`n  output: `"standalone`","
        Set-Content "$Salida\frontend\next.config.ts" $cfg -Encoding utf8
    }
    # node_modules llega reflejado desde frontend/ (mismas versiones que desarrollo; sin descargas)
    Push-Location "$Salida\frontend"
    $env:NEXT_PUBLIC_API_URL = $Api; $env:NEXT_TELEMETRY_DISABLED = "1"
    npx next build
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "next build fallo" }
    Pop-Location
    if (Test-Path "$Salida\web") { Remove-Item -Recurse -Force "$Salida\web" }
    Copy-Item -Recurse "$Salida\frontend\.next\standalone" "$Salida\web"
    New-Item -ItemType Directory -Force "$Salida\web\.next" | Out-Null
    Copy-Item -Recurse "$Salida\frontend\.next\static" "$Salida\web\.next\static"
    Copy-Item -Recurse "$Salida\frontend\public" "$Salida\web\public"
    $n = (Select-String -Path "$Salida\web\.next\static\chunks\*.js" -Pattern "127.0.0.1:8317" -List).Count
    if ($n -eq 0) { throw "La web compilada no apunta a $Api" }
}
if (-not (Test-Path "$Salida\web\server.js")) { throw "No hay web compilada: ejecuta sin -SoloEmpaquetar" }

# 3. PyInstaller: carpeta (onedir), ventana sin consola
Paso "PyInstaller"
Push-Location $Salida
& "$Salida\venv\Scripts\pyinstaller.exe" --noconfirm --clean --onedir --windowed --name SimuladorDR `
    --distpath "$Salida\dist" --workpath "$Salida\work" --specpath "$Salida" `
    --paths "$Repo" `
    --collect-submodules backend --collect-submodules core --collect-submodules api `
    --collect-submodules config --collect-submodules thermodynamics --collect-submodules uvicorn `
    --collect-data thermo --collect-data chemicals --collect-data fluids --collect-data pint `
    --collect-data plotly --collect-all webview `
    "$Repo\empaquetado\lanzador.py"
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "pyinstaller fallo" }
Pop-Location

# 4. ensamblado: web, node.exe, documentacion y version
Paso "Ensamblado"
$app = "$Salida\dist\SimuladorDR"
Copy-Item -Recurse "$Salida\web" "$app\web"
New-Item -ItemType Directory -Force "$app\node" | Out-Null
Copy-Item (Get-Command node).Source "$app\node\node.exe"
Copy-Item "$Repo\empaquetado\LEEME.md" "$app\LEEME.md"
# peticiones de los ejemplos de demostracion (para --prueba-demostracion; las hojas van en la web)
New-Item -ItemType Directory -Force "$app\demostracion" | Out-Null
Copy-Item "$Repo\docs\ejemplos\demostracion\*-peticion.json" "$app\demostracion\"
Push-Location $Repo
$commit = (git rev-parse --short HEAD) 2>$null
$sucio = if ((git status --porcelain) 2>$null) { "-sucio" } else { "" }
Pop-Location
$version = @(
    "SimuladorDR (prueba de escritorio)",
    "construido: $((Get-Date).ToString('yyyy-MM-dd HH:mm'))",
    "commit: $commit$sucio",
    "python: $(& $py -c 'import sys;print(sys.version.split()[0])')",
    "node: $(node --version)",
    "requirements.txt sha256: $hashReq"
)
Set-Content "$app\VERSION.txt" $version -Encoding utf8

# 5. prueba de humo de la build NUEVA (sin ventana) antes de reemplazar nada
if (-not $SinPrueba) {
    Paso "Prueba de humo"
    $prueba = "$env:LOCALAPPDATA\SimuladorDR\logs\prueba.txt"
    if (Test-Path $prueba) { Remove-Item $prueba }
    $p = Start-Process -FilePath "$app\SimuladorDR.exe" -ArgumentList "--prueba" -Wait -PassThru
    if (Test-Path $prueba) { Get-Content $prueba | Write-Host }
    if ($p.ExitCode -ne 0) { throw "La prueba de humo fallo (codigo $($p.ExitCode)); $Destino NO se reemplazo." }
}

# 6. reemplazo con respaldo de la version anterior
Paso "Instalacion"
if (Test-Path "$Destino-anterior") { Remove-Item -Recurse -Force "$Destino-anterior" }
if (Test-Path $Destino) { Move-Item $Destino "$Destino-anterior" }
Move-Item $app $Destino
Write-Host "`nListo en $([int]((Get-Date) - $t0).TotalMinutes) min: $Destino\SimuladorDR.exe ($commit$sucio)" -ForegroundColor Green
if (Test-Path "$Destino-anterior") { Write-Host "Version anterior: $Destino-anterior" }
