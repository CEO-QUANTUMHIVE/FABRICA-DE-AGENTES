import pytest

from motor_voz.brain.tenants.modelos import PerfilTenant, Servicio, Tenant, VozTenant


def _tenant_de_prueba() -> Tenant:
    return Tenant(
        id="1",
        slug="quantumhive",
        nombre="QuantumHive",
        idioma="es",
        perfil=PerfilTenant(slug="receptor", nombre="Receptor", prompt_base="Identidad."),
        prompt_propio="",
        servicios=(Servicio(nombre="Web inteligente", descripcion="Pagina que conversa"),),
        voz=VozTenant(proveedor="fishaudio", voice_id="abc123", consentimiento_aprobado=True),
    )


def test_expone_los_campos():
    t = _tenant_de_prueba()
    assert t.slug == "quantumhive"
    assert t.perfil.slug == "receptor"
    assert t.servicios[0].nombre == "Web inteligente"
    assert t.voz.voice_id == "abc123"


def test_es_inmutable():
    t = _tenant_de_prueba()
    with pytest.raises(Exception):
        t.slug = "otro"  # type: ignore[misc]


def test_puede_no_tener_voz_propia():
    t = Tenant(
        id="2", slug="sin-voz", nombre="Sin Voz", idioma="es",
        perfil=PerfilTenant(slug="receptor", nombre="Receptor", prompt_base="Identidad."),
        prompt_propio="", servicios=(), voz=None,
    )
    assert t.voz is None
