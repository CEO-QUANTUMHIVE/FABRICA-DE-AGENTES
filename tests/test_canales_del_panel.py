"""Configuracion de WhatsApp aislada por tenant y sin tokens en el navegador."""

from __future__ import annotations

import pytest

from motor_voz import config as config_mod
from motor_voz.api import servidor
from motor_voz.brain.tenants.modelos import PerfilTenant, Tenant
from motor_voz.channels.whatsapp.onboarding import ConexionAutorizada

DUENO = "sergio"
EMPLEADO = "empleado"


def _config(**cambios):
    entorno = {
        "GROQ_API_KEY": "x",
        "FISH_API_KEY": "x",
        "LIVEKIT_URL": "wss://ejemplo",
        "LIVEKIT_API_KEY": "x",
        "LIVEKIT_API_SECRET": "x",
        "SUPABASE_URL": "https://ejemplo.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "x",
    }
    entorno.update(cambios)
    return config_mod.cargar(entorno)


class _Canales:
    def __init__(self):
        self.guardados: list[dict] = []
        self.filas = [
            {
                "id": "canal-1",
                "canal": "whatsapp",
                "cuenta_externa_id": "123456789",
                "nombre": "WhatsApp QuantumHive",
                "estado": "pendiente",
                "secreto_ref": "whatsapp_quantumhive",
            }
        ]

    async def usuario_de_token(self, config, token):
        return token if token in {DUENO, EMPLEADO} else None

    async def obtener_tenant(self, config, slug):
        return Tenant(
            id="tenant-qh",
            slug=slug,
            nombre="QuantumHive",
            idioma="es",
            perfil=PerfilTenant(slug="receptor", nombre="Receptor", prompt_base=""),
            prompt_propio="",
            servicios=(),
            voz=None,
        )

    async def rol(self, config, usuario_id, tenant_id):
        return "dueño" if usuario_id == DUENO else "empleado"

    async def listar(self, config, tenant_id):
        assert tenant_id == "tenant-qh"
        return self.filas

    async def configurar(self, config, **datos):
        self.guardados.append(datos)
        return {"id": "canal-1", **datos}


@pytest.fixture
def canales():
    return _Canales()


async def _cliente(
    aiohttp_client,
    canales,
    config=None,
    completar_whatsapp_fn=None,
    guardar_secreto_whatsapp_fn=None,
):
    app = servidor.crear_app(
        config or _config(),
        obtener_tenant=canales.obtener_tenant,
        usuario_de_token=canales.usuario_de_token,
        rol_de_usuario_en_tenant=canales.rol,
        canales_para_panel=canales.listar,
        configurar_whatsapp_fn=canales.configurar,
        completar_whatsapp_fn=completar_whatsapp_fn,
        guardar_secreto_whatsapp_fn=guardar_secreto_whatsapp_fn,
    )
    return await aiohttp_client(app)


def _auth(usuario=DUENO):
    return {"Authorization": f"Bearer {usuario}"}


async def test_listar_no_expone_referencia_ni_token(aiohttp_client, canales):
    cliente = await _cliente(aiohttp_client, canales)
    respuesta = await cliente.get(
        "/api/panel/quantumhive/canales", headers=_auth()
    )

    cuerpo = await respuesta.json()
    canal = cuerpo["canales"][0]
    assert respuesta.status == 200
    assert "secreto_ref" not in canal
    assert "token" not in canal
    assert canal["preparacion"]["token_configurado"] is False


async def test_solo_el_dueno_puede_configurar(aiohttp_client, canales):
    cliente = await _cliente(aiohttp_client, canales)
    respuesta = await cliente.post(
        "/api/panel/quantumhive/canales/whatsapp",
        json={"phone_number_id": "123456789"},
        headers=_auth(EMPLEADO),
    )

    assert respuesta.status == 403
    assert canales.guardados == []


async def test_guardar_genera_la_referencia_en_el_servidor(aiohttp_client, canales):
    cliente = await _cliente(aiohttp_client, canales)
    respuesta = await cliente.post(
        "/api/panel/quantumhive/canales/whatsapp",
        json={"phone_number_id": "123456789", "nombre": "Ventas"},
        headers=_auth(),
    )

    assert respuesta.status == 200
    guardado = canales.guardados[0]
    assert guardado["tenant_id"] == "tenant-qh"
    assert guardado["secreto_ref"] == "whatsapp_quantumhive"
    assert guardado["estado"] == "pendiente"


