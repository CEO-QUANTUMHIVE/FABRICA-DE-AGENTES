# Imagen unica para las dos piezas del motor. El comando decide cual corre:
#
#   API      python -m motor_voz.api.servidor        (default)
#   agente   python -m motor_voz.voice.agente start
#
# Una sola imagen en vez de dos porque comparten casi todo el codigo, y dos
# imagenes se desincronizan: se actualiza una, se olvida la otra.
#
# Portable a proposito: corre igual en Cloud Run, Fly, Render o un VPS. La
# unica dependencia del entorno son las variables del .env.

FROM python:3.12-slim

# ffmpeg lo necesitan los plugins de audio; curl, el healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Las dependencias primero: si no cambian, Docker reusa la capa y el build
# baja de minutos a segundos.
COPY pyproject.toml uv.lock README.md ./
RUN pip install --no-cache-dir uv && uv pip install --system --no-cache .

COPY src/ ./src/
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1

# Cloud Run inyecta PORT; en local vale el default de la config.
ENV API_PUERTO=8080
EXPOSE 8080

# Sin privilegios: si alguien se escapa del proceso, no es root.
RUN useradd -m -u 1000 motor && chown -R motor:motor /app
USER motor

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD curl -fsS http://localhost:${API_PUERTO}/api/salud || exit 1

CMD ["python", "-m", "motor_voz.api.servidor"]
