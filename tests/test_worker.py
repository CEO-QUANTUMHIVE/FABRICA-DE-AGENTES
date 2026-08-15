"""El bucle del worker: que no se muera y que pare cuando se lo piden."""

from __future__ import annotations

import asyncio

import pytest

from motor_voz.channels import worker


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    """El bucle real espera segundos. Acá no."""
    monkeypatch.setattr(worker, "ESPERA_VACIO", 0.01)
    monkeypatch.setattr(worker, "ESPERA_TRABAJO", 0.01)
    monkeypatch.setattr(worker, "ESPERA_ERROR", 0.01)


async def test_las_dos_colas_corren_en_la_misma_vuelta(monkeypatch):
    """Lo que el procesador encola tiene que salir en el mismo ciclo, no en
    el siguiente: si no, cada respuesta espera una vuelta de mas."""
    orden = []

    async def procesar(config, deps, **kwargs):
        orden.append("procesar")
        return 1

    async def vaciar(config, deps, **kwargs):
        orden.append("enviar")
        return 1

    monkeypatch.setattr(worker.procesador, "procesar_pendientes", procesar)
    monkeypatch.setattr(worker.enviador, "vaciar_outbox", vaciar)

    hubo = await worker.una_vuelta(None, None, None)

    assert orden == ["procesar", "enviar"]
    assert hubo == 2


async def test_una_vuelta_que_explota_no_mata_el_bucle(monkeypatch):
    """Un error acá es la base caída o la red cortada, y las dos vuelven
    solas. Si el worker se muere, no vuelve hasta que alguien lo mire."""
    vueltas = []
    parar = asyncio.Event()

    async def una_vuelta(config, a, b):
        vueltas.append(1)
        if len(vueltas) < 3:
            raise RuntimeError("supabase caido")
        parar.set()
        return 0

    monkeypatch.setattr(worker, "una_vuelta", una_vuelta)
    monkeypatch.setattr(worker, "cargar", lambda: None)
    monkeypatch.setattr(
        worker.procesador.Dependencias, "de_produccion", classmethod(lambda cls: None)
    )
    monkeypatch.setattr(
        worker.enviador.Dependencias, "de_produccion", classmethod(lambda cls: None)
    )

    await asyncio.wait_for(worker.correr(parar), timeout=5)

    assert len(vueltas) == 3


async def test_pedirle_que_pare_lo_para(monkeypatch):
    parar = asyncio.Event()

    async def una_vuelta(config, a, b):
        parar.set()
        return 0

    monkeypatch.setattr(worker, "una_vuelta", una_vuelta)
    monkeypatch.setattr(worker, "cargar", lambda: None)
    monkeypatch.setattr(
        worker.procesador.Dependencias, "de_produccion", classmethod(lambda cls: None)
    )
    monkeypatch.setattr(
        worker.enviador.Dependencias, "de_produccion", classmethod(lambda cls: None)
    )

    await asyncio.wait_for(worker.correr(parar), timeout=5)
