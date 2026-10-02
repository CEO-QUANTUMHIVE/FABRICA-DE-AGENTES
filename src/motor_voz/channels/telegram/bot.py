"""Procesador y runner de Telegram Bot para un Tenant de Fábrica de Agentes.

Permite:
1. Parsear eventos entrantes de Telegram (webhook o long-polling).
2. Extraer contexto si el usuario ingresó por el embudo web (/start app_...).
3. Consultar el cerebro del agente (motor_voz.brain.conversacion.responder).
4. Responder al usuario en Telegram con el conocimiento del tenant.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
from typing import Any, Awaitable, Callable

import aiohttp

from motor_voz.brain import conversacion as cerebro
from motor_voz.brain.mensajes import Turno
from motor_voz.brain.tenants import repositorio
from motor_voz.brain.tenants.modelos import Tenant
from motor_voz.channels.telegram import cliente as cliente_telegram
from motor_voz.channels import secretos
from motor_voz.config import Config, cargar

logger = logging.getLogger(__name__)


def decodificar_payload_inicio(texto: str) -> str:
    """Extrae y decodifica parámetros de calificación enviados por la landing.

    Ejemplos soportados:
    - "/start app_challenge_FTMO_100K"
    - "/start b64_<base64_json>"
    """
    texto = (texto or "").strip()
    if not texto.startswith("/start"):
        return texto

    partes = texto.split(maxsplit=1)
    if len(partes) < 2:
        return "¡Hola! Quiero información sobre los servicios de Take Prop."

    param = partes[1].strip()
    if param.startswith("b64_"):
        try:
            crudo = base64.urlsafe_b64decode(param[4:].encode("utf-8")).decode("utf-8")
            datos = json.loads(crudo)
            servicio = "Superar evaluación" if datos.get("service") == "challenge" else "Administrar cuenta live"
            firma = datos.get("firm", "No especificada")
            tamano = datos.get("size", "100K")
            estado = datos.get("stage", "")
            return (
                f"Hola, vengo desde la landing de Take Prop. Apliqué con estos datos:\n"
                f"- Servicio: {servicio}\n"
                f"- Firma de fondeo: {firma}\n"
                f"- Tamaño de cuenta: {tamano}\n"
                f"- Estado actual: {estado}\n"
                f"Quiero saber cómo podemos empezar y los detalles del acuerdo 50/50."
            )
        except Exception:
            pass

    if param.startswith("app_"):
        segmentos = param.split("_")
        # app_challenge_FTMO_100K
        if len(segmentos) >= 4:
            tipo = "Superar evaluación" if segmentos[1] == "challenge" else "Administrar cuenta live"
            firma = segmentos[2]
            tamano = segmentos[3]
            return (
                f"Hola, vengo desde la web de Take Prop.\n"
                f"Solicito: {tipo} para {firma} de {tamano}.\n"
                f"¿Cómo avanzamos con la revisión de las reglas y el inicio?"
            )

    return "¡Hola! Quiero consultar sobre la superación de pruebas de fondeo y administración de cuentas live."


async def procesar_actualizacion(
    config: Config,
    tenant: Tenant,
    actualizacion: dict[str, Any],
    *,
    token: str,
    historial: list[Turno] | None = None,
    enviar_fn: Callable[..., Awaitable[cliente_telegram.Resultado]] = cliente_telegram.enviar_texto,
    responder_fn: Callable[..., Awaitable[str]] = cerebro.responder,
) -> cliente_telegram.Resultado | None:
    """Procesa un update individual de Telegram registrándolo en el pipeline durable."""
    mensaje = actualizacion.get("message") or actualizacion.get("edited_message")
    if not mensaje:
        return None

    texto_recibido = (mensaje.get("text") or "").strip()
    chat = mensaje.get("chat", {})
    chat_id = str(chat.get("id", ""))
    mensaje_id = str(mensaje.get("message_id", ""))
    
    # Convertir timestamp Unix a datetime si es necesario
    fecha_unix = mensaje.get("date", 0)
    from datetime import datetime, timezone
    if isinstance(fecha_unix, int) and fecha_unix > 0:
        fecha = datetime.fromtimestamp(fecha_unix, tz=timezone.utc)
    else:
        fecha = datetime.now(timezone.utc)
    
    if not chat_id:
        return None

    # Registrar el mensaje entrante en el pipeline durable para procesamiento asíncrono
    # Esto asegura que se maneje de forma idempotente y durable
    from motor_voz.brain.tenants import repositorio
    
    # Calcular clave de idempotencia
    import hashlib
    clave_base = f"telegram:{chat_id}:{mensaje_id}:{texto_recibido}"
    evento_externo_id = hashlib.sha256(clave_base.encode()).hexdigest()
    
    # Buscar el canal de Telegram para este tenant
    try:
        canal_telegram = await repositorio.canal_de_cuenta(config, canal="telegram", cuenta_externa_id=chat_id)
        tenant_canal_id = canal_telegram.id
    except repositorio.CanalNoEncontrado:
        # Si no encontramos un canal específico para este chat_id, buscamos cualquier canal telegram para este tenant
        # Obtenemos el tenant_canal_id de otra manera - buscando por tenant_id y canal
        cliente_supabase = await repositorio._cliente(config)
        respuesta = await cliente_supabase.table("tenant_canales").select("id").eq("tenant_id", tenant.id).eq("canal", "telegram").eq("estado", "conectado").maybe_single().execute()
        if not respuesta.data:
            logger.error("telegram | no se encontró canal telegram conectado para tenant | tenant_id=%s", tenant.id)
            return None
        tenant_canal_id = respuesta.data["id"]

    # Crear objeto MensajeEntrante
    from motor_voz.brain.mensajes import MensajeEntrante
    mensaje_entrante = MensajeEntrante(
        tenant_id=tenant.id,
        canal="telegram",
        conversacion_externa_id=chat_id,
        remitente_externo_id=chat_id,
        evento_externo_id=evento_externo_id,
        mensaje_externo_id=mensaje_id,
        texto=texto_recibido,
        recibido_en=fecha,
        payload=actualizacion
    )

    # Registrar el mensaje en el pipeline durable
    resultado_registro = await repositorio.registrar_mensaje_entrante(
        config,
        tenant_canal_id=tenant_canal_id,
        mensaje=mensaje_entrante
    )
    
    if resultado_registro.duplicado:
        logger.info("telegram | evento duplicado, ignorando | evento_id=%s", evento_externo_id)
        return None

    logger.info("telegram | mensaje registrado en pipeline durable | chat_id=%s | evento_id=%s", 
                chat_id, resultado_registro.inbox_id)
    
    return None  # El mensaje se procesará en el worker, no aquí


async def ejecutar_polling(
    config: Config,
    secreto_ref: str,
    tenant_slug: str = "takepropfit",
) -> None:
    """Bucle de long-polling para ejecutar el bot de forma continua."""
    logging.info("telegram | iniciando runner polling para tenant=%s con secreto_ref=%s", tenant_slug, secreto_ref)
    tenant = await repositorio.obtener_tenant(config, tenant_slug)
    
    # Obtener el token usando el sistema de secretos
    token = secretos.resolver(secreto_ref)
    
    ultimo_update_id = 0
    url_updates = f"https://api.telegram.org/bot{token}/getUpdates"

    # Memoria en memoria para sesiones de chat
    historiales: dict[str, list[Turno]] = {}

    timeout = aiohttp.ClientTimeout(total=40)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            try:
                params = {"offset": ultimo_update_id + 1, "timeout": 25}
                async with session.get(url_updates, params=params) as resp:
                    if resp.status != 200:
                        logger.warning("telegram | getUpdates fallo con HTTP %s", resp.status)
                        await asyncio.sleep(3)
                        continue
                    cuerpo = await resp.json()

                updates = cuerpo.get("result", [])
                for u in updates:
                    update_id = u.get("update_id", 0)
                    if update_id > ultimo_update_id:
                        ultimo_update_id = update_id

                    msg = u.get("message")
                    if msg and "chat" in msg:
                        cid = str(msg["chat"]["id"])
                        hist = historiales.setdefault(cid, [])
                        await procesar_actualizacion(
                            config,
                            tenant,
                            u,
                            token=token,
                            historial=hist,
                        )
                        # Mantener histórico breve
                        if len(hist) > 10:
                            del hist[:2]

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("telegram | error en bucle polling: %s", e)
                await asyncio.sleep(3)


def main() -> None:
    parser = argparse.ArgumentParser(description="Runner de Telegram Bot para Fábrica de Agentes")
    parser.add_argument("--secreto-ref", required=True, help="Referencia al secreto del Bot de Telegram (ej: telegram_takepropfit)")
    parser.add_argument("--tenant", default="takepropfit", help="Slug del tenant (defecto: takepropfit)")
    args = parser.parse_args()

    cfg = cargar()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(ejecutar_polling(cfg, args.secreto_ref, args.tenant))


if __name__ == "__main__":
    main()
