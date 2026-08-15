"""Arma el prompt final de una sesion a partir del tenant ya resuelto.

Combina la identidad propia del tenant (su perfil de vertical) con las
capas de entrega y canal de brain/prompt.py, y agrega sus servicios como
contexto de sesion. No sabe que existe livekit ni Supabase: recibe un
Tenant ya resuelto por brain/tenants/repositorio.py.
"""

from __future__ import annotations

import json

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


def _contexto_de_conocimiento(tenant: Tenant) -> str:
    """Solo recibe versiones publicadas cargadas por el repositorio."""
    if not tenant.conocimiento:
        return ""
    lineas = []
    for pieza in sorted(
        tenant.conocimiento, key=lambda item: (item.categoria, item.clave)
    ):
        contenido = json.dumps(
            pieza.contenido, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        lineas.append(
            f"- [{pieza.categoria}] {pieza.titulo} ({pieza.clave}): {contenido}"
        )
    texto = "Conocimiento aprobado y vigente del negocio:\n" + "\n".join(lineas)
    # Protege el costo por turno. El panel debe dividir piezas grandes, no
    # convertir el system prompt en un deposito ilimitado.
    return texto[:12000]


def construir_contexto(tenant: Tenant, motor: str = "pipeline", canal: str = "web") -> str:
    """Prompt final para este tenant, en este motor y este canal."""
    capas = [
        capa for capa in (_contexto_de_servicios(tenant), _contexto_de_conocimiento(tenant))
        if capa.strip()
    ]
    return construir(
        motor=motor,
        canal=canal,
        identidad=tenant.perfil.prompt_base,
        contexto_extra="\n\n".join(capas),
    )
