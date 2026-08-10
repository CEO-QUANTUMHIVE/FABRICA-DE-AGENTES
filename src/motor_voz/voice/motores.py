"""Los motores de conversacion disponibles. Cada uno es un plan comercial.

    basico    pipeline    Groq STT + Groq LLM + Fish TTS     ~USD 0,013/min
    medio     gemini      Gemini Live, voz a voz             ~USD 0,012/min
    premium   openai      OpenAI Realtime mini, voz a voz    ~USD 0,016/min

Precios verificados el 2026-08-09 contra las paginas oficiales de Google y
OpenAI. Contra lo que parecia, la voz a voz NO es cara: Gemini 3.1 Flash
Live cuesta lo mismo o menos que el pipeline, porque el pipeline paga TTS
de Fish por caracter y ahi se le va el 86% del costo.

El pipeline arma la respuesta en texto y despues la lee: la emocion se pierde
en esa frontera. Los de voz a voz generan el habla directamente, por eso
suenan naturales. Y ahora sabemos que eso no se paga mas caro.

Los dos premium se pueden facturar contra creditos en vez de tarjeta:
Gemini por Vertex AI (creditos de Google Cloud) y OpenAI por Azure OpenAI
(creditos de Azure). Ver `docs/motores-de-conversacion.md`.

Este modulo devuelve los componentes de la sesion. No decide el plan: eso
llega en la config del tenant.
"""

from __future__ import annotations

from typing import Any, NamedTuple

# Los tres van arriba, a nivel de modulo, aunque _gemini/_openai los usen
# recien mas abajo. livekit-agents registra cada plugin la primera vez que
# se importa, y exige que ese registro pase por el hilo principal del
# worker. Si el import quedara adentro de _gemini/_openai, la primera vez
# que se pide ese motor el import ocurre DENTRO del hilo del job, y
# revienta con "Plugins must be registered on the main thread". Verificado
# el 2026-08-10 con el traceback real en produccion.
from google.genai import types as genai_types
from livekit.plugins import google, silero
from livekit.plugins.openai import realtime as openai_realtime
from openai.types.realtime.realtime_audio_input_turn_detection import ServerVad

from motor_voz.config import Config
from motor_voz.voice.providers import llm as proveedor_llm
from motor_voz.voice.providers import stt as proveedor_stt
from motor_voz.voice.providers import tts as proveedor_tts

MOTORES = ("pipeline", "gemini", "openai")

PLANES = {
    "pipeline": "basico",
    "gemini": "medio",
    "openai": "premium",
}

class Voz(NamedTuple):
    """Una voz del catalogo, como la ve el visitante.

    El genero no es un adorno: el selector agrupa por genero, y esa
    variedad es parte de lo que se le esta vendiendo al cliente.
    """

    nombre: str
    genero: str  # "m" | "f"


# Las voces prearmadas que trae Gemini Live (verificado en
# livekit.plugins.google.realtime.api_proto.Voice, el 2026-08-10). Son
# nombres de estrellas en ingles, asi que el catalogo que ve el visitante
# usa nombres argentinos en su lugar — los mismos que ya eligio
# QUANTUM-ASISTENTE- (apps/desktop/src/orbe/Orbe.tsx, rama
# agent/navegador-integrado, constante NOMBRE_VOZ) para no duplicar el
# criterio en dos lugares. La clave sigue siendo el nombre real: es lo
# unico que entiende la API de Google.
VOCES_GEMINI = {
    "Puck": Voz("Mateo", "m"),
    "Charon": Voz("Joaco", "m"),
    "Fenrir": Voz("Nico", "m"),
    "Orus": Voz("Tomás", "m"),
    "Kore": Voz("Delfi", "f"),
    "Aoede": Voz("Camila", "f"),
    "Leda": Voz("Sofía", "f"),
    "Zephyr": Voz("Mora", "f"),
}
VOZ_GEMINI_POR_DEFECTO = "Puck"

