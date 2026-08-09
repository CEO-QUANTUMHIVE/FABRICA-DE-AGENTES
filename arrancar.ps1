# Arranca el motor de voz completo para probarlo en local.
#
#   .\arrancar.ps1
#
# Abre cuatro ventanas y el navegador. Para frenar todo: cerra las ventanas.
#
# NO usar $ErrorActionPreference = "Stop" en este script. PowerShell 5.1
# convierte el stderr de los comandos nativos en errores, y tanto uv como
# npm escriben avisos ahi aunque terminen bien.

$raiz = $PSScriptRoot
Set-Location $raiz
$env:PYTHONWARNINGS = "ignore"

function Fallar($mensaje) {
    Write-Host ""
    Write-Host "  FALTA ALGO: $mensaje" -ForegroundColor Red
    Write-Host ""
    exit 1
}

function Ventana($titulo, $comando, $carpeta) {
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "`$host.UI.RawUI.WindowTitle='$titulo'; Set-Location '$carpeta'; $comando"
    )
}

Write-Host ""
Write-Host "  Motor de Voz de QuantumHive" -ForegroundColor Cyan
Write-Host "  ---------------------------"
Write-Host ""

if (-not (Test-Path (Join-Path $raiz "scripts\livekit\livekit-server.exe"))) {
    Fallar "no esta livekit-server.exe en scripts\livekit\."
}
if (-not (Test-Path (Join-Path $raiz ".env"))) {
    Fallar "no existe .env. Copia .env.example y completa las claves."
}
if (-not (Test-Path (Join-Path $raiz "frontend\demo\node_modules"))) {
    Write-Host "  Instalando dependencias del frontend (una sola vez)..." -ForegroundColor Yellow
    Push-Location (Join-Path $raiz "frontend\demo")
    npm install --silent
    Pop-Location
}

Write-Host "  [1/4] Servidor LiveKit..." -NoNewline
Ventana "LiveKit" ".\scripts\livekit\livekit-server.exe --dev" $raiz
Start-Sleep -Seconds 3
Write-Host " ws://localhost:7880" -ForegroundColor Green

Write-Host "  [2/4] API de tokens..." -NoNewline
Ventana "API de tokens" "uv run python -m motor_voz.api.servidor" $raiz
Start-Sleep -Seconds 2
Write-Host " http://localhost:8080" -ForegroundColor Green

Write-Host "  [3/4] Agente..." -NoNewline
Ventana "AGENTE - los errores salen aca" "uv run python -m motor_voz.voice.agente dev" $raiz
Write-Host " arrancando (la primera vez baja el modelo de VAD y tarda)" -ForegroundColor Green

Write-Host "  [4/4] Frontend..." -NoNewline
Ventana "Frontend" "npm run dev" (Join-Path $raiz "frontend\demo")
Start-Sleep -Seconds 4
Write-Host " http://localhost:5173" -ForegroundColor Green

Write-Host ""
Write-Host "  LISTO. Ya no hace falta copiar ningun token:" -ForegroundColor Cyan
Write-Host "  la pagina se lo pide sola a la API."
Write-Host ""
Write-Host "  1. Elegi el nivel de realismo (Basico / Natural / Humano)"
Write-Host "  2. Toca Hablar y dale permiso al microfono"
Write-Host "  3. Cambia de nivel en vivo para comparar los tres planes"
Write-Host ""
Write-Host "  Si algo falla, mira la ventana AGENTE." -ForegroundColor Yellow
Write-Host ""

Start-Process "http://localhost:5173"
