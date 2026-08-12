"""Que las voces que tenemos guardadas existan de verdad en Fish.

Escrito el 2026-08-11, despues de que un voice_id inventado dejara la landing
sin voz durante horas.

**Por que fallo en silencio y nadie lo vio:**

El valor sembrado y el real compartian los primeros doce caracteres
(`63f9f124b940`), y el log del agente trunca el voice_id justo a doce. En
pantalla se veia identico al del `.env`. Fish devolvia 404, el plugin no
levantaba error visible, el LLM seguia contestando, y lo unico que pasaba era
que no se escuchaba nada.

Un `voice_id` roto **no da error**: da silencio. Por eso hace falta un test.

Corre contra la API de Fish, asi que no va por defecto:

    uv run pytest -m smoke tests/smoke/test_voces_existen.py -v
"""

from __future__ import annotations

import httpx
import pytest

from motor_voz.brain.tenants import repositorio
from motor_voz.config import cargar

TENANTS = ("quantumhive", "demo_capilar")


@pytest.mark.smoke
@pytest.mark.asyncio
@pytest.mark.parametrize("slug", TENANTS)
async def test_la_voz_del_tenant_existe_en_fish(slug):
    config = cargar()
    tenant = await repositorio.obtener_tenant(config, slug)

    assert tenant.voz is not None, f"{slug} no tiene voz configurada"
    voice_id = tenant.voz.voice_id

    async with httpx.AsyncClient(timeout=30) as cliente:
        r = await cliente.get(
            f"https://api.fish.audio/model/{voice_id}",
            headers={"Authorization": f"Bearer {config.fish_api_key}"},
        )

    assert r.status_code == 200, (
        f"El voice_id de '{slug}' ({voice_id}) no existe en Fish: HTTP "
        f"{r.status_code}. El agente va a contestar y no se va a escuchar nada."
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_la_voz_del_env_tambien_existe():
    """El fallback: lo que se usa cuando un tenant no tiene voz propia."""
    config = cargar()
    if not config.fish_voice_id.strip():
        pytest.skip("no hay FISH_VOICE_ID configurado")

    async with httpx.AsyncClient(timeout=30) as cliente:
        r = await cliente.get(
            f"https://api.fish.audio/model/{config.fish_voice_id.strip()}",
            headers={"Authorization": f"Bearer {config.fish_api_key}"},
        )

    assert r.status_code == 200, f"FISH_VOICE_ID no existe en Fish: HTTP {r.status_code}"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_dos_tenants_no_comparten_voz():
    """Si comparten, el gate de oido de la Fase 8 no prueba nada."""
    config = cargar()
    voces = {}
    for slug in TENANTS:
        tenant = await repositorio.obtener_tenant(config, slug)
        voces[slug] = tenant.voz.voice_id if tenant.voz else None
    assert len(set(voces.values())) == len(voces), f"voces repetidas: {voces}"
