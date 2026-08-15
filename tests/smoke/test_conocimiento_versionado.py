"""Borrador, publicacion, rollback y aislamiento contra Supabase real."""

import uuid

import pytest

from motor_voz.brain.tenants import repositorio
from motor_voz.config import cargar


pytestmark = pytest.mark.integracion


@pytest.fixture
async def tenants_reales():
    config = cargar()
    cliente = await repositorio._cliente(config)
    filas = (
        await cliente.table("tenants")
        .select("id, slug")
        .in_("slug", ["quantumhive", "demo_capilar"])
        .execute()
    ).data
    return config, {fila["slug"]: fila["id"] for fila in filas}


async def test_borrador_publicacion_y_rollback(tenants_reales):
    config, ids = tenants_reales
    cliente = await repositorio._cliente(config)
    clave = f"horario_prueba_{uuid.uuid4().hex}"
    conocimiento_id = None
    try:
        v1 = await repositorio.crear_borrador_conocimiento(
            config, tenant_id=ids["quantumhive"], categoria="horario",
            clave=clave, titulo="Horario de prueba",
            contenido={"lunes": "09:00-18:00"}, motivo="Version inicial"
        )
        conocimiento_id = v1["conocimiento_id"]

        antes = await repositorio.obtener_tenant(config, "quantumhive")
        assert clave not in {pieza.clave for pieza in antes.conocimiento}

        await repositorio.publicar_version_conocimiento(
            config, tenant_id=ids["quantumhive"], version_id=v1["version_id"]
        )
        publicado = await repositorio.obtener_tenant(config, "quantumhive")
        pieza = next(p for p in publicado.conocimiento if p.clave == clave)
        assert pieza.contenido["lunes"] == "09:00-18:00"

        v2 = await repositorio.crear_borrador_conocimiento(
            config, tenant_id=ids["quantumhive"], categoria="horario",
            clave=clave, titulo="Horario de prueba",
            contenido={"lunes": "10:00-19:00"}, motivo="Cambio de horario"
        )
        aun_v1 = await repositorio.obtener_tenant(config, "quantumhive")
        assert next(p for p in aun_v1.conocimiento if p.clave == clave).numero == 1

        await repositorio.publicar_version_conocimiento(
            config, tenant_id=ids["quantumhive"], version_id=v2["version_id"]
        )
        en_v2 = await repositorio.obtener_tenant(config, "quantumhive")
        assert next(p for p in en_v2.conocimiento if p.clave == clave).numero == 2

        await repositorio.publicar_version_conocimiento(
            config, tenant_id=ids["quantumhive"], version_id=v1["version_id"],
            motivo="Rollback de prueba"
        )
        restaurado = await repositorio.obtener_tenant(config, "quantumhive")
        assert next(p for p in restaurado.conocimiento if p.clave == clave).numero == 1

        otro = await repositorio.obtener_tenant(config, "demo_capilar")
        assert clave not in {pieza.clave for pieza in otro.conocimiento}

        with pytest.raises(Exception, match="no pertenece"):
            await repositorio.publicar_version_conocimiento(
                config, tenant_id=ids["demo_capilar"], version_id=v1["version_id"]
            )
    finally:
        if conocimiento_id:
            await cliente.table("conocimiento_tenant").delete().eq(
                "id", conocimiento_id
            ).execute()
