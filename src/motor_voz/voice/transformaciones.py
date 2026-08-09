"""Adaptador entre el normalizador de texto y el pipeline de LiveKit.

LiveKit entrega el texto del LLM en pedazos, a medida que el modelo lo va
escribiendo. Un reemplazo aplicado pedazo por pedazo se rompe cuando el
patron queda partido al medio: si "24" llega en un chunk y "/7" en el
siguiente, ninguno de los dos matchea y el error pasa igual.

Por eso se acumula hasta un limite de frase antes de normalizar y emitir.
"""

from __future__ import annotations

from collections.abc import AsyncIterable

from motor_voz.brain.normalizar import normalizar

# Se corta en puntuacion fuerte: ahi ya no hay patron que pueda quedar partido.
LIMITES = ".!?…\n"


async def normalizar_para_voz(texto: AsyncIterable[str]) -> AsyncIterable[str]:
    """Normaliza el texto por frases completas antes de mandarlo al TTS."""
    buffer = ""

    async for pedazo in texto:
        buffer += pedazo
        while True:
            corte = _primer_limite(buffer)
            if corte is None:
                break
            frase, buffer = buffer[: corte + 1], buffer[corte + 1 :]
            limpia = normalizar(frase)
            if limpia:
                yield limpia + " "

    if buffer.strip():
        limpia = normalizar(buffer)
        if limpia:
            yield limpia


def _primer_limite(texto: str) -> int | None:
    for i, c in enumerate(texto):
        if c in LIMITES:
            return i
    return None
