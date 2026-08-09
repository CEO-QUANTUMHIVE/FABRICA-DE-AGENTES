"""El texto del LLM llega en pedazos. Estos tests prueban que eso no rompe
la normalizacion, que es el modo de falla que un test sobre texto completo
nunca encontraria.
"""

from collections.abc import AsyncIterable

import pytest

from motor_voz.voice.transformaciones import normalizar_para_voz


async def flujo(*pedazos: str) -> AsyncIterable[str]:
    for p in pedazos:
        yield p


async def recolectar(*pedazos: str) -> str:
    return "".join([x async for x in normalizar_para_voz(flujo(*pedazos))])


@pytest.mark.asyncio
async def test_normaliza_una_frase_entera():
    r = await recolectar("Atiende 24/7 sin parar.")
    assert "las veinticuatro horas" in r
    assert "/" not in r


@pytest.mark.asyncio
async def test_el_patron_partido_al_medio_igual_se_normaliza():
    """El caso que rompe una implementacion ingenua: '24' y '/7' en chunks
    distintos. Sin buffer, ningun pedazo matchea y el error pasa igual."""
    r = await recolectar("Atiende 24", "/", "7 sin parar.")
    assert "las veinticuatro horas" in r
    assert "/" not in r


@pytest.mark.asyncio
async def test_un_numero_partido_letra_por_letra():
    r = await recolectar("Sale ", "1", "5", "0", "0", " pesos.")
    assert "mil quinientos" in r


@pytest.mark.asyncio
async def test_emite_frase_por_frase_y_no_espera_el_final():
    """Si esperara todo el texto para emitir, el agente tardaria en arrancar
    a hablar y perderiamos la latencia baja."""
    piezas = [x async for x in normalizar_para_voz(flujo("Hola. ", "Chau."))]
    assert len(piezas) >= 2


@pytest.mark.asyncio
async def test_no_pierde_el_final_sin_puntuacion():
    r = await recolectar("Esto no termina en punto")
    assert "termina en punto" in r


@pytest.mark.asyncio
async def test_conserva_los_signos_de_entonacion():
    r = await recolectar("¡Claro que sí! ", "¿Te lo muestro?")
    assert "¡" in r and "!" in r
    assert "¿" in r and "?" in r


@pytest.mark.asyncio
async def test_flujo_vacio_no_rompe():
    assert await recolectar() == ""
    assert await recolectar("", "  ") == ""
