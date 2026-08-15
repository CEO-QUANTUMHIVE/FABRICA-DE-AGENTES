"""Vaciar la cola de salida sin mandar dos veces ni trabarse.

El duplicado acá es peor que en la entrada: le llega al cliente.
"""

from __future__ import annotations

import pytest

from motor_voz import config as config_mod
from motor_voz.brain.mensajes import DestinoEnvio, EventoOutbox
from motor_voz.channels import enviador
from motor_voz.channels.secretos import SecretoNoEncontrado
from motor_voz.channels.whatsapp.cliente import Resultado


def _evento(evento_id: str = "out-1", canal: str = "whatsapp") -> EventoOutbox:
    return EventoOutbox(
        id=evento_id,
        tenant_id="tenant-1",
        tenant_canal_id="canal-1",
        conversacion_id="conv-1",
        canal=canal,
        clave_idempotencia=f"respuesta:mensaje:wamid.{evento_id}",
        payload={"texto": "Hola! Contame de tu negocio."},
    )


class _Repo:
    def __init__(self, eventos=(), estado_canal="conectado", secreto_ref="wa_qh"):
        self.eventos = list(eventos)
        self.destino = DestinoEnvio(
            cuenta_externa_id="111222333",
            secreto_ref=secreto_ref,
            contacto_externo_id="5493519999999",
            estado_canal=estado_canal,
        )
        self.cerrados: list[dict] = []
        self.registrados: list[dict] = []

    async def tomar(self, config, *, limite):
        tomados, self.eventos = self.eventos[:limite], self.eventos[limite:]
        return tomados

    async def cerrar(self, config, *, evento_id, ok, error="", reintentable=True):
        self.cerrados.append(
            {"id": evento_id, "ok": ok, "error": error, "reintentable": reintentable}
        )
        return "enviado" if ok else "fallido"

    async def destino_de(self, config, *, tenant_id, tenant_canal_id, conversacion_id):
        return self.destino

    async def registrar_saliente(self, config, **kwargs):
        self.registrados.append(kwargs)


def _deps(repo, *, enviar=None, resolver=None) -> enviador.Dependencias:
    async def enviar_ok(config, **kwargs):
        return Resultado(ok=True, mensaje_externo_id="wamid.SALIENTE")

    return enviador.Dependencias(
        tomar=repo.tomar,
        cerrar=repo.cerrar,
        destino_de=repo.destino_de,
        registrar_saliente=repo.registrar_saliente,
        resolver_secreto=resolver or (lambda ref: "TOKEN"),
        enviadores={"whatsapp": enviar or enviar_ok},
    )


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
        }
    )


async def test_una_respuesta_pendiente_se_manda_y_se_guarda(config):
    repo = _Repo(eventos=[_evento()])
    enviados = []

    async def enviar(config, **kwargs):
        enviados.append(kwargs)
        return Resultado(ok=True, mensaje_externo_id="wamid.SALIENTE")

    mandados = await enviador.vaciar_outbox(config, _deps(repo, enviar=enviar))

    assert mandados == 1
    assert enviados[0]["destino"] == "5493519999999"
    assert enviados[0]["phone_number_id"] == "111222333"
    assert enviados[0]["texto"] == "Hola! Contame de tu negocio."
    assert repo.cerrados[0]["ok"]


async def test_lo_que_contesto_el_agente_queda_en_el_historial(config):
    """Sin esto el proximo turno no ve lo que ya dijo y se repite."""
    repo = _Repo(eventos=[_evento()])

    await enviador.vaciar_outbox(config, _deps(repo))

    (registrado,) = repo.registrados
    assert registrado["mensaje_externo_id"] == "wamid.SALIENTE"
    assert registrado["texto"] == "Hola! Contame de tu negocio."
    assert registrado["conversacion_id"] == "conv-1"


