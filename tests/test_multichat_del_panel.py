from types import SimpleNamespace

import pytest

from motor_voz.api.servidor import crear_app
from motor_voz.brain.mensajes import Conversacion, MensajeGuardado
from motor_voz.brain.tenants import repositorio
from motor_voz.brain.tenants.modelos import PerfilTenant, Tenant
from motor_voz.config import cargar


ENTORNO = {
    "GROQ_API_KEY": "gsk_falsa",
    "FISH_API_KEY": "sk-falsa",
    "LIVEKIT_URL": "ws://localhost:7880",
    "LIVEKIT_API_KEY": "devkey",
    "LIVEKIT_API_SECRET": "secreto-largo-de-prueba-1234567890",
    "ENVIRONMENT": "test",
}

TENANT = Tenant(
    id="tenant-takeprop",
    slug="takepropfit",
    nombre="Take Prop",
    idioma="es",
    perfil=PerfilTenant(
        slug="receptor", nombre="Receptor", prompt_base="Soy Take Prop."
    ),
    prompt_propio="",
    servicios=(),
    voz=None,
)


def _conversacion(modo="automatico"):
    return Conversacion(
        id="conversacion-1",
        tenant_canal_id="canal-interno-1",
        canal="telegram",
        contacto_externo_id="contacto-telegram-1",
        nombre_contacto="Cliente",
        modo_atencion=modo,
        ultimo_mensaje_en="2026-09-14T12:00:00+00:00",
    )


async def _obtener_tenant(config, slug):
    if slug != TENANT.slug:
        raise repositorio.TenantNoEncontrado(slug)
    return TENANT


async def _usuario(config, token):
    return "usuario-1" if token == "jwt-valido" else None


@pytest.fixture
def cliente(aiohttp_client):
    async def _crear(*, rol="dueño", **funciones):
        async def _rol(config, usuario_id, tenant_id):
            assert usuario_id == "usuario-1"
            assert tenant_id == TENANT.id
            return rol

        async def _lista_vacia(config, tenant_id):
            return []

        async def _conversacion_existente(config, **datos):
            return _conversacion()

        async def _mensajes_vacios(config, **datos):
            return []

        async def _cambiar(config, **datos):
            return _conversacion(datos["modo"])

        async def _encolar(config, **datos):
            return True

        app = crear_app(
            cargar(ENTORNO),
            obtener_tenant=_obtener_tenant,
            tenant_de_dominio=lambda config, dominio: None,
            usuario_de_token=_usuario,
            rol_de_usuario_en_tenant=_rol,
            conversaciones_de_fn=funciones.get("conversaciones_de", _lista_vacia),
            conversacion_de_fn=funciones.get(
                "conversacion_de", _conversacion_existente
            ),
            mensajes_de_conversacion_fn=funciones.get(
                "mensajes_de_conversacion", _mensajes_vacios
            ),
            cambiar_modo_atencion_fn=funciones.get(
                "cambiar_modo_atencion", _cambiar
            ),
            encolar_respuesta_fn=funciones.get("encolar_respuesta", _encolar),
        )
        return await aiohttp_client(app)

    return _crear


def _auth():
    return {"Authorization": "Bearer jwt-valido"}


async def test_multichat_exige_sesion(cliente):
    c = await cliente()
    respuesta = await c.get("/api/panel/takepropfit/conversaciones")
    assert respuesta.status == 401


async def test_multichat_no_cruza_un_tenant_sin_membresia(cliente):
    llamado = False

    async def listar(config, tenant_id):
        nonlocal llamado
        llamado = True
        return []

    c = await cliente(rol=None, conversaciones_de=listar)
    respuesta = await c.get(
        "/api/panel/takepropfit/conversaciones", headers=_auth()
    )
    assert respuesta.status == 403
    assert llamado is False


