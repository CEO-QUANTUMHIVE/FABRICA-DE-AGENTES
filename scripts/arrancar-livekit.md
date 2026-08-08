# Arrancar LiveKit en desarrollo

1. Terminal 1 — servidor de medios:

       .\scripts\livekit\livekit-server.exe --dev

   Queda escuchando en ws://localhost:7880 con credenciales fijas
   devkey / secret.

2. Terminal 2 — agente:

       uv run python -m motor_voz.voice.agente dev

3. Terminal 3 — frontend demo:

       cd frontend/demo && npm run dev

El servidor en modo --dev no persiste nada y no usa TLS. Para produccion
va el mismo binario en un VPS con dominio, certificado y puertos UDP
abiertos para el media WebRTC.
