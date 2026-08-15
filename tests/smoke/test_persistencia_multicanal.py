"""Persistencia multicanal contra Supabase real.

Prueba las dos garantias que no sirven con mocks: que un reintento no duplique
mensajes y que ni siquiera la SERVICE_ROLE pueda cruzar tenant/canal por error.
"""

from datetime import datetime, timezone
import uuid

import pytest

from motor_voz.brain.mensajes import MensajeEntrante
from motor_voz.brain.tenants import repositorio
from motor_voz.config import cargar


pytestmark = pytest.mark.integracion


@pytest.fixture
async def canales_reales():
    config = cargar()
    cliente = await repositorio._cliente(config)
    tenants = (
        await cliente.table("tenants")
        .select("id, slug")
        .in_("slug", ["quantumhive", "demo_capilar"])
        .execute()
    ).data
    ids = {fila["slug"]: fila["id"] for fila in tenants}
    sufijo = uuid.uuid4().hex
    filas = [
        {
            "tenant_id": ids["quantumhive"],
            "canal": "whatsapp",
            "cuenta_externa_id": f"qh-{sufijo}",
            "nombre": "Prueba QuantumHive",
            "estado": "conectado",
        },
        {
            "tenant_id": ids["demo_capilar"],
            "canal": "whatsapp",
            "cuenta_externa_id": f"demo-{sufijo}",
            "nombre": "Prueba Demo",
            "estado": "conectado",
        },
    ]
    creados = (await cliente.table("tenant_canales").insert(filas).execute()).data
    try:
        yield config, {fila["tenant_id"]: fila for fila in creados}, ids
    finally:
        for fila in creados:
            await cliente.table("tenant_canales").delete().eq("id", fila["id"]).execute()


def _mensaje(tenant_id: str, *, evento: str = "evento-1") -> MensajeEntrante:
    return MensajeEntrante(
        tenant_id=tenant_id,
        canal="whatsapp",
        conversacion_externa_id="conversacion-externa-compartida",
        remitente_externo_id="contacto-externo-compartido",
        evento_externo_id=evento,
        mensaje_externo_id="mensaje-externo-compartido",
        texto="Hola",
        recibido_en=datetime.now(timezone.utc),
        payload={"tipo": "texto"},
    )


async def test_reintento_no_duplica_y_dos_tenants_no_se_mezclan(canales_reales):
    config, canales_por_tenant, ids = canales_reales
    qh = canales_por_tenant[ids["quantumhive"]]
    demo = canales_por_tenant[ids["demo_capilar"]]

    primero = await repositorio.registrar_mensaje_entrante(
        config, tenant_canal_id=qh["id"], mensaje=_mensaje(ids["quantumhive"])
    )
    repetido = await repositorio.registrar_mensaje_entrante(
        config, tenant_canal_id=qh["id"], mensaje=_mensaje(ids["quantumhive"])
    )
    otro_tenant = await repositorio.registrar_mensaje_entrante(
        config, tenant_canal_id=demo["id"], mensaje=_mensaje(ids["demo_capilar"])
    )

    assert not primero.duplicado
    assert repetido.duplicado
    assert not otro_tenant.duplicado
    assert primero.conversacion_id != otro_tenant.conversacion_id

    conversaciones_qh = await repositorio.conversaciones_de(config, ids["quantumhive"])
    conversaciones_demo = await repositorio.conversaciones_de(config, ids["demo_capilar"])
    assert {c.id for c in conversaciones_qh} >= {primero.conversacion_id}
    assert {c.id for c in conversaciones_demo} >= {otro_tenant.conversacion_id}

    mensajes_cruzados = await repositorio.mensajes_de_conversacion(
        config,
        tenant_id=ids["demo_capilar"],
        conversacion_id=primero.conversacion_id,
    )
    assert mensajes_cruzados == []


async def test_un_canal_no_acepta_el_tenant_del_otro(canales_reales):
    config, canales_por_tenant, ids = canales_reales
    canal_qh = canales_por_tenant[ids["quantumhive"]]

    with pytest.raises(Exception, match="no pertenece al tenant"):
        await repositorio.registrar_mensaje_entrante(
            config,
            tenant_canal_id=canal_qh["id"],
            mensaje=_mensaje(ids["demo_capilar"], evento="evento-cruzado"),
        )
