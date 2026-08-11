"""Lo que puede hacer un agente con un visitante.

Todas reciben el `Tenant` YA RESUELTO como primer argumento. **Ninguna acepta
un identificador de negocio por argumento**: si lo aceptara, el modelo podria
pasarle el de otro, y el modelo le hace caso a quien le habla.

Devuelven texto porque es lo que el modelo vuelve a leer. Un dict lo tendria
que serializar el, y lo hace peor.
"""

from __future__ import annotations

from motor_voz.brain.tenants import repositorio
from motor_voz.brain.tenants.modelos import Tenant
from motor_voz.config import Config


async def get_services(tenant: Tenant, config: Config) -> str:
    """Los servicios reales del negocio.

    Salen del tenant que ya venia resuelto, no de una consulta nueva: asi no
    hay forma de pedir los de otro.
    """
    if not tenant.servicios:
        return f"{tenant.nombre} todavia no tiene servicios cargados."
    lineas = [f"- {s.nombre}: {s.descripcion}" for s in tenant.servicios]
    return f"Servicios de {tenant.nombre}:\n" + "\n".join(lineas)


async def get_business_info(tenant: Tenant, config: Config) -> str:
    """Los datos del negocio que el visitante puede preguntar.

    Solo lo que el tenant declaro. No se inventan horarios ni direcciones que
    nadie cargo: un agente que inventa un horario hace que alguien viaje al
    pedo.
    """
    partes = [f"Negocio: {tenant.nombre}", f"Rubro: {tenant.perfil.nombre}"]
    if tenant.prompt_propio.strip():
        partes.append(tenant.prompt_propio.strip())
    return "\n".join(partes)


async def capture_lead(
    tenant: Tenant,
    config: Config,
    *,
    nombre: str = "",
    contacto: str = "",
    interes: str = "",
    sala: str = "",
) -> str:
    """Guarda un interesado con su contacto.

    Es la unica tool de esta fase que escribe. El negocio al que se le guarda
    sale del tenant resuelto, nunca de un argumento.
    """
    if not contacto.strip():
        # Un lead sin forma de contactarlo no sirve para nada, y guardarlo
        # ensucia la lista del dueño.
        return "Para anotarlo necesito un telefono o un mail."

    await repositorio.guardar_lead(
        config,
        tenant_id=tenant.id,
        nombre=nombre.strip(),
        contacto=contacto.strip(),
        interes=interes.strip(),
        sala=sala.strip(),
    )
    return f"Listo, quedo anotado el contacto de {nombre.strip() or 'la persona'}."


async def transfer_to_human(tenant: Tenant, config: Config, *, motivo: str = "", sala: str = "") -> str:
    """Deja constancia de que pidieron hablar con una persona.

    NO transfiere: hoy no hay a donde. Se guarda como un lead marcado, que es
    lo que el dueño va a ver. Prometer una transferencia que no existe es
    peor que decir la verdad.
    """
    await repositorio.guardar_lead(
        config,
        tenant_id=tenant.id,
        nombre="",
        contacto="",
        interes=f"PIDIO HABLAR CON UNA PERSONA. {motivo.strip()}".strip(),
        sala=sala.strip(),
    )
    return (
        "Le aviso a alguien del equipo. Si me dejas un telefono o un mail, "
        "te contactan mas rapido."
    )
