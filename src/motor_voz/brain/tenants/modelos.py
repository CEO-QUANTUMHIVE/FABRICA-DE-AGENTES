"""Modelos de datos del tenant: lo que devuelve el repositorio.

Estos dataclasses no saben que existe Supabase ni livekit. Son el
contrato que usan el resolver, el context builder y la seleccion de voz.
"""

from __future__ import annotations

from dataclasses import dataclass


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
class Tenant:
    id: str
    slug: str
    nombre: str
    idioma: str
    perfil: PerfilTenant
    prompt_propio: str
    servicios: tuple[Servicio, ...]
    voz: VozTenant | None
