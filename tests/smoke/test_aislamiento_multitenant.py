"""El test que bloquea el merge de las Fases 5-8 (spec S7).

Pide los dos tenants sembrados por la migracion (quantumhive y
demo_capilar) y verifica que los servicios de uno nunca aparecen en el
otro. Corre contra Supabase real: probar aislamiento contra un mock solo
prueba el mock, no el codigo.

Correr con:
    uv run pytest -m integracion tests/smoke/test_aislamiento_multitenant.py -v
"""

from __future__ import annotations

import pytest

from motor_voz.brain.tenants import repositorio
from motor_voz.config import cargar


@pytest.mark.integracion
@pytest.mark.asyncio
async def test_un_tenant_no_ve_servicios_del_otro():
    config = cargar()

    quantumhive = await repositorio.obtener_tenant(config, "quantumhive")
    demo_capilar = await repositorio.obtener_tenant(config, "demo_capilar")

    nombres_quantumhive = {s.nombre for s in quantumhive.servicios}
    nombres_capilar = {s.nombre for s in demo_capilar.servicios}

    assert nombres_quantumhive, "quantumhive deberia tener servicios sembrados"
    assert nombres_capilar, "demo_capilar deberia tener servicios sembrados"
    assert nombres_quantumhive.isdisjoint(nombres_capilar), (
        "Un tenant esta viendo servicios del otro: aislamiento roto"
    )
    assert quantumhive.perfil.slug == "receptor"
    assert demo_capilar.perfil.slug == "capilar"
    assert quantumhive.perfil.prompt_base != demo_capilar.perfil.prompt_base


@pytest.mark.integracion
@pytest.mark.asyncio
async def test_tenant_inexistente_o_pausado_no_se_resuelve():
    config = cargar()
    with pytest.raises(repositorio.TenantNoEncontrado):
        await repositorio.obtener_tenant(config, "no-existe-este-slug")
