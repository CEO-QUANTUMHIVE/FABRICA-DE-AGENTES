"""El proceso que mueve las dos colas.

    python -m motor_voz.channels.worker

Corre aparte de la API a proposito. El webhook tiene que devolver 200 en
milisegundos o Meta reintenta; generar una respuesta con un LLM y hacer un
POST al Graph API no entra en ese presupuesto.

Es un bucle simple con sondeo, no una cola con notificaciones. A la escala de
hoy —decenas de mensajes por dia— un `LISTEN/NOTIFY` o un broker suman una
pieza que se puede caer a cambio de un segundo de latencia. Cuando el volumen
lo pida, lo unico que cambia es este archivo: las funciones que hacen el
trabajo no saben quien las llama.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from motor_voz.channels import enviador, procesador
from motor_voz.config import cargar

logger = logging.getLogger("motor-voz.worker")

ESPERA_VACIO = 3.0
"""Segundos entre vueltas cuando no habia nada que hacer."""

ESPERA_TRABAJO = 0.2
"""Si el lote vino lleno probablemente haya mas: se vuelve casi enseguida."""

ESPERA_ERROR = 10.0
"""Si Supabase esta caido, insistir cada tres segundos no lo levanta."""


async def una_vuelta(config, deps_procesador, deps_enviador) -> int:
    """Procesa entrantes y vacia salientes. Devuelve cuanto trabajo hubo.

    Las dos colas van en la misma vuelta y en este orden: lo que el
    procesador encola sale en el mismo ciclo, sin esperar al siguiente.
    """
    procesados = await procesador.procesar_pendientes(config, deps_procesador)
    enviados = await enviador.vaciar_outbox(config, deps_enviador)
    if procesados or enviados:
        logger.info("worker | procesados=%s enviados=%s", procesados, enviados)
    return procesados + enviados


async def correr(parar: asyncio.Event | None = None) -> None:
    config = cargar()
    deps_procesador = procesador.Dependencias.de_produccion()
    deps_enviador = enviador.Dependencias.de_produccion()
    parar = parar or asyncio.Event()

    logger.info("worker | arrancando")
    while not parar.is_set():
        try:
            hubo = await una_vuelta(config, deps_procesador, deps_enviador)
            espera = ESPERA_TRABAJO if hubo else ESPERA_VACIO
        except Exception:
            # Nada puede matar el bucle. Un error acá es la base caída o la
            # red cortada, y las dos vuelven solas.
            logger.exception("worker | vuelta fallida")
            espera = ESPERA_ERROR

        try:
            await asyncio.wait_for(parar.wait(), timeout=espera)
        except TimeoutError:
            pass

    logger.info("worker | parando")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    async def arrancar() -> None:
        parar = asyncio.Event()
        bucle = asyncio.get_running_loop()
        for señal in (signal.SIGINT, signal.SIGTERM):
            try:
                bucle.add_signal_handler(señal, parar.set)
            except NotImplementedError:
                # Windows no los soporta. En la VM, que es Linux, si.
                pass
        await correr(parar)

    asyncio.run(arrancar())


if __name__ == "__main__":
    main()
