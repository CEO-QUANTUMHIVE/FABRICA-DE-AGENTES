"""Vacia la cola de salida y manda cada respuesta por su canal.

Contracara del procesador, con la misma forma: un lote, cada evento cerrado
por su cuenta, nada que trabe la cola. La diferencia es que acá el duplicado
**le llega al cliente**, así que todo lo que no se pueda mandar bien se
descarta explícitamente en vez de reintentarse por las dudas.

Es comun a los cuatro canales. `enviadores` es un mapa explicito de canal a
funcion, por el mismo motivo que el registry de tools: un canal que todavia
no tiene cliente de envio no tiene que resolverse por accidente.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from motor_voz.brain.mensajes import EventoOutbox
from motor_voz.brain.tenants import repositorio
from motor_voz.channels import secretos
from motor_voz.channels.whatsapp import cliente as cliente_whatsapp
from motor_voz.config import Config

logger = logging.getLogger(__name__)

ESTADOS_QUE_ENVIAN = frozenset({"conectado"})
"""Se lista lo que ABRE, igual que en el procesador.

Un canal `pausado`, `revocado` o `error` no puede seguir escribiendole a los
clientes de un negocio.
"""


@dataclass(frozen=True)
class Dependencias:
    tomar: Callable[..., Awaitable[list[EventoOutbox]]]
    cerrar: Callable[..., Awaitable[str]]
    destino_de: Callable[..., Awaitable[object]]
    registrar_saliente: Callable[..., Awaitable[None]]
    resolver_secreto: Callable[[str], str]
    enviadores: dict[str, Callable[..., Awaitable[cliente_whatsapp.Resultado]]]

    @classmethod
    def de_produccion(cls) -> Dependencias:
        return cls(
            tomar=repositorio.tomar_eventos_outbox,
            cerrar=repositorio.cerrar_evento_outbox,
            destino_de=repositorio.destino_de_envio,
            registrar_saliente=repositorio.registrar_mensaje_saliente,
            resolver_secreto=secretos.resolver,
            enviadores={"whatsapp": cliente_whatsapp.enviar_texto},
        )


class NoSePuedeMandar(RuntimeError):
    """El envio no se intenta y reintentarlo no lo va a cambiar."""


async def vaciar_outbox(config: Config, deps: Dependencias, *, limite: int = 10) -> int:
    """Manda lo pendiente. Devuelve cuantos salieron de verdad."""
    eventos = await deps.tomar(config, limite=limite)
    enviados = 0

    for evento in eventos:
        try:
            resultado = await _mandar(config, deps, evento)
        except NoSePuedeMandar as motivo:
            logger.warning("enviador | descartado | %s | %s", evento.id, motivo)
            await deps.cerrar(
                config, evento_id=evento.id, ok=False,
                error=str(motivo), reintentable=False,
            )
            continue
        except Exception as error:  # noqa: BLE001
            logger.exception("enviador | evento=%s", evento.id)
            await deps.cerrar(
                config, evento_id=evento.id, ok=False,
                error=f"{type(error).__name__}: {error}", reintentable=True,
            )
            continue

        if resultado.ok:
            enviados += 1
            # Se guarda DESPUES de mandar y con el id que devolvio Meta. Al
            # reves guardariamos como enviado algo que quizas no salio.
            await deps.registrar_saliente(
                config,
                tenant_id=evento.tenant_id,
                tenant_canal_id=evento.tenant_canal_id,
                conversacion_id=evento.conversacion_id,
                canal=evento.canal,
                mensaje_externo_id=resultado.mensaje_externo_id,
                texto=evento.payload.get("texto", ""),
            )

        await deps.cerrar(
            config,
            evento_id=evento.id,
            ok=resultado.ok,
            error=resultado.error,
            reintentable=resultado.reintentable,
        )

    return enviados


async def _mandar(
    config: Config, deps: Dependencias, evento: EventoOutbox
) -> cliente_whatsapp.Resultado:
    texto = str(evento.payload.get("texto") or "")
    if not texto.strip():
        # Un globo en blanco en el chat de un cliente parece un negocio roto.
        raise NoSePuedeMandar("la respuesta encolada esta vacia")

    enviar = deps.enviadores.get(evento.canal)
    if enviar is None:
        # Instagram y Facebook van a existir en la base antes que su cliente.
        raise NoSePuedeMandar(f"el canal '{evento.canal}' todavia no sabe enviar")

    destino = await deps.destino_de(
        config,
        tenant_id=evento.tenant_id,
        tenant_canal_id=evento.tenant_canal_id,
        conversacion_id=evento.conversacion_id,
    )
    if destino.estado_canal not in ESTADOS_QUE_ENVIAN:
        raise NoSePuedeMandar(f"el canal esta '{destino.estado_canal}'")

    try:
        token = deps.resolver_secreto(destino.secreto_ref)
    except secretos.SecretoNoEncontrado as falta:
        # Es un problema de configuracion. Reintentarlo cada treinta segundos
        # hasta agotar intentos solo llena la tabla de errores iguales.
        raise NoSePuedeMandar(str(falta)) from falta

    return await enviar(
        config,
        token=token,
        phone_number_id=destino.cuenta_externa_id,
        destino=destino.contacto_externo_id,
        texto=texto,
    )
