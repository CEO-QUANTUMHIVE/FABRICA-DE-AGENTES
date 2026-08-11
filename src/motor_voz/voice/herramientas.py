"""Adaptador entre el registro de tools del cerebro y el formato de livekit.

Vive en `voice/` y no en `brain/` porque importa livekit, y el cerebro no
puede. Asi el registro sigue sirviendo igual para WhatsApp, que no pasa por
LiveKit.

Lo que hace, en una frase: toma los nombres que el registry permite, les ata
el tenant y la sala, y los entrega como tools que el modelo puede llamar.

**El modelo nunca ve el tenant ni la sala.** Se le sacan de la firma antes de
entregarle la tool. Si los viera podria pasarle el de otro negocio, y el
modelo le hace caso a quien le habla.
"""

from __future__ import annotations

import functools
import inspect
import logging
from collections.abc import Callable

from livekit.agents import llm

from motor_voz.brain.tenants.modelos import Tenant
from motor_voz.brain.tools import registro
from motor_voz.config import Config

logger = logging.getLogger("motor-voz.herramientas")

# Lo que pone el motor y el modelo no elige.
_ATADOS = ("tenant", "config", "sala")


def _descripcion(funcion: Callable) -> str:
    """La primera linea del docstring. Es lo que el modelo lee para decidir."""
    doc = inspect.getdoc(funcion) or ""
    return doc.split("\n", 1)[0].strip() or funcion.__name__


def _atar(funcion: Callable, tenant: Tenant, config: Config, sala: str) -> Callable:
    """Ata el tenant, la config y la sala, y los saca de la firma visible."""
    firma = inspect.signature(funcion)
    visibles = [
        p
        for nombre, p in firma.parameters.items()
        if nombre not in _ATADOS and p.kind is not inspect.Parameter.VAR_KEYWORD
    ]
    # No todas la piden: get_services no necesita saber de que sala salio.
    # Pasarsela igual seria un TypeError en medio de una conversacion.
    quiere_sala = "sala" in firma.parameters

    @functools.wraps(funcion)
    async def envuelta(**kwargs):
        if quiere_sala:
            kwargs["sala"] = sala
        return await funcion(tenant, config, **kwargs)

    # Sin esto, livekit arma el esquema con `tenant` y `config` adentro y el
    # modelo intenta completarlos.
    envuelta.__signature__ = firma.replace(parameters=visibles)  # type: ignore[attr-defined]
    return envuelta


def para(modo: str, tenant: Tenant, config: Config, sala: str) -> list[llm.Tool]:
    """Las tools que este agente puede usar, listas para el modelo.

    `modo` decide el registry. Cae en publico ante cualquier valor que no sea
    exactamente `interno`: ver `brain/tools/registro.py`.
    """
    registry = registro.registry_de(modo)
    tools: list[llm.Tool] = []
    for nombre in sorted(registro.tools_de(registry)):
        funcion = registro.resolver_tool(registry, nombre)
        tools.append(
            llm.function_tool(
                _atar(funcion, tenant, config, sala),
                name=nombre,
                description=_descripcion(funcion),
            )
        )
    logger.info("tools | modo=%s registry=%s | %s", modo, registry, ", ".join(sorted(registro.tools_de(registry))))
    return tools
