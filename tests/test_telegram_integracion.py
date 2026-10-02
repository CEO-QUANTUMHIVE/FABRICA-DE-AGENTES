"""Tests de integración para el canal de Telegram: webhook y procesamiento de eventos."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, Mock

import pytest

from motor_voz import config as config_mod
from motor_voz.brain.mensajes import MensajeEntrante
from motor_voz.brain.tenants.modelos import PerfilTenant, Servicio, Tenant
from motor_voz.channels.telegram import bot, webhook
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
async def test_calcular_clave_idempotencia():
    """Prueba que la clave de idempotencia se calcule correctamente."""
    update = {
        "update_id": 123456,
        "message": {
            "message_id": 789,
            "from": {"id": 111, "first_name": "Test"},
            "chat": {"id": 999, "type": "private"},
            "date": 1700000000,
            "text": "Hola Telegram"
        }
    }
    
    clave = webhook.calcular_clave_idempotencia(update)
    assert isinstance(clave, str)
    assert len(clave) == 64  # SHA256 produce hashes de 64 caracteres hexadecimales
    
    # Dos updates idénticos deben producir la misma clave
    clave2 = webhook.calcular_clave_idempotencia(update)
    assert clave == clave2


@pytest.mark.asyncio
async def test_manipular_webhook_registro_exitoso(config_vacia: Config):
    """Prueba que el webhook registre correctamente un mensaje entrante."""
    # Mockear el repositorio para evitar llamadas a Supabase
    from motor_voz.brain.tenants import repositorio
    
    # Datos del tenant
    tenant_id = "test-tenant-id"
    tenant_canal_id = "test-canal-id"
    
    # Datos del mensaje
    update = {
        "update_id": 123456,
        "message": {
            "message_id": 789,
            "from": {"id": 111, "first_name": "Test User"},
            "chat": {"id": 999, "type": "private"},
            "date": 1700000000,
            "text": "Hola, quiero información sobre pruebas de fondeo"
        }
    }
    
    # Mockear la función de registro
    mock_resultado_registro = Mock()
    mock_resultado_registro.duplicado = False
    mock_resultado_registro.inbox_id = "inbox-test-id"
    mock_resultado_registro.conversacion_id = "conv-test-id"
    mock_resultado_registro.mensaje_id = "msg-test-id"
    
    # Creamos un mock para el repositorio
    original_registrar = repositorio.registrar_mensaje_entrante
    repositorio.registrar_mensaje_entrante = AsyncMock(return_value=mock_resultado_registro)
    
    try:
        # Llamar a la función
        resultado = await webhook.manejar_webhook(
            config_vacia, 
            tenant_canal_id, 
            tenant_id, 
            update
        )
        
        # Verificar que se llamó correctamente
        assert resultado["ok"] is True
        assert resultado["duplicado"] is False
        assert resultado["evento_id"] == "inbox-test-id"
        assert resultado["conversacion_id"] == "conv-test-id"
        assert resultado["mensaje_id"] == "msg-test-id"
        
        # Verificar que se llamó a la función de registro con los parámetros correctos
        repositorio.registrar_mensaje_entrante.assert_called_once()
        args, kwargs = repositorio.registrar_mensaje_entrante.call_args
        assert kwargs["tenant_canal_id"] == tenant_canal_id
        
        # Verificar que se creó el objeto MensajeEntrante correctamente
        mensaje = kwargs["mensaje"]
        assert isinstance(mensaje, MensajeEntrante)
        assert mensaje.tenant_id == tenant_id
        assert mensaje.canal == "telegram"
        assert mensaje.conversacion_externa_id == "999"
        assert mensaje.remitente_externo_id == "999"
        assert mensaje.texto == "Hola, quiero información sobre pruebas de fondeo"
        
    finally:
        # Restaurar la función original
        repositorio.registrar_mensaje_entrante = original_registrar


@pytest.mark.asyncio
async def test_manipular_webhook_mensaje_sin_texto(config_vacia: Config):
    """Prueba que el webhook maneje correctamente un mensaje sin texto."""
    from motor_voz.brain.tenants import repositorio
    
    # Datos del tenant
    tenant_id = "test-tenant-id"
    tenant_canal_id = "test-canal-id"
    
    # Update con mensaje sin texto (por ejemplo, una foto)
    update = {
        "update_id": 123456,
        "message": {
            "message_id": 789,
            "from": {"id": 111, "first_name": "Test User"},
            "chat": {"id": 999, "type": "private"},
            "date": 1700000000,
            "photo": [{"file_id": "abc123", "width": 100, "height": 100}]
        }
    }
    
    # Mockear la función de registro
    mock_resultado_registro = Mock()
    mock_resultado_registro.duplicado = False
    mock_resultado_registro.inbox_id = "inbox-test-id"
    mock_resultado_registro.conversacion_id = "conv-test-id"
    mock_resultado_registro.mensaje_id = "msg-test-id"
    
    repositorio.registrar_mensaje_entrante = AsyncMock(return_value=mock_resultado_registro)
    
    try:
        # Llamar a la función
        resultado = await webhook.manejar_webhook(
            config_vacia, 
            tenant_canal_id, 
            tenant_id, 
            update
        )
        
        # Verificar que se procesó correctamente
        assert resultado["ok"] is True
        assert resultado["duplicado"] is False
        
        # Verificar que se creó el objeto MensajeEntrante con texto vacío
        args, kwargs = repositorio.registrar_mensaje_entrante.call_args
        mensaje = kwargs["mensaje"]
        assert isinstance(mensaje, MensajeEntrante)
        assert mensaje.texto == ""
        
    finally:
        repositorio.registrar_mensaje_entrante = repositorio.registrar_mensaje_entrante


@pytest.mark.asyncio
async def test_procesar_actualizacion_registro_durable(config_vacia: Config):
    """Prueba que procesar_actualizacion registre el mensaje en el pipeline durable."""
    from motor_voz.brain.tenants import repositorio
    from motor_voz.brain.mensajes import Turno
    
    # Crear un tenant de prueba
    tenant = Tenant(
        id="test-tenant-id",
        slug="test-tenant",
        nombre="Test Tenant",
        idioma="es",
        perfil=PerfilTenant(
            slug="test-profile",
            nombre="Test Profile",
            prompt_base="Prompt de prueba",
        ),
        prompt_propio="",
        servicios=(Servicio(nombre="Test Service", descripcion="Test Description"),),
        voz=None,
    )
    
    # Update de Telegram
    actualizacion = {
        "update_id": 123456,
        "message": {
            "message_id": 789,
            "chat": {"id": 999},
            "from": {"first_name": "Test User"},
            "text": "Mensaje de prueba para pipeline durable",
            "date": 1700000000
        },
    }
    
    # Mockear las funciones necesarias
    mock_canal = Mock()
    mock_canal.id = "test-canal-id"
    
    repositorio.canal_de_cuenta = AsyncMock(return_value=mock_canal)
    
    mock_resultado_registro = Mock()
    mock_resultado_registro.duplicado = False
    mock_resultado_registro.inbox_id = "inbox-test-id"
    mock_resultado_registro.conversacion_id = "conv-test-id"
    mock_resultado_registro.mensaje_id = "msg-test-id"
    
    repositorio.registrar_mensaje_entrante = AsyncMock(return_value=mock_resultado_registro)
    
    try:
        # Llamar a la función
        resultado = await bot.procesar_actualizacion(
            config_vacia,
            tenant,
            actualizacion,
            token="dummy-token",
        )
        
        # El resultado debería ser None porque el mensaje se procesa en el pipeline durable
        assert resultado is None
        
        # Verificar que se llamó a la función de registro con los parámetros correctos
        repositorio.registrar_mensaje_entrante.assert_called_once()
        args, kwargs = repositorio.registrar_mensaje_entrante.call_args
        mensaje = kwargs["mensaje"]
        
        assert isinstance(mensaje, MensajeEntrante)
        assert mensaje.tenant_id == tenant.id
        assert mensaje.canal == "telegram"
        assert mensaje.conversacion_externa_id == "999"
        assert mensaje.remitente_externo_id == "999"
        assert mensaje.texto == "Mensaje de prueba para pipeline durable"
        
    finally:
        repositorio.canal_de_cuenta = repositorio.canal_de_cuenta
        repositorio.registrar_mensaje_entrante = repositorio.registrar_mensaje_entrante


def test_decodificar_payload_inicio_telegram():
    """Prueba que la decodificación de payloads de inicio funcione correctamente."""
    # Caso básico
    resultado = bot.decodificar_payload_inicio("/start")
    assert "Hola" in resultado
    
    # Caso con tag app
    resultado = bot.decodificar_payload_inicio("/start app_challenge_FTMO_100K")
    assert "FTMO" in resultado
    assert "100K" in resultado
    assert "Superar evaluación" in resultado
    
    # Caso con payload codificado en base64
    payload = {
        "service": "live",
        "firm": "Apex",
        "size": "50K",
        "stage": "Cuenta funded simulada",
    }
    b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    resultado = bot.decodificar_payload_inicio(f"/start b64_{b64}")
    assert "Apex" in resultado
    assert "50K" in resultado
    assert "Administrar cuenta live" in resultado
    assert "Cuenta funded simulada" in resultado