# Las diez voces de OpenAI Realtime, verificadas contra el SDK instalado
# (.venv/Lib/site-packages/openai/types/realtime/realtime_audio_config_output.py,
# el 2026-08-09). A diferencia de Gemini, aca la clave ya es el nombre que
# entiende la API (todo minuscula, sin nombres de estrellas de por medio),
# pero el criterio para el catalogo que ve el visitante es el mismo: nombres
# argentinos, distintos a los de VOCES_GEMINI para no confundir los dos
# selectores.
VOCES_OPENAI = {
    "alloy": Voz("Bruno", "m"),
    "ash": Voz("Facu", "m"),
    "ballad": Voz("Santi", "m"),
    "coral": Voz("Juli", "f"),
    "echo": Voz("Lauti", "m"),
    "sage": Voz("Flor", "f"),
    "shimmer": Voz("Vale", "f"),
    "verse": Voz("Thiago", "m"),
    "marin": Voz("Pili", "f"),
    "cedar": Voz("Caro", "f"),
}
VOZ_OPENAI_POR_DEFECTO = "marin"  # el default del plugin instalado


def catalogo_de_voces(motor: str) -> tuple[dict[str, Voz], str]:
    """Catalogo de voces y voz por defecto del motor pedido.

    El pipeline no entra aca: su voz es la clonada de Fish, que se
    configura por tenant y no se elige de una lista.
    """
    if motor == "gemini":
        return VOCES_GEMINI, VOZ_GEMINI_POR_DEFECTO
    if motor == "openai":
        return VOCES_OPENAI, VOZ_OPENAI_POR_DEFECTO
    return {}, ""


def ruta_de_muestra(motor: str, clave: str) -> str:
    """Donde vive el saludo pregrabado de una voz, relativo al widget.

    Antes, tocar un nombre en el selector reconectaba la sesion entera y se
    pagaba una sintesis; con 10 voces, un curioso quemaba 10 saludos en
    medio minuto. Ahora suena este archivo y cuesta cero.

    Relativa a proposito: el widget la resuelve contra su propio origen, asi
    sirve igual en local que en voz.quantumhive.com.ar. Los genera
    `scripts/generar_muestras.py` y `tests/test_muestras.py` verifica que no
    falte ninguna.
    """
    return f"assets/muestras/{motor}-{clave}.mp3"


class MotorNoDisponible(RuntimeError):
    """El motor pedido existe pero le faltan credenciales para funcionar."""


def componentes(config: Config, voice_id_override: str = "") -> dict[str, Any]:
    """Devuelve los kwargs de AgentSession del motor configurado.

    `voice_id_override` es la voz del tenant ya resuelto (spec S8). Solo
    el pipeline la usa hoy: Gemini y OpenAI hablan con una voz de catalogo
    fija (`gemini_voice`/`openai_voice`), no con una voz clonada.
    """
    if config.motor not in MOTORES:
        raise MotorNoDisponible(
            f"Motor '{config.motor}' desconocido. Validos: {', '.join(MOTORES)}."
        )
    return _CONSTRUCTORES[config.motor](config, voice_id_override)


def _pipeline(config: Config, voice_id_override: str = "") -> dict[str, Any]:
    return {
        "stt": proveedor_stt.crear(config),
        "llm": proveedor_llm.crear(config),
        "tts": proveedor_tts.crear(config, voice_id_override),
        # Groq Whisper no hace endpointing: sin VAD no hay deteccion de turno
        # ni interrupcion. Los defaults de silero (0.55 s de silencio, umbral
        # 0.5) cortan con cualquier ruido de fondo: el agente se callaba
        # creyendo que le hablaban. Los tres motores usan los mismos valores
        # de Config para que la sensibilidad se sienta igual en los tres.
        "vad": silero.VAD.load(
            min_silence_duration=config.vad_silencio_ms / 1000,
            prefix_padding_duration=config.vad_relleno_ms / 1000,
            activation_threshold=config.vad_umbral,
        ),
    }


