# Arrancar LiveKit en desarrollo

1. Terminal 1 — servidor de medios:

       .\scripts\livekit\livekit-server.exe --dev

   Queda escuchando en ws://localhost:7880 con credenciales fijas
   devkey / secret.

2. Terminal 2 — agente:

       uv run python -m motor_voz.voice.agente dev

3. Terminal 3 — frontend demo:

       cd frontend/demo && npm run dev

4. Generar un token para entrar a la sala desde el navegador:

       uv run python scripts/emitir_token.py sala-demo visitante

   Copiar el JWT que imprime y pegarlo en la demo.

El servidor en modo --dev no persiste nada y no usa TLS. Para produccion
va el mismo binario en un VPS con dominio, certificado y puertos UDP
abiertos para el media WebRTC.
