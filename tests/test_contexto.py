from motor_voz.brain.contexto import construir_contexto
from motor_voz.brain.prompt import ENTREGA_LIVE
from motor_voz.brain.tenants.modelos import ConocimientoTenant, PerfilTenant, Servicio, Tenant

QUANTUMHIVE = Tenant(
    id="1", slug="quantumhive", nombre="QuantumHive", idioma="es",
    perfil=PerfilTenant(slug="receptor", nombre="Receptor", prompt_base="Identidad de QuantumHive."),
    prompt_propio="",
    servicios=(Servicio(nombre="Web inteligente", descripcion="Pagina que conversa"),),
    voz=None,
)

DEMO_CAPILAR = Tenant(
    id="2", slug="demo_capilar", nombre="Barberia Demo", idioma="es",
    perfil=PerfilTenant(slug="capilar", nombre="Barberia", prompt_base="Identidad de barberia."),
    prompt_propio="Atendes en la barberia demo.",
    servicios=(Servicio(nombre="Corte clasico", descripcion="Corte tradicional"),),
    voz=None,
)

CON_CONOCIMIENTO = Tenant(
    id="3", slug="comercio", nombre="Comercio", idioma="es",
    perfil=PerfilTenant(slug="comercio", nombre="Comercio", prompt_base="Identidad."),
    prompt_propio="",
    servicios=(), voz=None,
    conocimiento=(
        ConocimientoTenant(
            id="c1", categoria="horario", clave="horario_general",
            titulo="Horario habitual", version_id="v2", numero=2,
            contenido={"lunes_a_viernes": "09:00-18:00"},
        ),
        ConocimientoTenant(
            id="c2", categoria="precio", clave="corte",
            titulo="Precio corte", version_id="v1", numero=1,
            contenido={"moneda": "ARS", "precio": 25000},
        ),
    ),
)


def test_usa_la_identidad_propia_del_tenant():
    p = construir_contexto(QUANTUMHIVE)
    assert "Identidad de QuantumHive." in p


def test_no_mezcla_identidades_entre_tenants():
    p_a = construir_contexto(QUANTUMHIVE)
    p_b = construir_contexto(DEMO_CAPILAR)
    assert "Identidad de barberia." not in p_a
    assert "Identidad de QuantumHive." not in p_b


def test_lista_solo_los_servicios_propios():
    p_a = construir_contexto(QUANTUMHIVE)
    p_b = construir_contexto(DEMO_CAPILAR)
    assert "Web inteligente" in p_a
    assert "Corte clasico" not in p_a
    assert "Corte clasico" in p_b
    assert "Web inteligente" not in p_b


def test_incluye_el_prompt_propio_del_tenant():
    assert "Atendes en la barberia demo." in construir_contexto(DEMO_CAPILAR)


def test_respeta_motor_y_canal():
    p = construir_contexto(QUANTUMHIVE, motor="gemini", canal="web")
    assert ENTREGA_LIVE in p


def test_un_tenant_sin_servicios_no_rompe():
    sin_servicios = Tenant(
        id="3", slug="nuevo", nombre="Nuevo", idioma="es",
        perfil=PerfilTenant(slug="receptor", nombre="Receptor", prompt_base="Identidad."),
        prompt_propio="Prompt propio sin servicios todavia.",
        servicios=(), voz=None,
    )
    p = construir_contexto(sin_servicios)
    assert "Prompt propio sin servicios todavia." in p


def test_incluye_solo_conocimiento_publicado_del_tenant():
    p = construir_contexto(CON_CONOCIMIENTO)
    assert "Conocimiento aprobado y vigente" in p
    assert "09:00-18:00" in p
    assert '"precio":25000' in p


def test_conocimiento_no_se_mezcla_con_otro_tenant():
    assert "09:00-18:00" not in construir_contexto(QUANTUMHIVE)
