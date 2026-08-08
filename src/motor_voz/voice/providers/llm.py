"""Generacion de respuestas con Groq.

El plugin aplica reasoning_effort='low' automaticamente a los modelos
gpt-oss, lo que reduce el consumo de tokens.
"""

from __future__ import annotations

from typing import Any

from livekit.plugins import groq

from motor_voz.config import Config


def opciones(config: Config) -> dict[str, Any]:
    """El default del plugin es llama-3.3: hay que pedir gpt-oss explicito."""
    return {
        "model": config.llm_model,
        "api_key": config.groq_api_key,
    }


def crear(config: Config) -> groq.LLM:
    return groq.LLM(**opciones(config))