async def test_no_declara_conectado_si_faltan_secretos(aiohttp_client, canales):
    cliente = await _cliente(aiohttp_client, canales)
    respuesta = await cliente.post(
        "/api/panel/quantumhive/canales/whatsapp",
        json={"phone_number_id": "123456789", "confirmar": True},
        headers=_auth(),
    )

    assert respuesta.status == 409
    assert canales.guardados == []


async def test_conecta_cuando_el_servidor_esta_listo(
    aiohttp_client, canales, monkeypatch
):
    monkeypatch.setenv("SECRETO_WHATSAPP_QUANTUMHIVE", "token-real-simulado")
    cliente = await _cliente(
        aiohttp_client,
        canales,
        _config(META_APP_SECRET="firma", WHATSAPP_VERIFY_TOKEN="verificacion"),
    )
    respuesta = await cliente.post(
        "/api/panel/quantumhive/canales/whatsapp",
        json={"phone_number_id": "123456789", "confirmar": True},
        headers=_auth(),
    )

    assert respuesta.status == 200
    assert canales.guardados[0]["estado"] == "conectado"


async def test_embedded_signup_asigna_numero_y_oculta_token(
    aiohttp_client, canales, monkeypatch, tmp_path
):
    monkeypatch.setenv("WHATSAPP_SECRET_DIR", str(tmp_path))
    secretos_guardados = []

    async def completar(config, **datos):
        assert datos["code"] == "codigo-temporal"
        assert datos["waba_id"] == "333333"
        return ConexionAutorizada(
            waba_id="333333",
            phone_number_id="444444",
            numero="+54 9 11 5555-5555",
            nombre="QuantumHive",
            access_token="token-super-secreto",
        )

    cliente = await _cliente(
        aiohttp_client,
        canales,
        _config(
            META_APP_ID="111111",
            META_APP_SECRET="firma",
            META_EMBEDDED_SIGNUP_CONFIG_ID="222222",
            WHATSAPP_VERIFY_TOKEN="verificacion",
            WHATSAPP_REGISTRATION_PIN="123456",
        ),
        completar_whatsapp_fn=completar,
        guardar_secreto_whatsapp_fn=lambda ref, token: secretos_guardados.append(
            (ref, token)
        ),
    )
    respuesta = await cliente.post(
        "/api/panel/quantumhive/canales/whatsapp/onboarding/completar",
        json={
            "code": "codigo-temporal",
            "waba_id": "333333",
            "phone_number_id": "444444",
        },
        headers=_auth(),
    )

    cuerpo = await respuesta.json()
    assert respuesta.status == 200
    assert [fila["estado"] for fila in canales.guardados[-2:]] == [
        "pendiente",
        "conectado",
    ]
    assert secretos_guardados == [
        ("whatsapp_quantumhive", "token-super-secreto")
    ]
    assert cuerpo["canal"]["cuenta_externa_id"] == "444444"
    assert "token-super-secreto" not in str(cuerpo)
    assert "secreto_ref" not in cuerpo["canal"]


async def test_configuracion_embedded_signup_solo_expone_datos_publicos(
    aiohttp_client, canales, monkeypatch, tmp_path
):
    monkeypatch.setenv("WHATSAPP_SECRET_DIR", str(tmp_path))
    cliente = await _cliente(
        aiohttp_client,
        canales,
        _config(
            META_APP_ID="111111",
            META_APP_SECRET="firma-privada",
            META_EMBEDDED_SIGNUP_CONFIG_ID="222222",
            WHATSAPP_VERIFY_TOKEN="verificacion-privada",
            WHATSAPP_REGISTRATION_PIN="123456",
        ),
    )
    respuesta = await cliente.get(
        "/api/panel/quantumhive/canales/whatsapp/onboarding", headers=_auth()
    )

    cuerpo = await respuesta.json()
    assert respuesta.status == 200
    assert cuerpo["disponible"] is True
    assert cuerpo["app_id"] == "111111"
    assert cuerpo["configuration_id"] == "222222"
    assert "firma-privada" not in str(cuerpo)
    assert "verificacion-privada" not in str(cuerpo)
    assert "123456" not in str(cuerpo)
