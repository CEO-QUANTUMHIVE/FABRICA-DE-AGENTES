"""Que puede hacer un agente, y quien puede hacer que.

Dos registries, y lo que decide cual toca es el MODO de la sesion, no el
vertical del negocio:

    publico   el visitante que llega a la landing
    interno   el dueño del negocio, en su panel de control

El interno es un SUPERCONJUNTO del publico: el dueño tambien atiende. Y no
depende del vertical, porque el dueño de una barberia y el de una peluqueria
necesitan los dos su modo interno.

NINGUN registry crea negocios ni agentes. Dar de alta es una operacion de la
fabrica detras de login, no algo que un agente haga porque se lo pidan bien
(regla de Sergio, 2026-08-11). Hay un test que lo fija: si alguna vez aparece
una tool que cree, se rompe y hay que discutirlo.

Este modulo no importa livekit ni Supabase. Las tools reciben lo que
necesitan como argumento, asi las reusa el canal asincrono sin tocar nada.
"""

from __future__ import annotations

from collections.abc import Callable

from motor_voz.brain.tools import internas, publicas

MODO_POR_DEFECTO = "publico"
"""Lo que se usa cuando nadie dijo nada, y cuando lo que dijeron no se entiende.

Esto decide si alguien ve los leads de un negocio. Un modo vacio, mal escrito
o inventado tiene que caer del lado seguro.
"""


class ToolNoPermitida(PermissionError):
    """La tool no existe, o existe y este registry no la alcanza.

    Un solo error para los dos casos a proposito: distinguirlos le diria al
    que esta probando cuales existen.
    """


class RegistryDesconocido(ValueError):
    """No hay un registry con ese nombre."""


# El mapa es la frontera. Una funcion que no este aca no es alcanzable, aunque
# exista en el modulo y aunque el modelo invente su nombre. Por eso es un mapa
# explicito y no un getattr sobre el modulo: con getattr, cualquier funcion que
# alguien agregue queda expuesta sin que nadie lo decida.
_PUBLICAS: dict[str, Callable] = {
    "get_services": publicas.get_services,
    "get_business_info": publicas.get_business_info,
    "capture_lead": publicas.capture_lead,
    "transfer_to_human": publicas.transfer_to_human,
}

_INTERNAS: dict[str, Callable] = {
    "get_mis_leads": internas.get_mis_leads,
    "get_mis_metricas": internas.get_mis_metricas,
    "get_mis_conversaciones": internas.get_mis_conversaciones,
}

_REGISTRIES: dict[str, dict[str, Callable]] = {
    "publico": _PUBLICAS,
    "interno": _PUBLICAS | _INTERNAS,
}


def registry_de(modo: str) -> str:
    """Que registry le toca a un modo de sesion.

    Falla cerrado: SOLO el string exacto `interno` abre lo interno. Vacio, con
    mayusculas, con espacios o inventado cae en publico.

    Se lista lo que ABRE, no lo que cierra. Comparar contra lo que cierra
    —`if modo != "publico"`— dejaria pasar cualquier valor raro, y este es el
    chequeo que decide si alguien ve los leads de un negocio.
    """
    return "interno" if modo == "interno" else MODO_POR_DEFECTO


def tools_de(registry: str) -> set[str]:
    """Los nombres que alcanza un registry."""
    if registry not in _REGISTRIES:
        raise RegistryDesconocido(f"No existe el registry '{registry}'.")
    return set(_REGISTRIES[registry])


def resolver_tool(registry: str, nombre: str) -> Callable:
    """La unica puerta. Si no pasa por aca, no se ejecuta."""
    if registry not in _REGISTRIES:
        raise RegistryDesconocido(f"No existe el registry '{registry}'.")
    funcion = _REGISTRIES[registry].get(nombre)
    if funcion is None:
        raise ToolNoPermitida(f"El registry '{registry}' no alcanza la tool '{nombre}'.")
    return funcion
