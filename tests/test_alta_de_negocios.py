"""Dar de alta un negocio: lo que le faltaba a la fabrica para ser una fabrica.

Lo que se prueba acá es quién puede hacerlo. Tener sesión no alcanza —cualquier
dueño de un negocio tiene una—; hace falta estar en la lista de operadores.
"""

from __future__ import annotations

import pytest

from motor_voz import config as config_mod
from motor_voz.api import servidor

OPERADOR = "usuario-sergio"
CLIENTE = "usuario-jaz"


def _config():
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


class _Fabrica:
    def __init__(self, operadores=(OPERADOR,)):
        self.operadores = set(operadores)
        self.creados: list[dict] = []
        self.activados: list[str] = []

    async def usuario_de_token(self, config, token):
        # El token ES el id del usuario, para no montar Supabase Auth acá.
        return token if token in {OPERADOR, CLIENTE} else None

    async def es_operador(self, config, usuario_id):
        return usuario_id in self.operadores

    async def crear(self, config, *, operador_id, slug, nombre, perfil_slug, **extra):
        if any(c["slug"] == slug for c in self.creados):
            raise RuntimeError(f"ya existe un negocio con slug '{slug}'")
        registro = {"slug": slug, "nombre": nombre, "perfil": perfil_slug, **extra}
        self.creados.append(registro)
        return {"tenant_id": "tenant-nuevo", "slug": slug, "estado": "borrador"}

    async def activar(self, config, *, operador_id, slug):
        self.activados.append(slug)
        return {"slug": slug, "estado": "activo", "cambio": True}


async def _sin_uso(*args, **kwargs):
    raise AssertionError("no deberia llamarse en este test")


@pytest.fixture
def fabrica():
    return _Fabrica()


@pytest.fixture
async def cliente_http(aiohttp_client, fabrica):
    app = servidor.crear_app(
        _config(),
        obtener_tenant=_sin_uso,
        usuario_de_token=fabrica.usuario_de_token,
        es_operador=fabrica.es_operador,
        crear_negocio_borrador=fabrica.crear,
        activar_negocio_fn=fabrica.activar,
    )
    return await aiohttp_client(app)


def _alta(**cambios) -> dict:
    datos = {"slug": "yaspapeobeauty", "nombre": "Yaspapeobeauty", "perfil": "capilar"}
    datos.update(cambios)
    return datos


# --- quien puede -------------------------------------------------------


async def test_sin_sesion_no_se_da_de_alta_nada(cliente_http, fabrica):
    r = await cliente_http.post("/api/fabrica/negocios", json=_alta())

    assert r.status == 401
    assert fabrica.creados == []


async def test_el_dueno_de_un_negocio_no_puede_crear_otros(cliente_http, fabrica):
    """Tiene sesion valida y es dueño de su tenant. No alcanza."""
    r = await cliente_http.post(
        "/api/fabrica/negocios",
        json=_alta(),
        headers={"Authorization": f"Bearer {CLIENTE}"},
    )

    assert r.status == 403
    assert fabrica.creados == []


async def test_un_operador_si_puede(cliente_http, fabrica):
    r = await cliente_http.post(
        "/api/fabrica/negocios",
        json=_alta(),
        headers={"Authorization": f"Bearer {OPERADOR}"},
    )

    assert r.status == 201
    cuerpo = await r.json()
    assert cuerpo["negocio"]["estado"] == "borrador"
    assert fabrica.creados[0]["slug"] == "yaspapeobeauty"


async def test_el_operador_sale_de_la_sesion_y_nunca_del_cuerpo(cliente_http, fabrica):
    """Si el cuerpo pudiera declarar el operador, cualquiera se declararia uno."""
    r = await cliente_http.post(
        "/api/fabrica/negocios",
        json=_alta(operador_id=OPERADOR, usuario_id=OPERADOR),
        headers={"Authorization": f"Bearer {CLIENTE}"},
    )

    assert r.status == 403
    assert fabrica.creados == []


# --- el alta en si -----------------------------------------------------


async def test_nace_en_borrador_siempre(cliente_http):
    """Aunque el cuerpo pida lo contrario: un agente no existe hasta que se paga."""
    r = await cliente_http.post(
        "/api/fabrica/negocios",
        json=_alta(estado="activo"),
        headers={"Authorization": f"Bearer {OPERADOR}"},
    )

    cuerpo = await r.json()
    assert cuerpo["negocio"]["estado"] == "borrador"


async def test_faltan_datos_obligatorios(cliente_http, fabrica):
    for incompleto in ({"slug": "x"}, {"nombre": "X"}, {"slug": "x", "nombre": "X"}):
        r = await cliente_http.post(
            "/api/fabrica/negocios",
            json=incompleto,
            headers={"Authorization": f"Bearer {OPERADOR}"},
        )
        assert r.status == 400
    assert fabrica.creados == []


async def test_un_slug_repetido_dice_por_que(cliente_http):
    cabeceras = {"Authorization": f"Bearer {OPERADOR}"}
    await cliente_http.post("/api/fabrica/negocios", json=_alta(), headers=cabeceras)

    r = await cliente_http.post("/api/fabrica/negocios", json=_alta(), headers=cabeceras)

    assert r.status == 400
    assert "ya existe" in (await r.json())["error"]


async def test_el_slug_se_normaliza_a_minusculas(cliente_http, fabrica):
    """Viaja en el nombre de sala, que el agente parsea por posicion."""
    await cliente_http.post(
        "/api/fabrica/negocios",
        json=_alta(slug="YasPapeoBeauty"),
        headers={"Authorization": f"Bearer {OPERADOR}"},
    )

    assert fabrica.creados[0]["slug"] == "yaspapeobeauty"


# --- activar -----------------------------------------------------------


async def test_activar_exige_ser_operador(cliente_http, fabrica):
    r = await cliente_http.post(
        "/api/fabrica/negocios/yaspapeobeauty/activar",
        headers={"Authorization": f"Bearer {CLIENTE}"},
    )

    assert r.status == 403
    assert fabrica.activados == []


async def test_activar_lo_deja_activo(cliente_http, fabrica):
    r = await cliente_http.post(
        "/api/fabrica/negocios/yaspapeobeauty/activar",
        headers={"Authorization": f"Bearer {OPERADOR}"},
    )

    assert r.status == 200
    assert (await r.json())["negocio"]["estado"] == "activo"
    assert fabrica.activados == ["yaspapeobeauty"]
