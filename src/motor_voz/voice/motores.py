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

from typing import Any

# Los tres van arriba, a nivel de modulo, aunque _gemini/_openai los usen
# recien mas abajo. livekit-agents registra cada plugin la primera vez que
# se importa, y exige que ese registro pase por el hilo principal del
# worker. Si el import quedara adentro de _gemini/_openai, la primera vez
# que se pide ese motor el import ocurre DENTRO del hilo del job, y
# revienta con "Plugins must be registered on the main thread". Verificado
# el 2026-08-10 con el traceback real en produccion.
from livekit.plugins import google, silero
from livekit.plugins.openai import realtime as openai_realtime

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

# Las voces prearmadas que trae Gemini Live (verificado en
# livekit.plugins.google.realtime.api_proto.Voice, el 2026-08-10). Son
# nombres de estrellas en ingles, asi que el catalogo que ve el visitante
# usa nombres argentinos en su lugar — los mismos que ya eligio
# QUANTUM-ASISTENTE- (apps/desktop/src/orbe/Orbe.tsx, rama
# agent/navegador-integrado, constante NOMBRE_VOZ) para no duplicar el
# criterio en dos lugares. La clave sigue siendo el nombre real: es lo
# unico que entiende la API de Google.
VOCES_GEMINI = {
    "Puck": "Mateo",
    "Charon": "Joaco",
    "Fenrir": "Nico",
    "Orus": "Tomás",
    "Kore": "Delfi",
    "Aoede": "Camila",
    "Leda": "Sofía",
    "Zephyr": "Mora",
}
VOZ_GEMINI_POR_DEFECTO = "Puck"


class MotorNoDisponible(RuntimeError):
    """El motor pedido existe pero le faltan credenciales para funcionar."""


def componentes(config: Config) -> dict[str, Any]:
    """Devuelve los kwargs de AgentSession del motor configurado."""
    if config.motor not in MOTORES:
        raise MotorNoDisponible(
            f"Motor '{config.motor}' desconocido. Validos: {', '.join(MOTORES)}."
        )
    return _CONSTRUCTORES[config.motor](config)


def _pipeline(config: Config) -> dict[str, Any]:
    return {
        "stt": proveedor_stt.crear(config),
        "llm": proveedor_llm.crear(config),
        "tts": proveedor_tts.crear(config),
        # Groq Whisper no hace endpointing: sin VAD no hay deteccion de turno
        # ni interrupcion.
        "vad": silero.VAD.load(),
    }


def opciones_gemini(config: Config) -> dict[str, Any]:
    """Vertex AI factura al proyecto de Google Cloud, o sea a los creditos.

    Con `GOOGLE_API_KEY` va por la API de pago por uso, contra tarjeta.
    """
    base: dict[str, Any] = {
        "model": config.gemini_model,
        "voice": config.gemini_voice,
        "temperature": config.gemini_temperature,
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


def _gemini(config: Config) -> dict[str, Any]:
    return {"llm": google.beta.realtime.RealtimeModel(**opciones_gemini(config))}


def opciones_openai(config: Config) -> dict[str, Any]:
    """Azure OpenAI factura contra los creditos de Azure.

    Con `OPENAI_API_KEY` va directo a OpenAI, contra tarjeta.
    """
    base: dict[str, Any] = {"voice": config.openai_voice}
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


def _openai(config: Config) -> dict[str, Any]:
    opts = opciones_openai(config)
    if opts.pop("_azure", False):
        return {"llm": openai_realtime.RealtimeModel.with_azure(**opts)}
    return {"llm": openai_realtime.RealtimeModel(**opts)}


_CONSTRUCTORES = {
    "pipeline": _pipeline,
    "gemini": _gemini,
    "openai": _openai,
}
