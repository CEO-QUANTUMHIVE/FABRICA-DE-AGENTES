"""Traduce el webhook de Meta al contrato neutral del cerebro.

Este modulo no decide el tenant y no puede: devuelve la cuenta que RECIBIO el
mensaje (`phone_number_id`) y quien la resuelve es
`repositorio.canal_de_cuenta()`. Por eso el mensaje sale como `MensajeCrudo` y
recien se convierte en `MensajeEntrante` con `con_tenant()`, ya del lado
seguro. Un payload no puede elegir a que negocio le escribe.

Tampoco levanta excepciones por un cuerpo raro. Un 500 en este endpoint hace
que Meta reintente el mismo evento para siempre: lo que no se entiende se
descarta y se responde 200.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from motor_voz.brain.mensajes import MensajeEntrante

CANAL = "whatsapp"

# Lo que hoy sabemos convertir en texto para el agente. El resto se recibe,
# se guarda y se contesta avisando, pero no se procesa como si fuera texto.
TIPOS_SOPORTADOS = frozenset({"text"})


@dataclass(frozen=True)
class MensajeCrudo:
    """Un mensaje de WhatsApp todavia sin dueño."""

    conversacion_externa_id: str
    remitente_externo_id: str
    evento_externo_id: str
    mensaje_externo_id: str
    texto: str
    tipo: str
    soportado: bool
    nombre_contacto: str
    recibido_en: datetime
    payload: dict[str, Any] = field(default_factory=dict)

    def con_tenant(self, tenant_id: str) -> MensajeEntrante:
        """Ata el mensaje al tenant que resolvio la cuenta receptora."""
        return MensajeEntrante(
            tenant_id=tenant_id,
            canal=CANAL,
            conversacion_externa_id=self.conversacion_externa_id,
            remitente_externo_id=self.remitente_externo_id,
            evento_externo_id=self.evento_externo_id,
            mensaje_externo_id=self.mensaje_externo_id,
            texto=self.texto,
            recibido_en=self.recibido_en,
            payload=self.payload,
        )


@dataclass(frozen=True)
class EntradaWhatsApp:
    """Los mensajes que recibio una misma cuenta de negocio."""

    cuenta_externa_id: str
    mensajes: list[MensajeCrudo]


def leer_webhook(cuerpo: Any) -> list[EntradaWhatsApp]:
    """Devuelve una entrada por cuenta receptora, en el orden que llegaron."""
    entradas: list[EntradaWhatsApp] = []
    for valor in _valores(cuerpo):
        metadata = valor.get("metadata")
        if not isinstance(metadata, dict):
            continue
        cuenta = str(metadata.get("phone_number_id") or "").strip()
        if not cuenta:
            continue

        nombres = _nombres_por_contacto(valor.get("contacts"))
        mensajes = [
            mensaje
            for crudo in _lista(valor.get("messages"))
            if (mensaje := _mensaje(crudo, nombres)) is not None
        ]
        if mensajes:
            entradas.append(EntradaWhatsApp(cuenta_externa_id=cuenta, mensajes=mensajes))
    return entradas


def _valores(cuerpo: Any) -> list[dict[str, Any]]:
    valores = []
    for entry in _lista(cuerpo.get("entry") if isinstance(cuerpo, dict) else None):
        for cambio in _lista(entry.get("changes") if isinstance(entry, dict) else None):
            valor = cambio.get("value") if isinstance(cambio, dict) else None
            if isinstance(valor, dict):
                valores.append(valor)
    return valores


def _nombres_por_contacto(contactos: Any) -> dict[str, str]:
    nombres = {}
    for contacto in _lista(contactos):
        if not isinstance(contacto, dict):
            continue
        wa_id = str(contacto.get("wa_id") or "").strip()
        perfil = contacto.get("profile")
        if wa_id and isinstance(perfil, dict):
            nombres[wa_id] = str(perfil.get("name") or "").strip()
    return nombres


def _mensaje(crudo: Any, nombres: dict[str, str]) -> MensajeCrudo | None:
    if not isinstance(crudo, dict):
        return None

    # Sin id no hay idempotencia posible: un reintento de Meta se contestaria
    # de nuevo. Es preferible perder el mensaje que responder dos veces.
    mensaje_id = str(crudo.get("id") or "").strip()
    remitente = str(crudo.get("from") or "").strip()
    if not mensaje_id or not remitente:
        return None

    tipo = str(crudo.get("type") or "").strip() or "desconocido"
    soportado = tipo in TIPOS_SOPORTADOS
    texto = ""
    if soportado:
        cuerpo_texto = crudo.get("text")
        if isinstance(cuerpo_texto, dict):
            texto = str(cuerpo_texto.get("body") or "")

    return MensajeCrudo(
        # WhatsApp no tiene hilos: la conversacion es el contacto.
        conversacion_externa_id=remitente,
        remitente_externo_id=remitente,
        evento_externo_id=f"mensaje:{mensaje_id}",
        mensaje_externo_id=mensaje_id,
        texto=texto,
        tipo=tipo,
        soportado=soportado,
        nombre_contacto=nombres.get(remitente, ""),
        recibido_en=_fecha(crudo.get("timestamp")),
        payload=crudo,
    )


def _fecha(timestamp: Any) -> datetime:
    """Meta manda epoch en segundos, como string."""
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _lista(valor: Any) -> list[Any]:
    return valor if isinstance(valor, list) else []
