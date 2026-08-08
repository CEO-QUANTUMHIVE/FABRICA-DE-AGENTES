# Arranca el motor de voz completo para probarlo en local.
#
#   .\arrancar.ps1
#
# Abre tres ventanas (servidor, agente, frontend), genera el token y
# te deja todo listo. Para frenar todo: cerra las tres ventanas.
#
# NO usar $ErrorActionPreference = "Stop" en este script. PowerShell 5.1
# convierte el stderr de los comandos nativos en errores, y tanto uv como
# npm escriben avisos ahi aunque terminen bien. Con "Stop" el script se
# corta antes de generar el token.

$raiz = $PSScriptRoot
Set-Location $raiz

# Silencia el aviso de PyJWT por el secreto corto de --dev, que ensucia
# la salida y confunde la captura del token.
$env:PYTHONWARNINGS = "ignore"

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

# --- Token primero: si esto falla, no tiene sentido levantar nada ---

Write-Host "  Generando token..." -NoNewline
$salida = uv run python scripts/emitir_token.py sala-demo visitante
$token = $salida | Where-Object { $_ -is [string] -and $_.StartsWith("eyJ") } | Select-Object -First 1

if (-not $token) {
    Write-Host " FALLO" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Salida completa del comando:" -ForegroundColor Yellow
    $salida | ForEach-Object { Write-Host "    $_" }
    Write-Host ""
    Fallar "no se pudo generar el token. Revisa LIVEKIT_API_KEY y LIVEKIT_API_SECRET en .env."
}

# Se guarda en archivo ademas del portapapeles, por si el portapapeles falla.
$token | Out-File -FilePath (Join-Path $raiz "token.txt") -Encoding utf8
try { Set-Clipboard -Value $token } catch { }
Write-Host " OK" -ForegroundColor Green

# --- 1. Servidor de medios ---

Write-Host "  [1/3] Servidor LiveKit..." -NoNewline
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "`$host.UI.RawUI.WindowTitle='LiveKit'; Set-Location '$raiz'; .\scripts\livekit\livekit-server.exe --dev"
)
Start-Sleep -Seconds 3
Write-Host " ws://localhost:7880" -ForegroundColor Green

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
Start-Sleep -Seconds 4
Write-Host " http://localhost:5173" -ForegroundColor Green

# --- Cierre ---

Write-Host ""
Write-Host "  TU TOKEN (ya copiado al portapapeles):" -ForegroundColor Cyan
Write-Host ""
Write-Host "  $token" -ForegroundColor White
Write-Host ""
Write-Host "  Tambien quedo guardado en token.txt" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Ahora:" -ForegroundColor Cyan
Write-Host "    1. Abri  http://localhost:5173"
Write-Host "    2. Pega el token con Ctrl+V"
Write-Host "    3. Conectar, y dale permiso al microfono"
Write-Host ""
Write-Host "  Si algo falla, mira la ventana AGENTE." -ForegroundColor Yellow
Write-Host "  Para frenar todo, cerra las tres ventanas."
Write-Host ""

Start-Process "http://localhost:5173"
