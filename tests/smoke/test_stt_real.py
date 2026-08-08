"""Llama a la API real de Groq. Cuesta fracciones de centavo.

Correr con:  uv run pytest -m smoke tests/smoke/test_stt_real.py -v -s
"""

from __future__ import annotations

import pathlib
import wave

import pytest

from livekit import rtc

from motor_voz.config import cargar
from motor_voz.voice.providers import stt

FIXTURE = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "hola_es.wav"


def cargar_wav(ruta: pathlib.Path) -> rtc.AudioFrame:
    """Lee un wav con la stdlib y arma un AudioFrame, sin helpers del SDK."""
    with wave.open(str(ruta), "rb") as w:
        assert w.getsampwidth() == 2, "El wav tiene que ser PCM de 16 bits"
        canales = w.getnchannels()
        frecuencia = w.getframerate()
        cantidad = w.getnframes()
        datos = w.readframes(cantidad)
    return rtc.AudioFrame(
        data=datos,
        sample_rate=frecuencia,
        num_channels=canales,
        samples_per_channel=cantidad,
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_transcribe_espanol_rioplatense():
    assert FIXTURE.exists(), f"Falta la grabacion de prueba en {FIXTURE}"

    motor = stt.crear(cargar())
    evento = await motor.recognize(cargar_wav(FIXTURE))
    texto = " ".join(alt.text for alt in evento.alternatives).lower()
    print(f"\nTranscripcion: {texto}\n")

    assert texto.strip(), "Groq devolvio texto vacio"
    assert "sabado" in texto or "sábado" in texto, f"No reconocio 'sabado' en: {texto}"
    assert "reservo" in texto, f"No reconocio 'reservo' en: {texto}"
