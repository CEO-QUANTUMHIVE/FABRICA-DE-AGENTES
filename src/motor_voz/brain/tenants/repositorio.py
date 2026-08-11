"""Unico punto del motor que habla con Supabase.

Ningun otro modulo instancia el cliente de Supabase ni arma una query.
Lo hace cumplir tests/test_un_solo_cliente_supabase.py, que recorre todo
src/motor_voz con AST y falla si aparece create_client/acreate_client
fuera de este archivo.

El aislamiento entre tenants depende de este archivo: cada metodo recibe
el tenant y lo aplica como filtro en cada query. Supabase se usa con la
SERVICE_ROLE_KEY, que saltea RLS por diseño, asi que RLS no es la
defensa real (spec S7) — la defensa es que ninguna query de aca sale sin
`.eq("tenant_id", ...)` o sin resolver antes el id del tenant por su slug.
"""

from __future__ import annotations

from supabase import AsyncClient, acreate_client

from motor_voz.brain.tenants.modelos import PerfilTenant, Servicio, Tenant, VozTenant
from motor_voz.config import Config


class TenantNoEncontrado(RuntimeError):
    """No existe un tenant activo con ese slug."""


async def _cliente(config: Config) -> AsyncClient:
    return await acreate_client(config.supabase_url, config.supabase_service_role_key)


async def tenant_de_dominio(config: Config, dominio: str) -> str | None:
    """Que tenant es dueño de este dominio, o None si no esta registrado.

    Es la defensa contra que cualquiera se lleve el agente de otro negocio.
    El dominio sale de la cabecera Origin, que el codigo de una pagina no
    puede falsear: una landing solo puede invocar al agente de su dueño.
    """
    if not dominio.strip():
        return None
    cliente = await _cliente(config)
    resp = (
        await cliente.table("tenant_dominios")
        .select("tenants(slug)")
        .eq("dominio", dominio.strip().lower())
        .maybe_single()
        .execute()
    )
    if resp is None or resp.data is None:
        return None
    return resp.data["tenants"]["slug"]


async def obtener_tenant(config: Config, slug: str) -> Tenant:
    """Trae un tenant completo: perfil, prompt propio, servicios y voz.

    Todo lo que trae esta filtrado por el tenant que se pide. No hay
    parametro ni camino que permita traer una fila de otro tenant.
    """
    cliente = await _cliente(config)

    tenant_resp = (
        await cliente.table("tenants")
        .select("id, slug, nombre, idioma, estado, perfil_slug")
        .eq("slug", slug)
        .eq("estado", "activo")
        .maybe_single()
        .execute()
    )
    if tenant_resp is None or tenant_resp.data is None:
        raise TenantNoEncontrado(f"No hay tenant activo con slug '{slug}'")
    datos_tenant = tenant_resp.data
    tenant_id = datos_tenant["id"]

    perfil_resp = (
        await cliente.table("agent_profiles")
        .select("slug, nombre, prompt_base")
        .eq("slug", datos_tenant["perfil_slug"])
        .single()
        .execute()
    )
    perfil = PerfilTenant(**perfil_resp.data)

    config_resp = (
        await cliente.table("tenant_configs")
        .select("prompt_propio")
        .eq("tenant_id", tenant_id)
        .maybe_single()
        .execute()
    )
    prompt_propio = (config_resp.data or {}).get("prompt_propio", "") if config_resp else ""

    servicios_resp = (
        await cliente.table("services")
        .select("nombre, descripcion")
        .eq("tenant_id", tenant_id)
        .eq("activo", True)
        .execute()
    )
    servicios = tuple(Servicio(**fila) for fila in servicios_resp.data)

    voz_resp = (
        await cliente.table("voice_profiles")
        .select("proveedor, voice_id, consentimiento_aprobado")
        .eq("tenant_id", tenant_id)
        .eq("estado", "aprobado")
        .maybe_single()
        .execute()
    )
    voz = VozTenant(**voz_resp.data) if voz_resp and voz_resp.data else None

    return Tenant(
        id=tenant_id,
        slug=datos_tenant["slug"],
        nombre=datos_tenant["nombre"],
        idioma=datos_tenant["idioma"],
        perfil=perfil,
        prompt_propio=prompt_propio,
        servicios=servicios,
        voz=voz,
    )
