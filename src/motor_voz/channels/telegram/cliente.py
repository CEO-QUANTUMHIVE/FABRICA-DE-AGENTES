"""Envío de mensajes por la API de Telegram Bot.

Contrato análogo al cliente de WhatsApp:
- Devolver un Resultado con ok, mensaje_externo_id, error y reintentable.
- Distinguir fallos permanentes (400, 401, 403) de temporales (429, 5xx).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import aiohttp

from motor_voz.config import Config

logger = logging.getLogger(__name__)

URL_BASE = "https://api.telegram.org"

# Errores permanentes de Telegram
PERMANENTES: dict[int, str] = {
    400: "parámetro o chat inválido",
    401: "token de bot inválido o revocado",
    403: "el bot fue bloqueado por el usuario o no tiene permisos en el chat",
    404: "método o recurso no encontrado",
}


@dataclass(frozen=True)
class Resultado:
    ok: bool
    mensaje_externo_id: str = ""
    error: str = ""
    reintentable: bool = True


async def _post(url: str, cuerpo: dict[str, Any]) -> tuple[int, dict]:
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=cuerpo) as respuesta:
            try:
                datos = await respuesta.json()
            except Exception:
                datos = {}
            return respuesta.status, datos


async def enviar_texto(
    config: Config,
    *,
    token: str,
    chat_id: str = "",
    destino: str = "",
    texto: str,
    pedir: Callable[..., Awaitable[tuple[int, dict]]] | None = None,
    **kwargs: Any,
) -> Resultado:
    """Envía un mensaje de texto a un chat de Telegram.

    No levanta excepciones: el enviador de la cola necesita una decisión clara.
    Acepta tanto `chat_id` como `destino` para compatibilidad con el worker multicanal.
    `pedir` se inyecta en tests para evitar llamadas a la red.
    """
    id_destino = (chat_id or destino or "").strip()
    if not token.strip():
        logger.error("telegram | canal sin token | destino=%s", id_destino)
        return Resultado(
            ok=False, error="el canal no tiene credencial", reintentable=False
        )

    if not id_destino:
        return Resultado(
            ok=False, error="falta chat_id destino", reintentable=False
        )

    llamar = pedir or _post
    url = f"{URL_BASE}/bot{token.strip()}/sendMessage"
    cuerpo = {
        "chat_id": id_destino,
        "text": texto,
    }

    try:
        codigo, datos = await llamar(url, cuerpo)
    except Exception as error:  # noqa: BLE001
        logger.warning("telegram | error de red | destino=%s error=%s", id_destino, error)
        return Resultado(
            ok=False,
            error=f"error de red: {error}",
            reintentable=True,
        )

    if codigo == 200 and datos.get("ok"):
        resultado = datos.get("result", {})
        mensaje_id = str(resultado.get("message_id", ""))
        logger.info("telegram | enviado | destino=%s mensaje_id=%s", id_destino, mensaje_id)
        return Resultado(ok=True, mensaje_externo_id=mensaje_id)

    descripcion = datos.get("description", "")
    logger.warning(
        "telegram | error de api | codigo=%s destino=%s descripcion=%s",
        codigo,
        id_destino,
        descripcion,
    )

    if codigo in PERMANENTES:
        return Resultado(
            ok=False,
            error=f"{PERMANENTES[codigo]}: {descripcion}",
            reintentable=False,
        )

    # 429 Too Many Requests o 5xx son temporales y se reintentan
    return Resultado(
        ok=False,
        error=f"HTTP {codigo}: {descripcion}",
        reintentable=True,
    )
