"""Worker de LiveKit: cablea el cerebro con el canal de voz.

Este archivo no tiene logica de negocio. Solo arma la sesion con los
proveedores y arranca. Todo lo que el agente sabe viene de brain/.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobExecutorType,
    MetricsCollectedEvent,
    cli,
    metrics,
    room_io,
)

from motor_voz.brain.contexto import construir_contexto
from motor_voz.brain.tenants import repositorio
from motor_voz.brain.tenants.resolver import tenant_de_la_sala
from motor_voz.config import cargar
from motor_voz.voice import herramientas, motores
from motor_voz.voice.transformaciones import normalizar_para_voz

logger = logging.getLogger("motor-voz")

def modo_de_metadata(metadata: str) -> str:
    """Lee el modo firmado; ausente, roto o desconocido siempre es publico."""
    try:
        datos = json.loads(metadata or "{}")
    except (json.JSONDecodeError, TypeError):
        return "publico"
    return "interno" if isinstance(datos, dict) and datos.get("modo") == "interno" else "publico"


class Receptor(Agent):
    """Agente receptor de un tenant.

    Recibe el prompt y las tools ya armados en vez de armarlos: quien decide
    que dice es brain/contexto.py y que puede hacer es brain/tools/registro.py.
    Este archivo sigue sin tener logica de negocio.
    """

    def __init__(self, instructions: str, tools: list | None = None) -> None:
        super().__init__(instructions=instructions, tools=tools or [])

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions="Saluda al visitante en una sola oracion corta y "
            "pregunta en que lo podes ayudar."
        )


def motor_de_la_sala(nombre: str, por_defecto: str) -> str:
    """Extrae el motor de `demo-<tenant>-<motor>-<voz>-<aleatorio>`.

    El tenant entro adelante, asi que el motor se corrio un lugar a la
    derecha. Los slugs de tenant no llevan guiones (`demo_capilar` usa
    guion bajo), asi que partir por `-` sigue siendo seguro.

    Si el nombre no sigue ese formato — una sala creada a mano, o una del
    formato viejo sin tenant — se usa el motor de la configuracion.
    """
    partes = nombre.split("-")
    if len(partes) >= 5 and partes[0] == "demo" and partes[2] in motores.MOTORES:
        return partes[2]
    return por_defecto


def voz_de_la_sala(nombre: str, motor: str, por_defecto: str) -> str:
    """Extrae la voz de `demo-<tenant>-<motor>-<voz>-<aleatorio>`.

    Se valida contra el catalogo real del motor YA resuelto (no contra el
    de otro motor): un nombre de sala armado a mano no puede pedirle a la
    API una voz que no existe, ni colar la voz de un motor en otro. Los
    motores sin catalogo (pipeline) siempre caen al default, porque
    servidor.py deja ese campo vacio a proposito.
    """
    catalogo, _ = motores.catalogo_de_voces(motor)
    partes = nombre.split("-")
    if len(partes) >= 5 and partes[0] == "demo" and partes[3] in catalogo:
        return partes[3]
    return por_defecto


# Medido: importar livekit y los plugins cuesta 440 MB, el modelo VAD 16 MB
# mas, y cada conversacion apenas 12 MB. O sea que el costo es casi todo
# fijo y se paga UNA vez por proceso.
#
# Por eso estos tres parametros no se dejan en su default:
#
# - num_idle_processes tiene prod_default=4, o sea cuatro procesos esperando
#   trabajo a 470 MB cada uno: 1,9 GB parado sin atender a nadie. En una VM
#   chica se muere antes de la primera llamada.
# - job_executor_type=THREAD hace que las sesiones compartan el proceso y
#   con el los 470 MB. Con procesos, cada sesion los pagaria de nuevo.
# - job_memory_warn_mb viene en 1000, mas que la RAM de la VM entera: avisa
#   cuando ya es tarde.
#
# Todo se puede subir por entorno cuando la maquina crezca.
server = AgentServer(
    job_executor_type=JobExecutorType.THREAD,
    num_idle_processes=int(os.environ.get("AGENTE_PROCESOS_OCIOSOS", "0")),
    job_memory_warn_mb=int(os.environ.get("AGENTE_AVISO_MEMORIA_MB", "600")),
)


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    # El motor viene en el nombre de la sala, que lo eligio el backend al
    # emitir el token. Como el token restringe a que sala se puede entrar,
    # el navegador no lo puede falsear: no puede pedir el plan premium por
    # su cuenta.
    base = cargar()
    motor = motor_de_la_sala(ctx.room.name, base.motor)
    # La voz vive en un campo de Config distinto por motor (gemini_voice,
    # openai_voice): cada plugin espera la suya. Solo se pisa el campo del
    # motor que efectivamente corre esta sesion; el otro se queda con el
    # default de config.py, aunque no se vaya a usar.
    gemini_voice = base.gemini_voice
    openai_voice = base.openai_voice
    if motor == "gemini":
        gemini_voice = voz_de_la_sala(ctx.room.name, motor, base.gemini_voice)
    elif motor == "openai":
        openai_voice = voz_de_la_sala(ctx.room.name, motor, base.openai_voice)
    config = dataclasses.replace(
        base,
        motor=motor,
        gemini_voice=gemini_voice,
        openai_voice=openai_voice,
    )
    # El tenant tambien viaja en el nombre de sala, adelante del motor. De el
    # salen las dos cosas que hacen que un cliente suene como el mismo: con
    # que voz habla el agente, y quien dice ser.
    tenant = await repositorio.obtener_tenant(config, tenant_de_la_sala(ctx.room.name))
    voice_id_override = tenant.voz.voice_id if tenant.voz else ""
    participante = await ctx.wait_for_participant()
    modo = modo_de_metadata(participante.metadata)

    ctx.log_context_fields = {
        "room": ctx.room.name,
        "motor": config.motor,
        "tenant": tenant.slug,
        "modo": modo,
    }

    # Se imprime la config al arrancar cada sesion: sin esto no hay forma de
    # saber a simple vista si el worker esta corriendo el codigo nuevo o
    # quedo con el viejo porque no se reinicio.
    logger.info(
        "sesion nueva | tenant=%s modo=%s plan=%s motor=%s | voz=%s speed=%s temp=%s "
        "| voz_gemini=%s voz_openai=%s",
        tenant.slug,
        modo,
        motores.PLANES.get(config.motor, "?"),
        config.motor,
        (voice_id_override or config.fish_voice_id)[:12] or "(default)",
        config.fish_speed,
        config.fish_temperature,
        config.gemini_voice,
        config.openai_voice,
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

    # Por que se toca la interrupcion:
    #
    # El default de livekit-agents es `min_words: 0`, o sea que alcanza UNA
    # palabra para callar al agente. Y Whisper, cuando le llega ruido o el
    # propio audio del agente colado por el microfono, no devuelve vacio:
    # alucina una palabra suelta que suena a algo ("gracias", "subtitulos").
    # Con el default esa palabra inventada interrumpe al agente y despues lo
    # hace contestarle a la nada — que es el sintoma de "se escucha a si
    # mismo y se responde solo".
    #
    # Pidiendo dos palabras, un fragmento alucinado ya no alcanza.
    # `resume_false_interruption` viene prendido de fabrica: si se callo por
    # una interrupcion que no era, retoma en vez de quedarse mudo.
    extras["turn_handling"] = {
        "interruption": {
            "min_words": int(os.environ.get("AGENTE_PALABRAS_INTERRUPCION", "2")),
            "min_duration": float(os.environ.get("AGENTE_DURACION_INTERRUPCION", "0.6")),
        }
    }

    session: AgentSession = AgentSession(
        **motores.componentes(config, voice_id_override), **extras
    )

    @session.on("metrics_collected")
    def _metricas(ev: MetricsCollectedEvent) -> None:
        metrics.log_metrics(ev.metrics)

    async def registrar_uso() -> None:
        logger.info(f"Uso de la sesion: {session.usage}")

    ctx.add_shutdown_callback(registrar_uso)

    prompt = construir_contexto(tenant, motor=config.motor, canal="web")
    # El modo decide que puede HACER el agente, no solo que dice. Llega firmado
    # por la API despues de validar sesion y pertenencia al tenant.
    tools = herramientas.para(modo, tenant, config, ctx.room.name)
    await session.start(
        agent=Receptor(prompt, tools),
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )


if __name__ == "__main__":
    cli.run_app(server)
