"""Transcripcion con Groq Whisper."""

from __future__ import annotations

from typing import Any

from livekit.plugins import groq

from motor_voz.config import Config


def opciones(config: Config) -> dict[str, Any]:
    """El plugin trae language='en' por defecto: hay que forzar el idioma.

    `prompt` es la pista de vocabulario de Whisper. Sin ella la marca se
    transcribe como "quantum high": comprobado con audio real.
    """
    opts: dict[str, Any] = {
        "model": config.stt_model,
        "language": config.idioma,
        "api_key": config.groq_api_key,
    }
    if config.stt_prompt.strip():
        opts["prompt"] = config.stt_prompt.strip()
    return opts


def crear(config: Config) -> groq.STT:
    return groq.STT(**opciones(config))
