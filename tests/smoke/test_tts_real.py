"""Llama a la API real de Fish Audio y deja un wav para escuchar.

Correr con:  uv run pytest -m smoke tests/smoke/test_tts_real.py -v -s
"""

from __future__ import annotations

import pathlib
import wave

import pytest

from livekit.agents import utils

from motor_voz.config import cargar
from motor_voz.voice.providers import tts

FRASE = (
    "Hola, ¿cómo andás? Mirá, para el sábado tenemos lugar a las cuatro y media, "
    "¿te sirve? Si querés te lo reservo ahora y listo."
)
SALIDA = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "salida_tts.wav"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_sintetiza_la_frase_de_prueba():
    # El plugin de Fish usa la sesion aiohttp compartida del worker. Fuera del
    # worker hay que abrir ese contexto a mano o falla con APIConnectionError.
    async with utils.http_context.open():
        motor = tts.crear(cargar())

        trozos: list[bytes] = []
        sample_rate = 0
        canales = 1
        async with motor.synthesize(FRASE) as stream:
            async for evento in stream:
                trozos.append(evento.frame.data.tobytes())
                sample_rate = evento.frame.sample_rate
                canales = evento.frame.num_channels

    audio = b"".join(trozos)
    assert audio, "Fish devolvio audio vacio"

    with wave.open(str(SALIDA), "wb") as w:
        w.setnchannels(canales)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(audio)

    segundos = len(audio) / (sample_rate * canales * 2)
    bytes_facturados = len(FRASE.encode("utf-8"))
    print(f"\nAudio en {SALIDA}")
    print(f"  {segundos:.1f} s · {sample_rate} Hz · {canales} canal")
    print(f"  Facturado: {bytes_facturados} bytes UTF-8 "
          f"= USD {bytes_facturados * 0.015 / 1000:.5f}\n")
