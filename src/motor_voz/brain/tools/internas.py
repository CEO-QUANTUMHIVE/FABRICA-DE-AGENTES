"""Lo que el dueño de un negocio le puede preguntar a su agente.

Todas son de LECTURA sobre lo propio. Ninguna escribe, y ninguna crea: dar de
alta un negocio o un agente es una operacion de la fabrica detras de login, no
de una conversacion (regla de Sergio, 2026-08-11).

Eso tambien acota el daño: aunque a alguien se le filtre el modo interno, lo
peor que puede hacer es leer.

Igual que las publicas, reciben el `Tenant` ya resuelto y **ninguna acepta un
identificador de negocio por argumento**.
"""

from __future__ import annotations

from motor_voz.brain.tenants import repositorio
from motor_voz.brain.tenants.modelos import Tenant
from motor_voz.config import Config


async def get_mis_leads(tenant: Tenant, config: Config, *, desde_dias: int = 30) -> str:
    """Los interesados que dejaron contacto en ESTE negocio."""
    # El modelo manda cualquier numero si el dueño dice "de todo el año".
    dias = max(1, min(int(desde_dias or 30), 365))
    leads = await repositorio.leads_de(config, tenant.id, desde_dias=dias)
    if not leads:
        return f"No hay contactos nuevos en los ultimos {dias} dias."

    lineas = []
    for lead in leads[:20]:
        quien = lead.nombre or "sin nombre"
        lineas.append(f"- {quien} ({lead.contacto}): {lead.interes or 'sin detalle'}")
    resumen = f"{len(leads)} contacto(s) en los ultimos {dias} dias:"
    if len(leads) > 20:
        resumen += " (te leo los 20 mas nuevos)"
    return resumen + "\n" + "\n".join(lineas)


async def get_mis_metricas(tenant: Tenant, config: Config, *, desde_dias: int = 30) -> str:
    """Como viene el negocio.

    Hoy solo cuenta contactos: las conversaciones todavia no se guardan, eso
    es de la Fase 10. Se dice lo que hay y no se estima nada.
    """
    dias = max(1, min(int(desde_dias or 30), 365))
    leads = await repositorio.leads_de(config, tenant.id, desde_dias=dias)
    pidieron_persona = sum(1 for lead in leads if "PIDIO HABLAR" in lead.interes)
    return (
        f"En los ultimos {dias} dias: {len(leads)} contacto(s), "
        f"{pidieron_persona} pidieron hablar con una persona.\n"
        "Todavia no estoy midiendo cuantas conversaciones hubo en total."
    )


async def get_mis_conversaciones(tenant: Tenant, config: Config, **_) -> str:
    """Todavia no se guardan las conversaciones.

    Devuelve un mensaje honesto en vez de fallar callado o inventar: un agente
    que promete un historial que no existe hace quedar mal al producto.
    """
    return (
        "Todavia no estoy guardando el historial de charlas. "
        "Lo que si tengo son los contactos que me dejaron."
    )
