"""Mandar el mensaje es la parte facil. Lo dificil es saber que hacer cuando
Meta dice que no.

Reintentar un error permanente gasta llamadas y deja la cola trabada detras
de algo que nunca va a salir. No reintentar uno temporal pierde el mensaje.
"""

from __future__ import annotations

import pytest

from motor_voz import config as config_mod
from motor_voz.channels.whatsapp import cliente


@pytest.fixture
def config():
    return config_mod.cargar(
        {
            "GROQ_API_KEY": "x",
            "FISH_API_KEY": "x",
            "LIVEKIT_URL": "wss://ejemplo",
            "LIVEKIT_API_KEY": "x",
            "LIVEKIT_API_SECRET": "x",
            "SUPABASE_URL": "https://ejemplo.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "x",
            "WHATSAPP_API_VERSION": "v21.0",
        }
    )


class _Meta:
    """Un Graph API de mentira."""

    def __init__(self, estado: int = 200, cuerpo: dict | None = None):
        self.estado = estado
        self.cuerpo = cuerpo if cuerpo is not None else {
            "messages": [{"id": "wamid.SALIENTE"}]
        }
        self.pedidos: list[dict] = []

    async def __call__(self, url: str, *, json: dict, headers: dict):
        self.pedidos.append({"url": url, "json": json, "headers": headers})
        return self.estado, self.cuerpo


def _error(codigo: int, subcodigo: int | None = None, mensaje: str = "no") -> dict:
    error = {"message": mensaje, "code": codigo}
    if subcodigo is not None:
        error["error_subcode"] = subcodigo
    return {"error": error}


# --- el envio ------------------------------------------------------------


async def test_un_texto_sale_con_la_forma_que_pide_meta(config):
    meta = _Meta()

    resultado = await cliente.enviar_texto(
        config,
        token="TOKEN",
        phone_number_id="111222333",
        destino="5493519999999",
        texto="Hola!",
        pedir=meta,
    )

    assert resultado.ok
    assert resultado.mensaje_externo_id == "wamid.SALIENTE"

    (pedido,) = meta.pedidos
    assert pedido["url"].endswith("/v21.0/111222333/messages")
    assert pedido["json"] == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "5493519999999",
        "type": "text",
        "text": {"preview_url": False, "body": "Hola!"},
    }
    assert pedido["headers"]["Authorization"] == "Bearer TOKEN"


async def test_el_token_no_aparece_en_el_resultado(config):
    """Lo que devuelve esto se guarda en ultimo_error de la base."""
    meta = _Meta(estado=401, cuerpo=_error(190, mensaje="Token TOKEN invalido"))

    resultado = await cliente.enviar_texto(
        config, token="TOKEN", phone_number_id="1", destino="2", texto="hola",
        pedir=meta,
    )

    assert "TOKEN" not in resultado.error


# --- que se reintenta y que no ------------------------------------------


async def test_un_token_revocado_no_se_reintenta(config):
    """Reintentar con la misma credencial muerta no la va a resucitar."""
    meta = _Meta(estado=401, cuerpo=_error(190))

    resultado = await cliente.enviar_texto(
        config, token="T", phone_number_id="1", destino="2", texto="hola", pedir=meta
    )

    assert not resultado.ok
    assert not resultado.reintentable


async def test_la_ventana_de_24_horas_vencida_no_se_reintenta(config):
    """Fuera de la ventana hace falta una plantilla aprobada. El mismo texto
    libre va a fallar igual dentro de un minuto y dentro de una hora."""
    meta = _Meta(estado=400, cuerpo=_error(131047))

    resultado = await cliente.enviar_texto(
        config, token="T", phone_number_id="1", destino="2", texto="hola", pedir=meta
    )

    assert not resultado.ok
    assert not resultado.reintentable
    assert "ventana" in resultado.error.lower()


async def test_un_numero_que_no_existe_en_whatsapp_no_se_reintenta(config):
    meta = _Meta(estado=400, cuerpo=_error(131026))

    resultado = await cliente.enviar_texto(
        config, token="T", phone_number_id="1", destino="2", texto="hola", pedir=meta
    )

    assert not resultado.reintentable


async def test_el_rate_limit_si_se_reintenta(config):
    meta = _Meta(estado=429, cuerpo=_error(131048))

    resultado = await cliente.enviar_texto(
        config, token="T", phone_number_id="1", destino="2", texto="hola", pedir=meta
    )

    assert not resultado.ok
    assert resultado.reintentable


async def test_un_error_del_servidor_de_meta_si_se_reintenta(config):
    meta = _Meta(estado=500, cuerpo={})

    resultado = await cliente.enviar_texto(
        config, token="T", phone_number_id="1", destino="2", texto="hola", pedir=meta
    )

    assert resultado.reintentable


async def test_un_codigo_desconocido_se_reintenta(config):
    """Ante la duda, reintentar: perder un mensaje del cliente es peor que
    gastar una llamada de mas."""
    meta = _Meta(estado=400, cuerpo=_error(999999))

    resultado = await cliente.enviar_texto(
        config, token="T", phone_number_id="1", destino="2", texto="hola", pedir=meta
    )

    assert resultado.reintentable


async def test_si_la_red_se_cae_se_reintenta(config):
    async def explota(url, *, json, headers):
        raise TimeoutError("no hubo respuesta")

    resultado = await cliente.enviar_texto(
        config, token="T", phone_number_id="1", destino="2", texto="hola",
        pedir=explota,
    )

    assert not resultado.ok
    assert resultado.reintentable


async def test_sin_token_no_se_llama_a_meta(config):
    """Falla cerrado: un canal sin credencial no puede quedar 'enviando'."""
    meta = _Meta()

    resultado = await cliente.enviar_texto(
        config, token="", phone_number_id="1", destino="2", texto="hola", pedir=meta
    )

    assert not resultado.ok
    assert not resultado.reintentable
    assert meta.pedidos == []


async def test_un_200_sin_id_de_mensaje_no_se_da_por_enviado(config):
    meta = _Meta(estado=200, cuerpo={"messages": []})

    resultado = await cliente.enviar_texto(
        config, token="T", phone_number_id="1", destino="2", texto="hola", pedir=meta
    )

    assert not resultado.ok
