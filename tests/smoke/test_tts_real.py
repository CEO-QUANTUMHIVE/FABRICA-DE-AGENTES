"""Llama a la API real de Fish Audio y deja un wav para escuchar.

Correr con:  uv run pytest -m smoke tests/smoke/test_tts_real.py -v -s
"""

from __future__ import annotations

import pathlib

import pytest

from motor_voz.config import cargar
from motor_voz.voice.providers import tts

FRASE = (
    "Hola, como andas? Mira, para el sabado tenemos lugar a las cuatro y media, "
    "te sirve? Si queres te lo reservo ahora y listo."
)
SALIDA = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "salida_tts.wav"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_sintetiza_la_frase_de_prueba():
    motor = tts.crear(cargar())

    trozos: list[bytes] = []
    async with motor.synthesize(FRASE) as stream:
        async for evento in stream:
            trozos.append(evento.frame.data.tobytes())

    audio = b"".join(trozos)
    assert audio, "Fish devolvio audio vacio"

    SALIDA.write_bytes(audio)
    print(f"\nAudio generado en {SALIDA} ({len(audio)} bytes)\n")
    print(f"Bytes de texto facturados: {len(FRASE.encode('utf-8'))}")
