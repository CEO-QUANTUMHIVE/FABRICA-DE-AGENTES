"""Worker de LiveKit: cablea el cerebro con el canal de voz.

Este archivo no tiene logica de negocio. Solo arma la sesion con los
proveedores y arranca. Todo lo que el agente sabe viene de brain/.
"""

from __future__ import annotations

import logging

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    MetricsCollectedEvent,
    cli,
    metrics,
    room_io,
)
from livekit.plugins import silero

from motor_voz.brain.prompt import construir
from motor_voz.config import cargar
from motor_voz.voice.providers import llm as proveedor_llm
from motor_voz.voice.providers import stt as proveedor_stt
from motor_voz.voice.providers import tts as proveedor_tts
from motor_voz.voice.transformaciones import normalizar_para_voz

logger = logging.getLogger("motor-voz")


class Receptor(Agent):
    """Agente receptor de QuantumHive."""

    def __init__(self) -> None:
        super().__init__(instructions=construir())

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions="Saluda al visitante en una sola oracion corta y "
            "pregunta en que lo podes ayudar."
        )


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    config = cargar()
    ctx.log_context_fields = {"room": ctx.room.name}

    # Se imprime la config al arrancar cada sesion: sin esto no hay forma de
    # saber a simple vista si el worker esta corriendo el codigo nuevo o
    # quedo con el viejo porque no se reinicio.
    logger.info(
        "sesion nueva | voz=%s modelo=%s speed=%s temp=%s | normalizador=ACTIVO",
        config.fish_voice_id[:12] or "(default)",
        config.fish_model,
        config.fish_speed,
        config.fish_temperature,
    )

    session: AgentSession = AgentSession(
        stt=proveedor_stt.crear(config),
        llm=proveedor_llm.crear(config),
        tts=proveedor_tts.crear(config),
        # Groq Whisper no hace endpointing: sin VAD el agente no sabe
        # cuando terminaste de hablar, y sin eso no hay interrupcion.
        vad=silero.VAD.load(),
        # El TTS lee literal: sin esto pronuncia "24/7" como "24 septimo".
        # Pedirselo al LLM no alcanza — falla, y el error sale al aire.
        tts_text_transforms=["filter_markdown", "filter_emoji", normalizar_para_voz],
    )

    @session.on("metrics_collected")
    def _metricas(ev: MetricsCollectedEvent) -> None:
        metrics.log_metrics(ev.metrics)

    async def registrar_uso() -> None:
        logger.info(f"Uso de la sesion: {session.usage}")

    ctx.add_shutdown_callback(registrar_uso)

    await session.start(
        agent=Receptor(),
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )


if __name__ == "__main__":
    cli.run_app(server)
