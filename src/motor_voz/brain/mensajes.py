"""Contrato neutral entre los canales de texto y el cerebro del agente.

WhatsApp, Instagram y Facebook convierten sus webhooks a este modelo. El
cerebro nunca recibe payloads de Meta ni decide el tenant desde datos del
usuario: el adaptador ya debe haber validado la firma y resuelto la cuenta
externa contra un tenant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


CANALES_COMERCIALES = frozenset({"web", "whatsapp", "instagram", "facebook"})


@dataclass(frozen=True)
class MensajeEntrante:
    tenant_id: str
    canal: str
    conversacion_externa_id: str
    remitente_externo_id: str
    evento_externo_id: str
    mensaje_externo_id: str
    texto: str
    recibido_en: datetime
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.canal not in CANALES_COMERCIALES:
            raise ValueError(f"Canal no soportado: {self.canal!r}")
        for campo in (
            "tenant_id",
            "conversacion_externa_id",
            "remitente_externo_id",
            "evento_externo_id",
            "mensaje_externo_id",
        ):
            if not getattr(self, campo).strip():
                raise ValueError(f"{campo} es obligatorio")

    @property
    def clave_idempotencia(self) -> str:
        """Evita contestar dos veces si el proveedor reintenta un webhook."""
        return f"{self.canal}:{self.mensaje_externo_id}"


@dataclass(frozen=True)
class CanalTenant:
    id: str
    tenant_id: str
    canal: str
    cuenta_externa_id: str
    nombre: str
    estado: str


@dataclass(frozen=True)
class ResultadoIngreso:
    duplicado: bool
    inbox_id: str | None = None
    conversacion_id: str | None = None
    mensaje_id: str | None = None


@dataclass(frozen=True)
class Turno:
    """Un mensaje ya guardado, como lo ve el cerebro.

    `rol` usa el vocabulario de OpenAI (`user` / `assistant`) porque es lo que
    espera cualquier LLM de texto. La direccion que guarda la base
    (`entrante` / `saliente`) se traduce a esto al leerla.
    """

    rol: str
    texto: str


@dataclass(frozen=True)
class EventoInbox:
    """Un webhook pendiente de procesar, ya resuelto a tenant y conversacion."""

    id: str
    tenant_id: str
    tenant_canal_id: str
    conversacion_id: str | None
    canal: str
    evento_externo_id: str


@dataclass(frozen=True)
class ContextoConversacion:
    """Lo que el procesador necesita saber para decidir si contesta."""

    modo_atencion: str
    turnos: tuple[Turno, ...]


@dataclass(frozen=True)
class Permiso:
    """Si el agente puede contestar, y por que no si no puede.

    El motivo se guarda y se muestra: "no contesto" sin explicacion es lo que
    hace que alguien desactive el limite en vez de entenderlo.
    """

    permitido: bool
    motivo: str = ""


@dataclass(frozen=True)
class EventoOutbox:
    """Una respuesta lista para mandar al proveedor."""

    id: str
    tenant_id: str
    tenant_canal_id: str
    conversacion_id: str
    canal: str
    clave_idempotencia: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class DestinoEnvio:
    """A quien y desde donde se manda, resuelto en una sola consulta."""

    cuenta_externa_id: str
    secreto_ref: str
    contacto_externo_id: str
    estado_canal: str


@dataclass(frozen=True)
class Conversacion:
    id: str
    canal: str
    contacto_externo_id: str
    nombre_contacto: str
    modo_atencion: str
    ultimo_mensaje_en: str | None


@dataclass(frozen=True)
class MensajeGuardado:
    id: str
    canal: str
    direccion: str
    texto: str
    estado: str
    ocurrido_en: str