async def test_un_error_permanente_se_descarta_en_vez_de_reintentarse(config):
    async def enviar(config, **kwargs):
        return Resultado(
            ok=False, error="[131047] fuera de la ventana", reintentable=False
        )

    repo = _Repo(eventos=[_evento()])

    mandados = await enviador.vaciar_outbox(config, _deps(repo, enviar=enviar))

    assert mandados == 0
    assert repo.cerrados[0]["reintentable"] is False
    assert repo.registrados == []


async def test_un_error_temporal_vuelve_a_la_cola(config):
    async def enviar(config, **kwargs):
        return Resultado(ok=False, error="[131048] rate limit", reintentable=True)

    repo = _Repo(eventos=[_evento()])

    await enviador.vaciar_outbox(config, _deps(repo, enviar=enviar))

    assert repo.cerrados[0]["reintentable"] is True
    assert repo.cerrados[0]["ok"] is False


async def test_un_canal_desconectado_no_manda_nada(config):
    """Un canal pausado o revocado no puede seguir escribiendole a clientes."""
    repo = _Repo(eventos=[_evento()], estado_canal="pausado")
    enviados = []

    async def enviar(config, **kwargs):
        enviados.append(kwargs)
        return Resultado(ok=True, mensaje_externo_id="x")

    await enviador.vaciar_outbox(config, _deps(repo, enviar=enviar))

    assert enviados == []
    assert repo.cerrados[0]["ok"] is False
    assert repo.cerrados[0]["reintentable"] is False


async def test_un_secreto_que_falta_no_se_reintenta_para_siempre(config):
    def resolver(ref):
        raise SecretoNoEncontrado("falta la variable SECRETO_WA_QH")

    repo = _Repo(eventos=[_evento()])

    await enviador.vaciar_outbox(config, _deps(repo, resolver=resolver))

    assert repo.cerrados[0]["ok"] is False
    assert repo.cerrados[0]["reintentable"] is False
    assert "SECRETO_WA_QH" in repo.cerrados[0]["error"]


async def test_un_canal_sin_enviador_no_traba_la_cola(config):
    """Instagram va a existir en la base antes que su cliente de envio."""
    repo = _Repo(eventos=[_evento(canal="instagram")])

    await enviador.vaciar_outbox(config, _deps(repo))

    assert repo.cerrados[0]["reintentable"] is False


async def test_una_respuesta_vacia_no_se_manda(config):
    evento = EventoOutbox(**{**_evento().__dict__, "payload": {"texto": "   "}})
    repo = _Repo(eventos=[evento])
    enviados = []

    async def enviar(config, **kwargs):
        enviados.append(kwargs)
        return Resultado(ok=True, mensaje_externo_id="x")

    await enviador.vaciar_outbox(config, _deps(repo, enviar=enviar))

    assert enviados == []
    assert repo.cerrados[0]["reintentable"] is False


async def test_un_evento_roto_no_frena_al_resto(config):
    repo = _Repo(eventos=[_evento("out-1"), _evento("out-2")])

    async def falla_el_primero(config, *, tenant_id, tenant_canal_id, conversacion_id):
        if not repo.cerrados:
            raise RuntimeError("base inaccesible")
        return repo.destino

    deps = enviador.Dependencias(
        **{**_deps(repo).__dict__, "destino_de": falla_el_primero}
    )

    await enviador.vaciar_outbox(config, deps)

    assert [c["id"] for c in repo.cerrados] == ["out-1", "out-2"]
    assert [c["ok"] for c in repo.cerrados] == [False, True]


def test_las_dependencias_reales_existen():
    from motor_voz.brain.tenants import repositorio

    deps = enviador.Dependencias.de_produccion()

    assert deps.tomar is repositorio.tomar_eventos_outbox
    assert deps.cerrar is repositorio.cerrar_evento_outbox
    assert deps.destino_de is repositorio.destino_de_envio
    assert deps.registrar_saliente is repositorio.registrar_mensaje_saliente
    assert "whatsapp" in deps.enviadores
