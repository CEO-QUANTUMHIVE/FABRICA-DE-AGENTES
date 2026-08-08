"""Transcripcion con Groq Whisper."""

from __future__ import annotations

from typing import Any

from livekit.plugins import groq

from motor_voz.config import Config


def opciones(config: Config) -> dict[str, Any]:
    """El plugin trae language='en' por defecto: hay que forzar el idioma."""
    return {
        "model": config.stt_model,
        "language": config.idioma,
        "api_key": config.groq_api_key,
    }


def crear(config: Config) -> groq.STT:
    return groq.STT(**opciones(config))
