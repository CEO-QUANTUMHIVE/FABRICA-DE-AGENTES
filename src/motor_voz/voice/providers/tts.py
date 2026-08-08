"""Sintesis de voz con Fish Audio.

Este modulo es el unico punto que conoce a Fish. Cuando se agregue el pool
de proveedores del spec, el router vive aca y el resto del motor no se entera.
"""

from __future__ import annotations

from typing import Any

from livekit.plugins import fishaudio

from motor_voz.config import Config


def opciones(config: Config) -> dict[str, Any]:
    """El default de latency_mode es 'balanced'; para Live queremos 'low'."""
    opts: dict[str, Any] = {
        "model": config.fish_model,
        "latency_mode": config.fish_latency_mode,
        "api_key": config.fish_api_key,
    }
    if config.fish_voice_id.strip():
        opts["voice_id"] = config.fish_voice_id.strip()
    return opts


def crear(config: Config) -> fishaudio.TTS:
    return fishaudio.TTS(**opciones(config))