@pytest.mark.parametrize("rol", ["dueño", "empleado"])
async def test_dueno_y_empleado_pueden_listar_solo_su_tenant(cliente, rol):
    recibido = {}

    async def listar(config, tenant_id):
        recibido["tenant_id"] = tenant_id
        return [_conversacion()]

    c = await cliente(rol=rol, conversaciones_de=listar)
    respuesta = await c.get(
        "/api/panel/takepropfit/conversaciones", headers=_auth()
    )
    cuerpo = await respuesta.json()
    assert respuesta.status == 200
    assert recibido == {"tenant_id": TENANT.id}
    assert cuerpo["rol"] == rol
    assert cuerpo["conversaciones"][0]["canal"] == "telegram"
    assert "tenant_canal_id" not in cuerpo["conversaciones"][0]


async def test_mensajes_validan_la_conversacion_en_el_tenant(cliente):
    recibido = []

    async def obtener(config, **datos):
        recibido.append(("conversacion", datos))
        return _conversacion()

    async def listar(config, **datos):
        recibido.append(("mensajes", datos))
        return [
            MensajeGuardado(
                id="mensaje-1",
                canal="telegram",
                direccion="entrante",
                texto="Hola",
                estado="recibido",
                ocurrido_en="2026-09-14T12:00:00+00:00",
            )
        ]

    c = await cliente(conversacion_de=obtener, mensajes_de_conversacion=listar)
    respuesta = await c.get(
        "/api/panel/takepropfit/conversaciones/conversacion-1/mensajes",
        headers=_auth(),
    )
    assert respuesta.status == 200
    assert recibido == [
        (
            "conversacion",
            {"tenant_id": TENANT.id, "conversacion_id": "conversacion-1"},
        ),
        (
            "mensajes",
            {"tenant_id": TENANT.id, "conversacion_id": "conversacion-1"},
        ),
    ]


async def test_mensajes_ajenos_responden_como_no_encontrados(cliente):
    async def ajena(config, **datos):
        raise repositorio.ConversacionNoEncontrada("ajena")

    c = await cliente(conversacion_de=ajena)
    respuesta = await c.get(
        "/api/panel/takepropfit/conversaciones/ajena/mensajes", headers=_auth()
    )
    assert respuesta.status == 404
    assert (await respuesta.json()) == {"error": "Conversacion no encontrada."}


async def test_cambia_los_tres_modos_con_tenant_resuelto(cliente):
    recibidos = []

    async def cambiar(config, **datos):
        recibidos.append(datos)
        return _conversacion(datos["modo"])

    c = await cliente(cambiar_modo_atencion=cambiar)
    for modo in ("automatico", "humano", "cerrado"):
        respuesta = await c.post(
            "/api/panel/takepropfit/conversaciones/conversacion-1/modo",
            headers=_auth(),
            json={"modo": modo, "tenant_id": "tenant-ajeno"},
        )
        assert respuesta.status == 200
        assert (await respuesta.json())["modo_atencion"] == modo
    assert [datos["tenant_id"] for datos in recibidos] == [TENANT.id] * 3


async def test_rechaza_un_modo_invalido_sin_tocar_la_base(cliente):
    llamado = False

    async def cambiar(config, **datos):
        nonlocal llamado
        llamado = True

    c = await cliente(cambiar_modo_atencion=cambiar)
    respuesta = await c.post(
        "/api/panel/takepropfit/conversaciones/conversacion-1/modo",
        headers=_auth(),
        json={"modo": "administrador"},
    )
    assert respuesta.status == 400
    assert llamado is False


