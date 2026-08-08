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
    if not FIXTURE.exists():
        pytest.skip(
            f"Falta la grabacion local en {FIXTURE}. No se versiona: un wav "
            "limpio de una voz alcanza para clonarla y el repo es publico. "
            "Graba 10-15 segundos en espanol y dejala ahi."
        )

    motor = stt.crear(cargar())
    evento = await motor.recognize(cargar_wav(FIXTURE))
    texto = " ".join(alt.text for alt in evento.alternatives).lower()
    print(f"\nTranscripcion: {texto}\n")

    assert texto.strip(), "Groq devolvio texto vacio"

    # La grabacion real es el pitch de QuantumHive, en voz de Sergio.
    assert "negocio" in texto, f"No reconocio 'negocio' en: {texto}"
    assert "avatar" in texto, f"No reconocio 'avatar' en: {texto}"

    # Voseo rioplatense: si esto falla, el idioma quedo mal configurado.
    assert any(m in texto for m in ("acá", "aca", "vos", "unite")), (
        f"No aparece ninguna marca de voseo rioplatense en: {texto}"
    )

    # Sin la pista de vocabulario, Whisper escribe "quantum high".
    normalizado = texto.replace(" ", "")
    assert "quantumhive" in normalizado, (
        f"La marca se transcribio mal. Revisar STT_PROMPT. Texto: {texto}"
    )
