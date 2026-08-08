# Arranca el motor de voz completo para probarlo en local.
#
#   .\arrancar.ps1
#
# Abre tres ventanas (servidor, agente, frontend), genera el token y
# te deja todo listo. Para frenar todo: cerrá las tres ventanas.

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
Set-Location $raiz

function Fallar($mensaje) {
    Write-Host ""
    Write-Host "  FALTA ALGO: $mensaje" -ForegroundColor Red
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "  Motor de Voz de QuantumHive" -ForegroundColor Cyan
Write-Host "  ---------------------------"
Write-Host ""

# --- Chequeos previos, para fallar temprano y con un mensaje claro ---

$servidor = Join-Path $raiz "scripts\livekit\livekit-server.exe"
if (-not (Test-Path $servidor)) {
    Fallar "no esta livekit-server.exe. Bajalo con el comando de docs/superpowers/plans/."
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

# --- 1. Servidor de medios ---

Write-Host "  [1/3] Servidor LiveKit..." -NoNewline
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "`$host.UI.RawUI.WindowTitle='LiveKit'; Set-Location '$raiz'; .\scripts\livekit\livekit-server.exe --dev"
)
Start-Sleep -Seconds 3
Write-Host " arriba en ws://localhost:7880" -ForegroundColor Green

# --- 2. Agente ---

Write-Host "  [2/3] Agente..." -NoNewline
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "`$host.UI.RawUI.WindowTitle='AGENTE - los errores salen aca'; Set-Location '$raiz'; uv run python -m motor_voz.voice.agente dev"
)
Write-Host " arrancando (la primera vez baja el modelo de VAD y tarda)" -ForegroundColor Green

# --- 3. Frontend ---

Write-Host "  [3/3] Frontend..." -NoNewline
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "`$host.UI.RawUI.WindowTitle='Frontend'; Set-Location '$raiz\frontend\demo'; npm run dev"
)
Start-Sleep -Seconds 3
Write-Host " en http://localhost:5173" -ForegroundColor Green

# --- 4. Token ---

Write-Host ""
Write-Host "  Generando token..." -ForegroundColor Cyan
$token = (uv run python scripts/emitir_token.py sala-demo visitante) | Select-Object -Last 1

if ($token -and $token.StartsWith("eyJ")) {
    Set-Clipboard -Value $token
    Write-Host "  Token copiado al portapapeles." -ForegroundColor Green
} else {
    Write-Host "  No se pudo generar el token. Revisa las variables LIVEKIT_* del .env." -ForegroundColor Red
    Write-Host "  Salida: $token"
}

Write-Host ""
Write-Host "  LISTO. Ahora:" -ForegroundColor Cyan
Write-Host "    1. Abri  http://localhost:5173"
Write-Host "    2. Pega el token con Ctrl+V (ya esta copiado)"
Write-Host "    3. Conectar, y dale permiso al microfono"
Write-Host ""
Write-Host "  Si algo falla, mira la ventana que dice AGENTE." -ForegroundColor Yellow
Write-Host "  Para frenar todo, cerra las tres ventanas."
Write-Host ""

Start-Process "http://localhost:5173"
