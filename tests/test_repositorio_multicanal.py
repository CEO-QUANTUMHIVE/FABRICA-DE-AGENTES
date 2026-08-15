from datetime import datetime, timezone
from types import SimpleNamespace

from motor_voz.brain.mensajes import MensajeEntrante
from motor_voz.brain.tenants import repositorio


class ConsultaFalsa:
    def __init__(self, datos):
        self.datos = datos
        self.filtros = []
        self.parametros_rpc = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, campo, valor):
        self.filtros.append((campo, valor))
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def maybe_single(self):
        return self

    async def execute(self):
        return SimpleNamespace(data=self.datos)


class ClienteFalso:
    def __init__(self, datos=None):
        self.consulta = ConsultaFalsa(datos or [])

    def table(self, nombre):
        self.tabla = nombre
        return self.consulta

    def rpc(self, nombre, parametros):
        self.rpc_nombre = nombre
        self.consulta.parametros_rpc = parametros
        return self.consulta


async def test_conversaciones_siempre_filtra_por_tenant(monkeypatch):
    cliente = ClienteFalso()

    async def _falso(config):
        return cliente

    monkeypatch.setattr(repositorio, "_cliente", _falso)
    await repositorio.conversaciones_de(object(), "tenant-1")
    assert cliente.tabla == "conversaciones"
    assert ("tenant_id", "tenant-1") in cliente.consulta.filtros


async def test_mensajes_exige_tenant_y_conversacion(monkeypatch):
    cliente = ClienteFalso()

    async def _falso(config):
        return cliente

    monkeypatch.setattr(repositorio, "_cliente", _falso)
    await repositorio.mensajes_de_conversacion(
        object(), tenant_id="tenant-1", conversacion_id="conversacion-1"
    )
    assert set(cliente.consulta.filtros) >= {
        ("tenant_id", "tenant-1"),
        ("conversacion_id", "conversacion-1"),
    }


async def test_rpc_recibe_tenant_y_canal_resueltos(monkeypatch):
    cliente = ClienteFalso({"duplicado": False, "mensaje_id": "mensaje-db"})

    async def _falso(config):
        return cliente

    monkeypatch.setattr(repositorio, "_cliente", _falso)
    mensaje = MensajeEntrante(
        tenant_id="tenant-1",
        canal="whatsapp",
        conversacion_externa_id="chat-1",
        remitente_externo_id="persona-1",
        evento_externo_id="evento-1",
        mensaje_externo_id="mensaje-1",
        texto="Hola",
        recibido_en=datetime.now(timezone.utc),
    )
    resultado = await repositorio.registrar_mensaje_entrante(
        object(), tenant_canal_id="canal-1", mensaje=mensaje
    )
    assert cliente.rpc_nombre == "registrar_mensaje_entrante"
    assert cliente.consulta.parametros_rpc["p_tenant_id"] == "tenant-1"
    assert cliente.consulta.parametros_rpc["p_tenant_canal_id"] == "canal-1"
    assert resultado.mensaje_id == "mensaje-db"


async def test_crear_borrador_no_publica_y_fija_tenant(monkeypatch):
    cliente = ClienteFalso(
        {"conocimiento_id": "c1", "version_id": "v2", "numero": 2, "publicada": False}
    )

    async def _falso(config):
        return cliente

    monkeypatch.setattr(repositorio, "_cliente", _falso)
    resultado = await repositorio.crear_borrador_conocimiento(
        object(), tenant_id="tenant-1", categoria="precio", clave="corte",
        titulo="Precio corte", contenido={"precio": 25000}, motivo="Actualizacion"
    )
    assert cliente.rpc_nombre == "crear_borrador_conocimiento"
    assert cliente.consulta.parametros_rpc["p_tenant_id"] == "tenant-1"
    assert resultado["publicada"] is False


async def test_publicar_version_fija_tenant_y_version(monkeypatch):
    cliente = ClienteFalso({"version_id": "v2", "publicada": True})

    async def _falso(config):
        return cliente

    monkeypatch.setattr(repositorio, "_cliente", _falso)
    resultado = await repositorio.publicar_version_conocimiento(
        object(), tenant_id="tenant-1", version_id="v2", motivo="Aprobada"
    )
    assert cliente.rpc_nombre == "publicar_version_conocimiento"
    assert cliente.consulta.parametros_rpc["p_tenant_id"] == "tenant-1"
    assert cliente.consulta.parametros_rpc["p_version_id"] == "v2"
    assert resultado["publicada"] is True
