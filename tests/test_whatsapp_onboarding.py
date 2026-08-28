"""Embedded Signup directo con Meta, sin proveedores ni tokens expuestos."""

from __future__ import annotations

import pytest

from motor_voz import config as config_mod
from motor_voz.channels import secretos
from motor_voz.channels.whatsapp import onboarding


def _config(**cambios):
    entorno = {
        "GROQ_API_KEY": "x",
        "FISH_API_KEY": "x",
        "LIVEKIT_URL": "wss://ejemplo",
        "LIVEKIT_API_KEY": "x",
        "LIVEKIT_API_SECRET": "x",
        "META_APP_ID": "111111",
        "META_APP_SECRET": "secreto-app",
        "META_EMBEDDED_SIGNUP_CONFIG_ID": "222222",
        "WHATSAPP_VERIFY_TOKEN": "verificacion",
        "WHATSAPP_REGISTRATION_PIN": "123456",
    }
    entorno.update(cambios)
    return config_mod.cargar(entorno)


def test_boveda_privada_guarda_y_resuelve_sin_base(tmp_path):
    entorno = {"WHATSAPP_SECRET_DIR": str(tmp_path)}
    secretos.guardar("whatsapp_cliente_uno", "token-cliente", entorno)

    assert secretos.resolver("whatsapp_cliente_uno", entorno) == "token-cliente"
    archivos = list(tmp_path.glob("*.token"))
    assert len(archivos) == 1
    assert "token-cliente" not in archivos[0].name


def test_variable_legacy_sigue_teniendo_prioridad(tmp_path):
    entorno = {
        "WHATSAPP_SECRET_DIR": str(tmp_path),
        "SECRETO_WHATSAPP_CLIENTE": "token-env",
    }
    secretos.guardar("whatsapp_cliente", "token-archivo", entorno)

    assert secretos.resolver("whatsapp_cliente", entorno) == "token-env"


async def test_completa_registra_suscribe_y_no_expone_token_en_repr():
    llamadas = []

    async def pedir(metodo, url, **opciones):
        llamadas.append((metodo, url, opciones))
        if url.endswith("/oauth/access_token"):
            return 200, {"access_token": "token-super-secreto"}
        if url.endswith("/333333/phone_numbers"):
            return 200, {
                "data": [
                    {
                        "id": "444444",
                        "display_phone_number": "+54 9 11 5555-5555",
                        "verified_name": "QuantumHive",
                    }
                ]
            }
        return 200, {"success": True}

    conexion = await onboarding.completar(
        _config(), code="codigo-temporal", waba_id="333333", pedir=pedir
    )

    assert conexion.phone_number_id == "444444"
    assert conexion.numero == "+54 9 11 5555-5555"
    assert conexion.access_token == "token-super-secreto"
    assert "token-super-secreto" not in repr(conexion)
    assert [llamada[0] for llamada in llamadas] == ["GET", "GET", "POST", "POST"]
    assert llamadas[2][1].endswith("/444444/register")
    assert llamadas[2][2]["json"]["pin"] == "123456"
    assert llamadas[3][1].endswith("/333333/subscribed_apps")


async def test_rechaza_numero_que_no_pertenece_al_waba():
    async def pedir(metodo, url, **opciones):
        if url.endswith("/oauth/access_token"):
            return 200, {"access_token": "token"}
        return 200, {"data": [{"id": "444444"}]}

    with pytest.raises(onboarding.OnboardingInvalido, match="no pertenece"):
        await onboarding.completar(
            _config(),
            code="codigo",
            waba_id="333333",
            phone_number_id="555555",
            pedir=pedir,
        )


async def test_error_de_meta_no_filtra_mensaje_ni_token():
    async def pedir(metodo, url, **opciones):
        return 400, {
            "error": {"code": 190, "message": "token-super-secreto invalid"}
        }

    with pytest.raises(onboarding.MetaRechazo) as error:
        await onboarding.completar(
            _config(), code="codigo", waba_id="333333", pedir=pedir
        )

    assert "token-super-secreto" not in str(error.value)
    assert "190" in str(error.value)
