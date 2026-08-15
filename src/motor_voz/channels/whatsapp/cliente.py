"""Envio por la WhatsApp Cloud API.

Mandar el mensaje es un POST. Lo que decide si esto funciona en produccion es
**clasificar la respuesta cuando Meta dice que no**:

- reintentar un error permanente gasta llamadas y deja la cola trabada detras
  de algo que nunca va a salir;
- no reintentar uno temporal pierde el mensaje de un cliente.

Ante un codigo que no conocemos se reintenta. Perder lo que escribio un
cliente es peor que gastar una llamada de mas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import aiohttp

from motor_voz.config import Config

logger = logging.getLogger(__name__)

URL_BASE = "https://graph.facebook.com"

# Codigos de Meta que no se arreglan reintentando.
PERMANENTES: dict[int, str] = {
    190: "credencial invalida o revocada",
    131047: "fuera de la ventana de 24 horas: hace falta una plantilla aprobada",
    131026: "el numero no recibe mensajes de WhatsApp",
    131051: "tipo de mensaje no soportado",
    132000: "la plantilla no coincide con los parametros",
    100: "parametro invalido",
}


@dataclass(frozen=True)
class Resultado:
    ok: bool
    mensaje_externo_id: str = ""
    error: str = ""
    reintentable: bool = True


async def enviar_texto(
    config: Config,
    *,
    token: str,
    phone_number_id: str,
    destino: str,
    texto: str,
    pedir: Callable[..., Awaitable[tuple[int, dict]]] | None = None,
) -> Resultado:
    """Manda un mensaje de texto libre y devuelve que paso.

    No levanta excepciones: el enviador necesita una decision, no un stack
    trace. `pedir` se inyecta en los tests.
    """
    if not token.strip():
        # Sin credencial no hay a quien pedirle nada, y reintentar tampoco la
        # va a traer. Falla cerrado y ruidoso.
        logger.error("whatsapp | canal sin token | phone_number_id=%s", phone_number_id)
        return Resultado(
            ok=False, error="el canal no tiene credencial", reintentable=False
        )

    llamar = pedir or _post
    url = f"{URL_BASE}/{config.whatsapp_api_version}/{phone_number_id}/messages"
    cuerpo = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": destino,
        "type": "text",
        # preview_url en False a proposito: una URL en la respuesta del agente
        # generaria una tarjeta de vista previa que no controlamos.
        "text": {"preview_url": False, "body": texto},
    }

    try:
        estado, respuesta = await llamar(
            url, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
        )
    except Exception as error:  # noqa: BLE001
        # Timeout, DNS, conexion cortada. Nada de eso dice que el mensaje sea
        # invalido, asi que vuelve a la cola.
        logger.warning("whatsapp | sin respuesta de Meta | %s", type(error).__name__)
        return Resultado(ok=False, error=f"sin respuesta: {type(error).__name__}")

    if estado == 200:
        mensajes = respuesta.get("messages") or []
        identificador = mensajes[0].get("id", "") if mensajes else ""
        if identificador:
            return Resultado(ok=True, mensaje_externo_id=identificador)
        # 200 sin id es una respuesta que no entendemos. No se da por enviado.
        return Resultado(ok=False, error="Meta respondio 200 sin id de mensaje")

    return _falla(estado, respuesta, token)


def _falla(estado: int, respuesta: dict[str, Any], token: str) -> Resultado:
    error = respuesta.get("error") or {}
    codigo = error.get("code")
    motivo = PERMANENTES.get(codigo)

    if motivo is None:
        detalle = str(error.get("message") or f"HTTP {estado}")
        reintentable = True
    else:
        detalle = motivo
        reintentable = False

    return Resultado(
        ok=False,
        # El mensaje de Meta puede traer el token adentro, y esto termina en
        # `ultimo_error` de la base y en los logs.
        error=f"[{codigo or estado}] {_sin_token(detalle, token)}",
        reintentable=reintentable,
    )


def _sin_token(texto: str, token: str) -> str:
    return texto.replace(token, "***") if token else texto


async def _post(url: str, *, json: dict, headers: dict) -> tuple[int, dict]:
    tiempo = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=tiempo) as sesion:
        async with sesion.post(url, json=json, headers=headers) as r:
            try:
                cuerpo = await r.json()
            except Exception:  # noqa: BLE001
                cuerpo = {}
            return r.status, cuerpo
