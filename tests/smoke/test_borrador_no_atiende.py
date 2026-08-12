"""Un borrador no atiende a nadie hasta que se paga.

Es lo que separa "alguien probo la fabrica" de "hay un agente en produccion".
Sin esto, cualquiera que complete la entrevista tiene un agente vivo sin haber
pagado.

Corre contra Supabase real porque la garantia esta en la consulta, no en el
codigo Python: `obtener_tenant` filtra `estado = 'activo'` del lado de la
base. Probarlo con un mock probaria el mock.

    uv run pytest -m integracion tests/smoke/test_borrador_no_atiende.py -v
"""

from __future__ import annotations

import uuid

import pytest

from motor_voz.brain.tenants import repositorio
from motor_voz.config import cargar


@pytest.fixture
async def borrador():
    """Crea un borrador de prueba y lo borra al terminar."""
    config = cargar()
    cliente = await repositorio._cliente(config)
    slug = f"borrador_de_prueba_{uuid.uuid4().hex[:8]}"

    await (
        cliente.table("tenants")
        .insert(
            {
                "slug": slug,
                "nombre": "Negocio Sin Pagar",
                "perfil_slug": "capilar",
                "estado": "borrador",
            }
        )
        .execute()
    )
    yield slug
    await cliente.table("tenants").delete().eq("slug", slug).execute()


@pytest.mark.integracion
@pytest.mark.asyncio
async def test_un_borrador_no_se_puede_resolver(borrador):
    """Aunque sepas su slug, no hay forma de hablarle."""
    config = cargar()
    with pytest.raises(repositorio.TenantNoEncontrado):
        await repositorio.obtener_tenant(config, borrador)


@pytest.mark.integracion
@pytest.mark.asyncio
async def test_los_que_pagaron_si_se_resuelven(borrador):
    """La guarda: si esto fallara, el test de arriba pasaria por otra razon."""
    config = cargar()
    tenant = await repositorio.obtener_tenant(config, "quantumhive")
    assert tenant.slug == "quantumhive"


@pytest.mark.integracion
@pytest.mark.asyncio
async def test_pagar_lo_pone_en_produccion(borrador):
    """El pago es lo unico que lo hace existir de verdad."""
    config = cargar()
    cliente = await repositorio._cliente(config)

    await (
        cliente.table("tenants")
        .update({"estado": "activo", "activo_desde": "now()"})
        .eq("slug", borrador)
        .execute()
    )

    tenant = await repositorio.obtener_tenant(config, borrador)
    assert tenant.slug == borrador
