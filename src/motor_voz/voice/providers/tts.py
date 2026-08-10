"""Sintesis de voz con Fish Audio.

Este modulo es el unico punto que conoce a Fish. Cuando se agregue el pool
de proveedores del spec, el router vive aca y el resto del motor no se entera.
"""

from __future__ import annotations

from typing import Any

from livekit.plugins import fishaudio

from motor_voz.config import Config


def opciones(config: Config, voice_id_override: str = "") -> dict[str, Any]:
    """El default de latency_mode es 'balanced'; para Live queremos 'low'.

    `speed` y `temperature` salen de configuracion porque son de oido, no
    de calculo: se ajustan escuchando. `voice_id_override` es la voz del
    tenant resuelto (spec S8, "cada tenant habla con su propia voz");
    gana sobre `FISH_VOICE_ID` de Config, que queda como fallback para
    cuando no hay tenant (fases 0-4, desarrollo local).
    """
    opts: dict[str, Any] = {
        "model": config.fish_model,
        "latency_mode": config.fish_latency_mode,
        "speed": config.fish_speed,
        "temperature": config.fish_temperature,
        "api_key": config.fish_api_key,
    }
    voice_id = voice_id_override.strip() or config.fish_voice_id.strip()
    if voice_id:
        opts["voice_id"] = voice_id
    return opts


def crear(config: Config, voice_id_override: str = "") -> fishaudio.TTS:
    return fishaudio.TTS(**opciones(config, voice_id_override))
