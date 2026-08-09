"""Unico punto del motor que lee variables de entorno.

Ningun otro modulo debe llamar a os.environ. Todo recibe un Config.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

OBLIGATORIAS = (
    "GROQ_API_KEY",
    "FISH_API_KEY",
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
)


VOCABULARIO_DE_MARCA = (
    "Conversacion en espanol rioplatense sobre QuantumHive: paginas web "
    "inteligentes, empleado virtual, catalogo vivo, avatar y clonacion de voz."
)
"""Pista de vocabulario para Whisper.

Sin esto, Groq transcribe la marca como "quantum high". Verificado el
2026-08-08 con una grabacion real de 60 segundos. Whisper usa este texto
como contexto previo y corrige los nombres propios.
"""


class ConfigInvalida(RuntimeError):
    """El entorno no tiene lo minimo para arrancar el motor."""


@dataclass(frozen=True)
class Config:
    groq_api_key: str
    fish_api_key: str
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    stt_model: str
    llm_model: str
    fish_model: str
    fish_latency_mode: str
    fish_voice_id: str
    fish_speed: float
    fish_temperature: float
    idioma: str
    stt_prompt: str
    max_session_seconds: int
    max_sesiones_por_ip_hora: int
    max_sesiones_por_dia: int
    api_puerto: int
    # Plan comercial: que motor de conversacion usa este tenant.
    motor: str
    # Plan medio - Gemini Live. Con gcp_project va por Vertex AI y consume
    # creditos de Google Cloud; con google_api_key es pago por uso.
    gemini_model: str
    gemini_voice: str
    gemini_temperature: float
    google_api_key: str
    gcp_project: str
    gcp_location: str
    # Plan premium - OpenAI Realtime. Con azure_endpoint consume creditos de
    # Azure; con openai_api_key es pago por uso.
    openai_model: str
    openai_voice: str
    openai_api_key: str
    azure_endpoint: str
    azure_deployment: str
    azure_api_key: str


def cargar(entorno: dict[str, str] | None = None) -> Config:
    e = dict(os.environ) if entorno is None else entorno

    faltantes = [n for n in OBLIGATORIAS if not (e.get(n) or "").strip()]
    if faltantes:
        raise ConfigInvalida(
            "Faltan variables de entorno obligatorias: "
            + ", ".join(faltantes)
            + ". Copiar .env.example a .env y completarlas."
        )

    return Config(
        groq_api_key=e["GROQ_API_KEY"].strip(),
        fish_api_key=e["FISH_API_KEY"].strip(),
        livekit_url=e["LIVEKIT_URL"].strip(),
        livekit_api_key=e["LIVEKIT_API_KEY"].strip(),
        livekit_api_secret=e["LIVEKIT_API_SECRET"].strip(),
        stt_model=e.get("GROQ_STT_MODEL", "whisper-large-v3-turbo"),
        llm_model=e.get("GROQ_LLM_MODEL", "openai/gpt-oss-20b"),
        stt_prompt=e.get("STT_PROMPT", VOCABULARIO_DE_MARCA),
        fish_model=e.get("FISH_MODEL", "s2.1-pro"),
        fish_latency_mode=e.get("FISH_LATENCY_MODE", "low"),
        fish_speed=float(e.get("FISH_SPEED", "1.25")),
        fish_temperature=float(e.get("FISH_TEMPERATURE", "1.0")),
        fish_voice_id=e.get("FISH_VOICE_ID", ""),
        idioma=e.get("IDIOMA", "es"),
        max_session_seconds=int(e.get("MAX_SESSION_SECONDS", "240")),
        max_sesiones_por_ip_hora=int(e.get("MAX_SESSIONS_PER_IP_HOUR", "20")),
        max_sesiones_por_dia=int(e.get("MAX_SESSIONS_PER_DAY", "300")),
        api_puerto=int(e.get("API_PUERTO", "8080")),
        motor=e.get("MOTOR", "pipeline").strip().lower(),
        gemini_model=e.get("GEMINI_MODEL", "gemini-live-2.5-flash-native-audio"),
        gemini_voice=e.get("GEMINI_VOICE", "Puck"),
        gemini_temperature=float(e.get("GEMINI_TEMPERATURE", "0.8")),
        google_api_key=e.get("GOOGLE_API_KEY", ""),
        gcp_project=e.get("GCP_PROJECT", ""),
        gcp_location=e.get("GCP_LOCATION", "us-east4"),
        openai_model=e.get("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1-mini"),
        openai_voice=e.get("OPENAI_VOICE", "alloy"),
        openai_api_key=e.get("OPENAI_API_KEY", ""),
        azure_endpoint=e.get("AZURE_OPENAI_ENDPOINT", ""),
        azure_deployment=e.get("AZURE_OPENAI_DEPLOYMENT", ""),
        azure_api_key=e.get("AZURE_OPENAI_API_KEY", ""),
    )
