"""Worker de LiveKit: cablea el cerebro con el canal de voz.

Este archivo no tiene logica de negocio. Solo arma la sesion con los
proveedores y arranca. Todo lo que el agente sabe viene de brain/.
"""

from __future__ import annotations

import dataclasses
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

from motor_voz.brain.prompt import construir
from motor_voz.config import cargar
from motor_voz.voice import motores
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


def motor_de_la_sala(nombre: str, por_defecto: str) -> str:
    """Extrae el motor del nombre de sala `demo-<motor>-<aleatorio>`.

    Si el nombre no sigue ese formato — una sala creada a mano, por ejemplo —
    se usa el motor de la configuracion.
    """
    partes = nombre.split("-")
    if len(partes) >= 3 and partes[0] == "demo" and partes[1] in motores.MOTORES:
        return partes[1]
    return por_defecto


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    # El motor viene en el nombre de la sala, que lo eligio el backend al
    # emitir el token. Como el token restringe a que sala se puede entrar,
    # el navegador no lo puede falsear: no puede pedir el plan premium por
    # su cuenta.
    config = dataclasses.replace(cargar(), motor=motor_de_la_sala(ctx.room.name, cargar().motor))
    ctx.log_context_fields = {"room": ctx.room.name, "motor": config.motor}

    # Se imprime la config al arrancar cada sesion: sin esto no hay forma de
    # saber a simple vista si el worker esta corriendo el codigo nuevo o
    # quedo con el viejo porque no se reinicio.
    logger.info(
        "sesion nueva | plan=%s motor=%s | voz=%s speed=%s temp=%s",
        motores.PLANES.get(config.motor, "?"),
        config.motor,
        config.fish_voice_id[:12] or "(default)",
        config.fish_speed,
        config.fish_temperature,
    )

    # Los motores de voz a voz generan el habla directamente: no pasan por
    # texto, asi que no tiene sentido normalizarles el texto ni darles TTS.
    extras: dict = {}
    if config.motor == "pipeline":
        # El TTS lee literal: sin esto pronuncia "24/7" como "24 septimo".
        # Pedirselo al LLM no alcanza — falla, y el error sale al aire.
        extras["tts_text_transforms"] = [
            "filter_markdown",
            "filter_emoji",
            normalizar_para_voz,
        ]

    session: AgentSession = AgentSession(**motores.componentes(config), **extras)

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
