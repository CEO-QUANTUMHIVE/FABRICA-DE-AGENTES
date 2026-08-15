"""De un mensaje recibido a una respuesta encolada.

El webhook no contesta: guarda y devuelve 200, porque si tardara Meta
reintentaria el mismo evento. Este worker es el que hace el trabajo, y por
eso corre aparte y sobre una cola durable.

Es comun a los cuatro canales. No sabe nada de WhatsApp: recibe eventos con
tenant, conversacion y canal ya resueltos, y encola texto. Quien lo traduce
al formato del proveedor es el cliente de cada canal.

Tres reglas que decidieron la forma de este modulo:

- **Un evento roto no se lleva puesto al lote.** Cada uno se cierra por su
  cuenta; el que falla queda para reintentar y los demas siguen.
- **La clave de idempotencia sale del evento, no del momento.** Si el worker
  muere despues de encolar y antes de cerrar, al reanudar choca contra la
  misma clave en vez de encolar otra respuesta.
- **Si atiende una persona, el agente se calla.** El handoff no es un aviso
  al dueño: es que el agente deja de contestar esa conversacion.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from motor_voz.brain import conversacion
from motor_voz.brain.mensajes import (
    ContextoConversacion,
    EventoInbox,
    Permiso,
    Turno,
)
from motor_voz.brain.tenants import repositorio
from motor_voz.config import Config

logger = logging.getLogger(__name__)

SOLO_LEO_TEXTO = (
    "Por ahora solo puedo leer mensajes de texto. ¿Me lo escribis?"
)
"""Respuesta a un audio, una imagen o una ubicacion.

Se contesta sin pasar por el modelo: el parser dejo el texto vacio, y
mandarle un mensaje en blanco a un LLM es pagar para que conteste a la nada.
"""

MODOS_QUE_CONTESTAN = frozenset({"automatico"})
"""Se lista lo que ABRE, no lo que cierra.

Mismo criterio que `registry_de`: comparar contra lo que cierra
—`if modo != "humano"`— dejaria contestar con cualquier valor raro, y este
chequeo decide si el agente le habla por encima a una persona.
"""


@dataclass(frozen=True)
class Dependencias:
    """Todo lo que toca la base entra por aca, para poder probar sin Supabase.

    `de_produccion()` las cablea al repositorio real. Los tests pasan dobles y
    la suite sigue sin depender de que Supabase este arriba.
    """

    tomar: Callable[..., Awaitable[list[EventoInbox]]]
    cerrar: Callable[..., Awaitable[str]]
    tenant_de_id: Callable[..., Awaitable[Any]]
    contexto_de: Callable[..., Awaitable[ContextoConversacion]]
    encolar: Callable[..., Awaitable[bool]]
    puede_responder: Callable[..., Awaitable[Permiso]] = repositorio.puede_responder
    responder: Callable[..., Awaitable[str]] = conversacion.responder

    @classmethod
    def de_produccion(cls) -> Dependencias:
        return cls(
            tomar=repositorio.tomar_eventos_inbox,
            cerrar=repositorio.cerrar_evento_inbox,
            tenant_de_id=repositorio.tenant_por_id,
            contexto_de=repositorio.contexto_de_conversacion,
            encolar=repositorio.encolar_respuesta,
        )


async def procesar_pendientes(
    config: Config, deps: Dependencias, *, limite: int = 10
) -> int:
    """Toma un lote del inbox y encola una respuesta por cada uno.

    Devuelve cuantos terminaron bien. Los que fallaron quedan en la cola con
    su backoff: no se pierden y no bloquean a los otros.
    """
    eventos = await deps.tomar(config, limite=limite)
    procesados = 0

    for evento in eventos:
        try:
            if await _atender(config, deps, evento):
                procesados += 1
            await deps.cerrar(config, evento_id=evento.id, ok=True, error="")
        except Exception as error:  # noqa: BLE001
            logger.exception(
                "procesador | evento=%s tenant=%s", evento.id, evento.tenant_id
            )
            await deps.cerrar(
                config, evento_id=evento.id, ok=False, error=f"{type(error).__name__}: {error}"
            )

    return procesados


async def _atender(config: Config, deps: Dependencias, evento: EventoInbox) -> bool:
    """True si se encolo una respuesta.

    Un False no es un error: es que no habia nada que contestar. Se cierra
    igual, porque reintentarlo no lo va a cambiar.
    """
    if not evento.conversacion_id:
        logger.warning("procesador | evento sin conversacion | %s", evento.id)
        return False

    contexto = await deps.contexto_de(
        config, tenant_id=evento.tenant_id, conversacion_id=evento.conversacion_id
    )

    if contexto.modo_atencion not in MODOS_QUE_CONTESTAN:
        logger.info(
            "procesador | atiende una persona | conversacion=%s modo=%s",
            evento.conversacion_id,
            contexto.modo_atencion,
        )
        return False

    if not contexto.turnos or contexto.turnos[-1].rol != "user":
        # El ultimo movimiento fue nuestro. Nada que contestar.
        return False

    # El boton rojo global, antes que cualquier consulta. Es para el momento
    # en que algo se desmadra y no hay tiempo de averiguar de quien es.
    if not config.respuestas_automaticas:
        logger.warning("procesador | respuestas automaticas apagadas por entorno")
        return False

    ultimo = contexto.turnos[-1]
    if not ultimo.texto.strip():
        texto = SOLO_LEO_TEXTO
    else:
        # Antes del LLM, no despues: el punto de un tope de gasto es no
        # pagarlo, no descartar la respuesta cuando ya se pago.
        permiso = await deps.puede_responder(
            config, tenant_id=evento.tenant_id, conversacion_id=evento.conversacion_id
        )
        if not permiso.permitido:
            logger.warning(
                "procesador | no se contesta | tenant=%s | %s",
                evento.tenant_id,
                permiso.motivo,
            )
            return False

        tenant = await deps.tenant_de_id(config, evento.tenant_id)
        texto = await deps.responder(
            config,
            tenant,
            historial=contexto.turnos[:-1],
            texto=ultimo.texto,
            canal=evento.canal,
        )

    await deps.encolar(
        config,
        tenant_id=evento.tenant_id,
        tenant_canal_id=evento.tenant_canal_id,
        conversacion_id=evento.conversacion_id,
        canal=evento.canal,
        clave_idempotencia=f"respuesta:{evento.evento_externo_id}",
        payload={"texto": texto},
    )
    return True
