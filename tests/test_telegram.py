"""Tests del adaptador de Telegram: cliente HTTP y procesamiento de inicio."""

from __future__ import annotations

import base64
import json
import pytest

from motor_voz import config as config_mod
from motor_voz.channels.telegram import bot, cliente
from motor_voz.config import Config


@pytest.fixture
def config_vacia() -> Config:
    return config_mod.cargar(
        {
            "GROQ_API_KEY": "x",
            "FISH_API_KEY": "x",
            "LIVEKIT_URL": "wss://ejemplo",
            "LIVEKIT_API_KEY": "x",
            "LIVEKIT_API_SECRET": "x",
            "SUPABASE_URL": "https://ejemplo.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "x",
        }
    )


@pytest.mark.asyncio
async def test_enviar_texto_ok(config_vacia: Config):
    async def fake_pedir(url: str, cuerpo: dict) -> tuple[int, dict]:
        assert "bot_token_123" in url
        assert cuerpo["chat_id"] == "987654"
        assert cuerpo["text"] == "Hola desde QuantumHive"
        return 200, {"ok": True, "result": {"message_id": 555}}

    res = await cliente.enviar_texto(
        config_vacia,
        token="bot_token_123",
        chat_id="987654",
        texto="Hola desde QuantumHive",
        pedir=fake_pedir,
    )
    assert res.ok is True
    assert res.mensaje_externo_id == "555"
    assert res.reintentable is True


@pytest.mark.asyncio
async def test_enviar_texto_bloqueado_es_permanente(config_vacia: Config):
    async def fake_pedir(url: str, cuerpo: dict) -> tuple[int, dict]:
        return 403, {"ok": False, "description": "Forbidden: bot was blocked by the user"}

    res = await cliente.enviar_texto(
        config_vacia,
        token="bot_token_123",
        chat_id="987654",
        texto="Hola",
        pedir=fake_pedir,
    )
    assert res.ok is False
    assert res.reintentable is False
    assert "bloqueado" in res.error


@pytest.mark.asyncio
async def test_enviar_texto_rate_limit_es_reintentable(config_vacia: Config):
    async def fake_pedir(url: str, cuerpo: dict) -> tuple[int, dict]:
        return 429, {"ok": False, "description": "Too Many Requests"}

    res = await cliente.enviar_texto(
        config_vacia,
        token="bot_token_123",
        chat_id="987654",
        texto="Hola",
        pedir=fake_pedir,
    )
    assert res.ok is False
    assert res.reintentable is True


@pytest.mark.asyncio
async def test_enviar_sin_token_falla_cerrado(config_vacia: Config):
    res = await cliente.enviar_texto(
        config_vacia,
        token="",
        chat_id="987654",
        texto="Hola",
    )
    assert res.ok is False
    assert res.reintentable is False


def test_decodificar_payload_inicio_simple():
    res = bot.decodificar_payload_inicio("/start")
    assert "Take Prop" in res


def test_decodificar_payload_inicio_app_tag():
    res = bot.decodificar_payload_inicio("/start app_challenge_FTMO_100K")
    assert "FTMO" in res
    assert "100K" in res
    assert "Superar evaluación" in res


def test_decodificar_payload_inicio_base64():
    payload = {
        "service": "live",
        "firm": "Apex",
        "size": "50K",
        "stage": "Cuenta funded simulada",
    }
    b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    res = bot.decodificar_payload_inicio(f"/start b64_{b64}")
    assert "Apex" in res
    assert "50K" in res
    assert "Administrar cuenta live" in res
    assert "Cuenta funded simulada" in res


@pytest.mark.asyncio
async def test_procesar_actualizacion_flujo_completo(config_vacia: Config):
    from motor_voz.brain.tenants.modelos import PerfilTenant, Servicio, Tenant
    from motor_voz.brain.tenants import repositorio
    from unittest.mock import AsyncMock, Mock

    tenant = Tenant(
        id="t-1",
        slug="takepropfit",
        nombre="Take Prop",
        idioma="es",
        perfil=PerfilTenant(
            slug="takeprop",
            nombre="Take Prop",
            prompt_base="Sos el asistente de Take Prop. Pruebas de fondeo 50/50 sin anticipo.",
        ),
        prompt_propio="",
        servicios=(Servicio(nombre="Retos de fondeo", descripcion="Sin costo inicial"),),
        voz=None,
    )

    actualizacion = {
        "update_id": 1,
        "message": {
            "message_id": 100,
            "chat": {"id": 12345},
            "from": {"first_name": "Trader"},
            "text": "/start app_challenge_FTMO_100K",
        },
    }

    llamadas_responder = []
    llamadas_enviar = []

    async def fake_responder(config, tenant, mensaje, *, historial, canal):
        llamadas_responder.append((mensaje, canal))
        return "¡Hola Trader! Vi tu interés en superar un reto de 100K en FTMO."

    async def fake_enviar(config, *, token, chat_id, texto, **kwargs):
        llamadas_enviar.append((token, chat_id, texto))
        return cliente.Resultado(ok=True, mensaje_externo_id="msg-999")

    # Mockear las funciones que requieren conexión a Supabase
    mock_canal = Mock()
    mock_canal.id = "test-canal-id"
    
    original_canal_de_cuenta = repositorio.canal_de_cuenta
    original_registrar_mensaje = repositorio.registrar_mensaje_entrante
    
    repositorio.canal_de_cuenta = AsyncMock(return_value=mock_canal)
    repositorio.registrar_mensaje_entrante = AsyncMock(return_value=Mock(duplicado=False))

    try:
        res = await bot.procesar_actualizacion(
            config_vacia,
            tenant,
            actualizacion,
            token="token_test",
            enviar_fn=fake_enviar,
            responder_fn=fake_responder,
        )

        # Verificar que las funciones mockeadas fueron llamadas
        assert repositorio.canal_de_cuenta.called
        assert repositorio.registrar_mensaje_entrante.called
        
        # El resultado debería ser None porque el mensaje se procesa en el pipeline durable
        assert res is None
        
    finally:
        # Restaurar las funciones originales
        repositorio.canal_de_cuenta = original_canal_de_cuenta
        repositorio.registrar_mensaje_entrante = original_registrar_mensaje

