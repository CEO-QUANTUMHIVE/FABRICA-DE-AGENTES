"""Llama a la API real de Groq.

Correr con:  uv run pytest -m smoke tests/smoke/test_llm_real.py -v -s
"""

from __future__ import annotations

import pytest

from motor_voz.config import cargar
from motor_voz.voice.providers import llm


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_responde_en_espanol_y_breve():
    from livekit.agents.llm import ChatContext

    modelo = llm.crear(cargar())
    contexto = ChatContext()
    contexto.add_message(
        role="system",
        content="Sos el asistente de QuantumHive. Respondes en espanol rioplatense, "
        "en una sola oracion corta, sin emojis ni markdown.",
    )
    contexto.add_message(role="user", content="Hola, que hacen ustedes?")

    partes: list[str] = []
    async with modelo.chat(chat_ctx=contexto) as stream:
        async for fragmento in stream:
            if fragmento.delta and fragmento.delta.content:
                partes.append(fragmento.delta.content)

    respuesta = "".join(partes).strip()
    print(f"\nRespuesta: {respuesta}\n")

    assert respuesta, "El modelo devolvio texto vacio"
    assert len(respuesta) < 400, f"Demasiado largo para voz ({len(respuesta)} chars)"
    assert "*" not in respuesta, "Devolvio markdown, que no se puede hablar"
