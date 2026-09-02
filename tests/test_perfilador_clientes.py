"""El Perfilador se consume desde el servidor sin filtrar credenciales."""

from __future__ import annotations

import pytest

from motor_voz import config as config_mod
from motor_voz.api import servidor
from motor_voz.fabrica import perfilador


def _config(**extras):
    return config_mod.cargar(
        {
            "GROQ_API_KEY": "x",
            "FISH_API_KEY": "x",
            "LIVEKIT_URL": "wss://ejemplo",
            "LIVEKIT_API_KEY": "x",
            "LIVEKIT_API_SECRET": "x",
            "SUPABASE_URL": "https://ejemplo.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "x",
            **extras,
        }
    )


async def test_el_token_viaja_solo_entre_servidores_y_normaliza_la_respuesta():
    pedido = {}

    async def pedir(metodo, url, **opciones):
        pedido.update({"metodo": metodo, "url": url, **opciones})
        return 200, {
            "negocio": {
                "nombre": "Taller Norte",
                "categoria": "Mecánica",
                "texto_web": "x" * 7000,
            },
            "servicios": ["Service", "Frenos"],
            "precios": ["Service desde $10"],
            "horarios": "Lunes a viernes",
            "preguntas_frecuentes": [
                {"pregunta": "¿Dan turnos?", "respuesta": "Sí."}
            ],
            "marca": {
                "logo_url": "https://taller.test/logo.png",
                "colores": ["#AABBCC", "javascript:alert(1)"],
            },
            "competidores": ["Otro taller"],
            "campo_privado": "no debe pasar",
        }

    resultado = await perfilador.investigar(
        _config(
            CENTRO_INTELIGENCIA_URL="https://inteligencia.test/",
            CENTRO_INTELIGENCIA_TOKEN="secreto-interno",
        ),
        nombre="Taller Norte",
        instagram="tallernorte",
        facebook="tallernorte",
        web="www.taller.test",
        pedir=pedir,
    )

    assert pedido["metodo"] == "POST"
    assert pedido["url"] == "https://inteligencia.test/clientes/investigar"
    assert pedido["headers"]["Authorization"] == "Bearer secreto-interno"
    assert pedido["json"]["web"] == "https://www.taller.test"
    assert pedido["json"]["instagram"] == "@tallernorte"
    assert pedido["json"]["facebook"] == "https://www.facebook.com/tallernorte"
    assert resultado["marca"]["colores"] == ["#aabbcc"]
    assert len(resultado["negocio"]["texto_web"]) == 6000
    assert "campo_privado" not in resultado


async def test_rechaza_fuentes_no_publicas_antes_de_hacer_red():
    async def no_llamar(*args, **kwargs):
        raise AssertionError("no debía hacer una llamada")

    with pytest.raises(perfilador.PerfiladorInvalido):
        await perfilador.investigar(
            _config(
                CENTRO_INTELIGENCIA_URL="https://inteligencia.test",
                CENTRO_INTELIGENCIA_TOKEN="token",
            ),
            nombre="Negocio",
            web="file:///C:/secreto.txt",
            pedir=no_llamar,
        )

    with pytest.raises(perfilador.PerfiladorInvalido):
        await perfilador.investigar(
            _config(
                CENTRO_INTELIGENCIA_URL="https://inteligencia.test",
                CENTRO_INTELIGENCIA_TOKEN="token",
            ),
            nombre="Negocio",
            web="http://127.0.0.1:8000/admin",
            pedir=no_llamar,
        )


def test_descarta_el_logo_generico_de_instagram_y_sus_colores():
    resultado = perfilador.normalizar_paquete(
        {
            "negocio": {"nombre": "Trader Boss"},
            "marca": {
                "logo_url": "https://static.cdninstagram.com/rsrc.php/v4/yD/r/logo.png",
                "colores": ["#405de6", "#e1306c"],
            },
        }
    )

    assert resultado["marca"]["logo_url"] == ""
    assert resultado["marca"]["colores"] == []


async def test_sin_configuracion_falla_cerrado():
    with pytest.raises(perfilador.PerfiladorNoConfigurado):
        await perfilador.investigar(_config(), nombre="Negocio")


async def test_la_api_publica_no_expone_el_token(aiohttp_client):
    recibido = {}

    async def investigar(config, **fuentes):
        recibido.update(fuentes)
        return {
            "negocio": {"nombre": fuentes["nombre"]},
            "servicios": [],
            "precios": [],
            "horarios": None,
            "preguntas_frecuentes": [],
            "marca": {"logo_url": "", "colores": []},
            "competidores": [],
        }

    config = _config(
        CENTRO_INTELIGENCIA_URL="https://inteligencia.test",
        CENTRO_INTELIGENCIA_TOKEN="no-sale-al-navegador",
    )
    app = servidor.crear_app(
        config,
        obtener_tenant=lambda *_: None,
        investigar_cliente_fn=investigar,
    )
    cliente = await aiohttp_client(app)

    estado = await cliente.get("/api/fabrica/perfilador")
    respuesta = await cliente.post(
        "/api/fabrica/investigar",
        json={"nombre": "Taller Norte", "web": "https://taller.test"},
    )

    assert estado.status == 200
    assert await estado.json() == {"disponible": True}
    assert respuesta.status == 200
    cuerpo = await respuesta.json()
    assert cuerpo["perfil"]["negocio"]["nombre"] == "Taller Norte"
    assert "token" not in str(cuerpo).lower()
    assert recibido["web"] == "https://taller.test"


async def test_la_api_traduce_un_pedido_invalido_a_400(aiohttp_client):
    async def investigar(*args, **kwargs):
        raise perfilador.PerfiladorInvalido("fuente inválida")

    app = servidor.crear_app(
        _config(),
        obtener_tenant=lambda *_: None,
        investigar_cliente_fn=investigar,
    )
    cliente = await aiohttp_client(app)

    respuesta = await cliente.post(
        "/api/fabrica/investigar", json={"nombre": "Negocio"}
    )

    assert respuesta.status == 400
    assert (await respuesta.json())["error"] == "fuente inválida"