def opciones_gemini(config: Config) -> dict[str, Any]:
    """Vertex AI factura al proyecto de Google Cloud, o sea a los creditos.

    Con `GOOGLE_API_KEY` va por la API de pago por uso, contra tarjeta.
    """
    base: dict[str, Any] = {
        "model": config.gemini_model,
        "voice": config.gemini_voice,
        "temperature": config.gemini_temperature,
        # Sensibilidad baja para que no se auto-interrumpa al escucharse por
        # los parlantes del visitante, ni con ruido de fondo. Mismo criterio
        # que QUANTUM-ASISTENTE-, que ya habia pasado por este problema.
        "realtime_input_config": genai_types.RealtimeInputConfig(
            automatic_activity_detection=genai_types.AutomaticActivityDetection(
                start_of_speech_sensitivity=genai_types.StartSensitivity.START_SENSITIVITY_LOW,
                end_of_speech_sensitivity=genai_types.EndSensitivity.END_SENSITIVITY_LOW,
                prefix_padding_ms=config.vad_relleno_ms,
                silence_duration_ms=config.vad_silencio_ms,
            )
        ),
    }
    if config.gcp_project.strip():
        return base | {
            "vertexai": True,
            "project": config.gcp_project.strip(),
            "location": config.gcp_location.strip() or "us-central1",
        }
    if config.google_api_key.strip():
        return base | {"api_key": config.google_api_key.strip()}
    raise MotorNoDisponible(
        "El motor Gemini necesita GCP_PROJECT (para consumir creditos de Google "
        "Cloud via Vertex AI) o GOOGLE_API_KEY (pago por uso). Falta ambos."
    )


def _gemini(config: Config, voice_id_override: str = "") -> dict[str, Any]:
    # Acepta el override y no lo usa: Gemini habla con una voz de su catalogo,
    # no con una clonada. El parametro esta para que el despacho por
    # diccionario siga siendo uniforme entre los tres motores.
    return {"llm": google.beta.realtime.RealtimeModel(**opciones_gemini(config))}


def opciones_openai(config: Config) -> dict[str, Any]:
    """Azure OpenAI factura contra los creditos de Azure.

    Con `OPENAI_API_KEY` va directo a OpenAI, contra tarjeta.
    """
    base: dict[str, Any] = {
        "voice": config.openai_voice,
        # Mismo motivo que en Gemini: el umbral por defecto corta con
        # cualquier ruido. Aca la sensibilidad es un numero (mas alto =
        # menos sensible) en vez de un enum.
        "turn_detection": ServerVad(
            type="server_vad",
            threshold=config.vad_umbral,
            prefix_padding_ms=config.vad_relleno_ms,
            silence_duration_ms=config.vad_silencio_ms,
        ),
    }
    if config.azure_endpoint.strip():
        return base | {
            "_azure": True,
            "azure_endpoint": config.azure_endpoint.strip(),
            "azure_deployment": config.azure_deployment.strip(),
            "api_key": config.azure_api_key.strip(),
        }
    if config.openai_api_key.strip():
        return base | {"model": config.openai_model, "api_key": config.openai_api_key.strip()}
    raise MotorNoDisponible(
        "El motor OpenAI necesita AZURE_OPENAI_ENDPOINT (para consumir creditos "
        "de Azure) o OPENAI_API_KEY (pago por uso). Falta ambos."
    )


def _openai(config: Config, voice_id_override: str = "") -> dict[str, Any]:
    # Mismo criterio que _gemini: la voz sale del catalogo de OpenAI.
    opts = opciones_openai(config)
    if opts.pop("_azure", False):
        return {"llm": openai_realtime.RealtimeModel.with_azure(**opts)}
    return {"llm": openai_realtime.RealtimeModel(**opts)}


_CONSTRUCTORES = {
    "pipeline": _pipeline,
    "gemini": _gemini,
    "openai": _openai,
}
