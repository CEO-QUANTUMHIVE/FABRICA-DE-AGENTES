"""Arma el prompt final de una sesion a partir del tenant ya resuelto.

Combina la identidad propia del tenant (su perfil de vertical) con las
capas de entrega y canal de brain/prompt.py, y agrega sus servicios como
contexto de sesion. No sabe que existe livekit ni Supabase: recibe un
Tenant ya resuelto por brain/tenants/repositorio.py.
"""

from __future__ import annotations

from motor_voz.brain.prompt import construir
from motor_voz.brain.tenants.modelos import Tenant


def _contexto_de_servicios(tenant: Tenant) -> str:
    if not tenant.servicios:
        return tenant.prompt_propio
    lista = "\n".join(f"- {s.nombre}: {s.descripcion}" for s in tenant.servicios)
    servicios_texto = (
        f"Estos son los servicios reales de {tenant.nombre}, no inventes otros:\n{lista}"
    )
    if tenant.prompt_propio.strip():
        return f"{tenant.prompt_propio.strip()}\n\n{servicios_texto}"
    return servicios_texto


def construir_contexto(tenant: Tenant, motor: str = "pipeline", canal: str = "web") -> str:
    """Prompt final para este tenant, en este motor y este canal."""
    return construir(
        motor=motor,
        canal=canal,
        identidad=tenant.perfil.prompt_base,
        contexto_extra=_contexto_de_servicios(tenant),
    )
