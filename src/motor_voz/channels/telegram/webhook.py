"""Webhook handler para Telegram que integra con el pipeline multicanal durable.

Recibe actualizaciones de Telegram y las registra en eventos_inbox para procesamiento
durable, sin mantener historial en memoria ni mantener un bot aislado.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from motor_voz.brain.mensajes import EventoInbox, MensajeEntrante
from motor_voz.brain.tenants import repositorio
from motor_voz.config import Config, cargar

logger = logging.getLogger(__name__)


def calcular_clave_idempotencia(update: Dict[str, Any]) -> str:
    """Calcula una clave de idempotencia única para un update de Telegram.
    
    Esto asegura que si Telegram reenvía el mismo evento, no se procese duplicadamente.
    """
    # Extraer campos relevantes para identificar unívocamente el evento
    mensaje = update.get("message") or update.get("edited_message") or {}
    chat = mensaje.get("chat", {})
    mensaje_id = mensaje.get("message_id", "")
    chat_id = chat.get("id", "")
    texto = mensaje.get("text", "")
    
    # Crear una cadena única basada en estos campos
    clave_base = f"telegram:{chat_id}:{mensaje_id}:{texto}"
    return hashlib.sha256(clave_base.encode()).hexdigest()


async def manejar_webhook(
    config: Config,
    tenant_canal_id: str,
    tenant_id: str,
    update: Dict[str, Any]
) -> Dict[str, Any]:
    """Registra una actualización de Telegram en el pipeline durable.
    
    Args:
        config: Configuración del sistema
        tenant_canal_id: ID del canal de Telegram en la tabla tenant_canales
        tenant_id: ID del tenant asociado
        update: Objeto de actualización de Telegram recibido por webhook
        
    Returns:
        Dict con resultado de la operación
    """
    try:
        mensaje = update.get("message") or update.get("edited_message")
        if not mensaje:
            return {"error": "No se encontró mensaje en la actualización", "ok": False}

        chat = mensaje.get("chat", {})
        chat_id = str(chat.get("id", ""))
        mensaje_id = str(mensaje.get("message_id", ""))
        texto = mensaje.get("text", "")
        
        # Convertir timestamp Unix a datetime si es necesario
        fecha_unix = mensaje.get("date", 0)
        if isinstance(fecha_unix, int) and fecha_unix > 0:
            fecha = datetime.fromtimestamp(fecha_unix, tz=timezone.utc)
        else:
            fecha = datetime.now(timezone.utc)
        
        if not chat_id or not mensaje_id:
            return {"error": "Mensaje incompleto: falta chat_id o message_id", "ok": False}

        # Calcular clave de idempotencia
        clave_idempotencia = calcular_clave_idempotencia(update)
        evento_externo_id = clave_idempotencia

        # Crear objeto MensajeEntrante
        mensaje_entrante = MensajeEntrante(
            tenant_id=tenant_id,
            canal="telegram",
            conversacion_externa_id=chat_id,  # Usar chat_id como identificador de conversación
            remitente_externo_id=chat_id,     # Remitente también es el chat_id
            evento_externo_id=evento_externo_id,
            mensaje_externo_id=mensaje_id,
            texto=texto,
            recibido_en=fecha,
            payload=update  # Guardar el payload completo por si se necesita más tarde
        )

        # Registrar el mensaje entrante en el pipeline durable
        resultado_registro = await repositorio.registrar_mensaje_entrante(
            config,
            tenant_canal_id=tenant_canal_id,
            mensaje=mensaje_entrante
        )

        return {
            "ok": True,
            "duplicado": resultado_registro.duplicado,
            "evento_id": resultado_registro.inbox_id,
            "conversacion_id": resultado_registro.conversacion_id,
            "mensaje_id": resultado_registro.mensaje_id
        }

    except Exception as e:
        logger.exception("Error al manejar webhook de Telegram: %s", e)
        return {"error": f"Error interno: {str(e)}", "ok": False}


async def verificar_token_webhook(token: str, expected_secreto_ref: str) -> bool:
    """Verifica que el token recibido sea válido antes de procesar el webhook."""
    from motor_voz.channels import secretos
    
    try:
        # Resolver el token real usando la referencia de secreto
        token_real = secretos.resolver(expected_secreto_ref)
        return hmac.compare_digest(token, token_real)
    except Exception:
        logger.warning("No se pudo verificar el token de webhook")
        return False


def main():
    """Ejemplo de uso del webhook handler."""
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python -m motor_voz.channels.telegram.webhook <ruta_al_json>")
        sys.exit(1)
    
    # Cargar configuración
    config = cargar()
    
    # Leer el update de ejemplo desde archivo
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        update = json.load(f)
    
    # Ejemplo de IDs (esto normalmente vendría del contexto del webhook)
    tenant_canal_id = "ejemplo-uuid"
    tenant_id = "ejemplo-uuid"
    
    # Procesar el webhook
    resultado = asyncio.run(manejar_webhook(config, tenant_canal_id, tenant_id, update))
    print(json.dumps(resultado, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()