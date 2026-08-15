"""Modelos de datos del tenant: lo que devuelve el repositorio.

Estos dataclasses no saben que existe Supabase ni livekit. Son el
contrato que usan el resolver, el context builder y la seleccion de voz.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Servicio:
    nombre: str
    descripcion: str


@dataclass(frozen=True)
class PerfilTenant:
    slug: str
    nombre: str
    prompt_base: str


@dataclass(frozen=True)
class VozTenant:
    proveedor: str
    voice_id: str
    consentimiento_aprobado: bool


@dataclass(frozen=True)
class Lead:
    """Alguien que dejo su contacto hablando con el agente de un negocio.

    No lleva `tenant_id`: quien lo pide ya sabe de que negocio es, porque lo
    pidio filtrando por el. Llevarlo invitaria a pasarlo de un lado a otro.
    """

    nombre: str
    contacto: str
    interes: str
    creado_en: str


@dataclass(frozen=True)
class DominioTenant:
    """Un dominio registrado y de quien es.

    `puede_declarar` es para nuestros propios sitios de demos, donde conviven
    varios rubros en el mismo host: ahi la pagina dice que agente quiere. El
    dominio de un cliente real nunca lo tiene, porque si no volveria a poder
    pedir el agente de otro negocio.
    """

    tenant_slug: str
    puede_declarar: bool


@dataclass(frozen=True)
class ConocimientoTenant:
    id: str
    categoria: str
    clave: str
    titulo: str
    version_id: str
    numero: int
    contenido: dict[str, Any]


@dataclass(frozen=True)
class Tenant:
    id: str
    slug: str
    nombre: str
    idioma: str
    perfil: PerfilTenant
    prompt_propio: str
    servicios: tuple[Servicio, ...]
    voz: VozTenant | None
    conocimiento: tuple[ConocimientoTenant, ...] = field(default_factory=tuple)