async def test_mensaje_humano_fuerza_handoff_y_usa_el_outbox(cliente):
    pasos = []

    async def cambiar(config, **datos):
        pasos.append(("modo", datos))
        return _conversacion(datos["modo"])

    async def encolar(config, **datos):
        pasos.append(("outbox", datos))
        return True

    c = await cliente(
        cambiar_modo_atencion=cambiar,
        encolar_respuesta=encolar,
    )
    respuesta = await c.post(
        "/api/panel/takepropfit/conversaciones/conversacion-1/mensajes",
        headers=_auth(),
        json={
            "texto": "Te atiendo personalmente.",
            "tenant_id": "tenant-ajeno",
            "canal": "whatsapp",
            "clave_idempotencia": "elegida-por-el-navegador",
        },
    )
    cuerpo = await respuesta.json()
    assert respuesta.status == 202
    assert cuerpo == {
        "conversacion_id": "conversacion-1",
        "modo_atencion": "humano",
        "encolado": True,
    }
    assert pasos[0] == (
        "modo",
        {
            "tenant_id": TENANT.id,
            "conversacion_id": "conversacion-1",
            "modo": "humano",
        },
    )
    enviado = pasos[1][1]
    assert enviado["tenant_id"] == TENANT.id
    assert enviado["tenant_canal_id"] == "canal-interno-1"
    assert enviado["canal"] == "telegram"
    assert enviado["payload"] == {"texto": "Te atiendo personalmente."}
    assert enviado["clave_idempotencia"].startswith("humano:conversacion-1:")
    assert enviado["clave_idempotencia"] != "elegida-por-el-navegador"


async def test_mensaje_humano_vacio_no_cambia_el_modo(cliente):
    llamado = False

    async def cambiar(config, **datos):
        nonlocal llamado
        llamado = True

    c = await cliente(cambiar_modo_atencion=cambiar)
    respuesta = await c.post(
        "/api/panel/takepropfit/conversaciones/conversacion-1/mensajes",
        headers=_auth(),
        json={"texto": "   "},
    )
    assert respuesta.status == 400
    assert llamado is False


class ConsultaFalsa:
    def __init__(self, datos):
        self.datos = datos
        self.filtros = []
        self.actualizacion = None

    def select(self, *args, **kwargs):
        return self

    def update(self, datos):
        self.actualizacion = datos
        return self

    def eq(self, campo, valor):
        self.filtros.append((campo, valor))
        return self

    def maybe_single(self):
        return self

    async def execute(self):
        return SimpleNamespace(data=self.datos)


class ClienteFalso:
    def __init__(self, datos):
        self.consulta = ConsultaFalsa(datos)

    def table(self, nombre):
        assert nombre == "conversaciones"
        return self.consulta


def _fila_conversacion(modo="automatico"):
    return {
        "id": "conversacion-1",
        "tenant_canal_id": "canal-1",
        "canal": "telegram",
        "contacto_externo_id": "contacto-1",
        "nombre_contacto": "Cliente",
        "modo_atencion": modo,
        "ultimo_mensaje_en": None,
    }


async def test_repositorio_obtiene_conversacion_con_doble_filtro(monkeypatch):
    cliente_falso = ClienteFalso(_fila_conversacion())

    async def _cliente(config):
        return cliente_falso

    monkeypatch.setattr(repositorio, "_cliente", _cliente)
    await repositorio.conversacion_de(
        object(), tenant_id="tenant-1", conversacion_id="conversacion-1"
    )
    assert set(cliente_falso.consulta.filtros) == {
        ("tenant_id", "tenant-1"),
        ("id", "conversacion-1"),
    }


async def test_repositorio_cambia_modo_con_doble_filtro(monkeypatch):
    cliente_falso = ClienteFalso([_fila_conversacion("humano")])

    async def _cliente(config):
        return cliente_falso

    monkeypatch.setattr(repositorio, "_cliente", _cliente)
    conversacion = await repositorio.cambiar_modo_atencion(
        object(),
        tenant_id="tenant-1",
        conversacion_id="conversacion-1",
        modo="humano",
    )
    assert conversacion.modo_atencion == "humano"
    assert cliente_falso.consulta.actualizacion == {"modo_atencion": "humano"}
    assert set(cliente_falso.consulta.filtros) == {
        ("tenant_id", "tenant-1"),
        ("id", "conversacion-1"),
    }
