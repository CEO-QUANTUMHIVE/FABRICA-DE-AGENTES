"""El worker que convierte un mensaje recibido en una respuesta encolada.

Lo que importa acá no es que conteste: es que no conteste dos veces, que no
conteste cuando atiende una persona, y que un evento roto no se lleve puesto
al resto del lote.
"""

from __future__ import annotations

import pytest

from motor_voz import config as config_mod
from motor_voz.brain import conversacion as conversacion_mod
from motor_voz.brain.conversacion import Turno
from motor_voz.brain.mensajes import Permiso
from motor_voz.brain.tenants.modelos import PerfilTenant, Servicio, Tenant
from motor_voz.channels import procesador


def _entorno(**cambios) -> dict:
    base = {
        "GROQ_API_KEY": "x",
        "FISH_API_KEY": "x",
        "LIVEKIT_URL": "wss://ejemplo",
        "LIVEKIT_API_KEY": "x",
        "LIVEKIT_API_SECRET": "x",
        "SUPABASE_URL": "https://ejemplo.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "x",
    }
    base.update(cambios)
    return base


def _tenant() -> Tenant:
    return Tenant(
        id="tenant-1",
        slug="quantumhive",
        nombre="QuantumHive",
        idioma="es",
        perfil=PerfilTenant(slug="quantumhive", nombre="QuantumHive", prompt_base=""),
        prompt_propio="",
        servicios=(Servicio(nombre="Agentes de voz", descripcion="24/7"),),
        voz=None,
    )


def _evento(evento_id: str = "ev-1", **cambios) -> procesador.EventoInbox:
    datos = {
        "id": evento_id,
        "tenant_id": "tenant-1",
        "tenant_canal_id": "canal-1",
        "conversacion_id": "conv-1",
        "canal": "whatsapp",
        "evento_externo_id": f"mensaje:wamid.{evento_id}",
    }
    datos.update(cambios)
    return procesador.EventoInbox(**datos)


class _Repo:
    def __init__(
        self,
        eventos=(),
        modo_atencion="automatico",
        turnos=(Turno("user", "hola"),),
        respuesta="Hola! Contame.",
    ):
        self.eventos = list(eventos)
        self.contexto = procesador.ContextoConversacion(
            modo_atencion=modo_atencion, turnos=tuple(turnos)
        )
        self.respuesta = respuesta
        self.encolados: list[dict] = []
        self.cerrados: list[tuple[str, bool, str]] = []
        self.pedidos_al_cerebro: list[dict] = []

    async def tomar(self, config, *, limite):
        tomados, self.eventos = self.eventos[:limite], self.eventos[limite:]
        return tomados

    async def cerrar(self, config, *, evento_id, ok, error=""):
        self.cerrados.append((evento_id, ok, error))
        return "procesado" if ok else "fallido"

    async def tenant_de_id(self, config, tenant_id):
        return _tenant()

    async def contexto_de(self, config, *, tenant_id, conversacion_id):
        return self.contexto

    async def encolar(self, config, **kwargs):
        self.encolados.append(kwargs)
        return True

    async def responder(self, config, tenant, **kwargs):
        self.pedidos_al_cerebro.append(kwargs)
        return self.respuesta


async def _permite(config, *, tenant_id, conversacion_id):
    """El default de `Dependencias` es el repositorio real, que iria a
    Supabase. Los tests que no prueban limites usan este."""
    return Permiso(permitido=True)


def _deps(repo: _Repo) -> procesador.Dependencias:
    return procesador.Dependencias(
        tomar=repo.tomar,
        cerrar=repo.cerrar,
        tenant_de_id=repo.tenant_de_id,
        contexto_de=repo.contexto_de,
        encolar=repo.encolar,
        puede_responder=_permite,
        responder=repo.responder,
    )


@pytest.fixture
def config():
    return config_mod.cargar(_entorno())


@pytest.fixture
def config_apagado():
    return config_mod.cargar(_entorno(RESPUESTAS_AUTOMATICAS="off"))


async def test_un_mensaje_pendiente_termina_encolado_como_respuesta(config):
    repo = _Repo(eventos=[_evento()])

    procesados = await procesador.procesar_pendientes(config, _deps(repo))

    assert procesados == 1
    assert len(repo.encolados) == 1
    assert repo.encolados[0]["payload"]["texto"] == "Hola! Contame."
    assert repo.cerrados == [("ev-1", True, "")]


async def test_la_clave_de_idempotencia_sale_del_evento(config):
    """Si el worker muere despues de encolar y antes de cerrar, al reanudar
    tiene que chocar contra la misma clave en vez de encolar otra respuesta."""
    repo = _Repo(eventos=[_evento()])

    await procesador.procesar_pendientes(config, _deps(repo))

    assert repo.encolados[0]["clave_idempotencia"] == "respuesta:mensaje:wamid.ev-1"


async def test_el_ultimo_mensaje_es_el_que_se_contesta_y_el_resto_es_historial(config):
    repo = _Repo(
        eventos=[_evento()],
        turnos=(
            Turno("user", "hola"),
            Turno("assistant", "hola! contame"),
            Turno("user", "cuanto sale?"),
        ),
    )

    await procesador.procesar_pendientes(config, _deps(repo))

    pedido = repo.pedidos_al_cerebro[0]
    assert pedido["texto"] == "cuanto sale?"
    assert [t.texto for t in pedido["historial"]] == ["hola", "hola! contame"]
    assert pedido["canal"] == "whatsapp"


async def test_si_atiende_una_persona_el_agente_se_calla(config):
    """El handoff no es un aviso: es que deja de contestar."""
    repo = _Repo(eventos=[_evento()], modo_atencion="humano")

    await procesador.procesar_pendientes(config, _deps(repo))

    assert repo.encolados == []
    assert repo.pedidos_al_cerebro == []
    assert repo.cerrados == [("ev-1", True, "")]


async def test_una_conversacion_cerrada_tampoco_se_contesta(config):
    repo = _Repo(eventos=[_evento()], modo_atencion="cerrado")

    await procesador.procesar_pendientes(config, _deps(repo))

    assert repo.encolados == []


async def test_un_audio_se_contesta_sin_gastar_un_llm(config):
    """El parser deja el texto vacio en lo que no sabe leer. Mandarselo al
    modelo es pagar por que conteste a la nada."""
    repo = _Repo(eventos=[_evento()], turnos=(Turno("user", "   "),))

    await procesador.procesar_pendientes(config, _deps(repo))

    assert repo.pedidos_al_cerebro == []
    assert len(repo.encolados) == 1
    assert repo.encolados[0]["payload"]["texto"] == procesador.SOLO_LEO_TEXTO


async def test_si_el_cerebro_falla_no_se_encola_nada_y_el_evento_queda_fallido(config):
    repo = _Repo(eventos=[_evento()])

    async def explota(config, tenant, **kwargs):
        raise RuntimeError("groq caido")

    deps = _deps(repo)
    deps = procesador.Dependencias(**{**deps.__dict__, "responder": explota})

    procesados = await procesador.procesar_pendientes(config, deps)

    assert procesados == 0
    assert repo.encolados == []
    evento_id, ok, error = repo.cerrados[0]
    assert (evento_id, ok) == ("ev-1", False)
    assert "groq" in error.lower()


async def test_un_evento_roto_no_se_lleva_puesto_al_resto_del_lote(config):
    repo = _Repo(eventos=[_evento("ev-1"), _evento("ev-2", conversacion_id="conv-2")])
    original = repo.contexto_de

    async def falla_el_primero(config, *, tenant_id, conversacion_id):
        if conversacion_id == "conv-1":
            raise RuntimeError("conversacion inaccesible")
        return await original(config, tenant_id=tenant_id, conversacion_id=conversacion_id)

    deps = procesador.Dependencias(**{**_deps(repo).__dict__, "contexto_de": falla_el_primero})

    await procesador.procesar_pendientes(config, deps)

    assert [c[0] for c in repo.cerrados] == ["ev-1", "ev-2"]
    assert [c[1] for c in repo.cerrados] == [False, True]


async def test_un_evento_sin_conversacion_no_se_reintenta_para_siempre(config):
    """Sin conversacion no hay nada que contestar y reintentarlo no lo va a
    arreglar. Se cierra bien, no se deja girando en la cola."""
    repo = _Repo(eventos=[_evento(conversacion_id=None)])

    await procesador.procesar_pendientes(config, _deps(repo))

    assert repo.encolados == []
    assert repo.cerrados == [("ev-1", True, "")]


async def test_procesa_todo_el_lote_y_devuelve_cuantos(config):
    repo = _Repo(eventos=[_evento("ev-1"), _evento("ev-2"), _evento("ev-3")])

    procesados = await procesador.procesar_pendientes(config, _deps(repo))

    assert procesados == 3
    assert len(repo.encolados) == 3


def test_las_dependencias_reales_existen_y_apuntan_al_repositorio():
    """Todo lo de arriba usa dobles. Sin esto, un nombre mal escrito en
    `de_produccion()` recien se descubre con un mensaje real perdido."""
    from motor_voz.brain.tenants import repositorio

    deps = procesador.Dependencias.de_produccion()

    assert deps.tomar is repositorio.tomar_eventos_inbox
    assert deps.cerrar is repositorio.cerrar_evento_inbox
    assert deps.tenant_de_id is repositorio.tenant_por_id
    assert deps.contexto_de is repositorio.contexto_de_conversacion
    assert deps.encolar is repositorio.encolar_respuesta
    assert deps.responder is conversacion_mod.responder


def test_la_base_y_el_cerebro_hablan_del_mismo_turno():
    """Si `Turno` se duplicara, el repositorio devolveria uno y
    `armar_mensajes` esperaria el otro, y el historial saldria vacio."""
    from motor_voz.brain import mensajes

    assert conversacion_mod.Turno is mensajes.Turno
    assert procesador.EventoInbox is mensajes.EventoInbox


async def test_sin_nada_pendiente_no_hace_nada(config):
    repo = _Repo(eventos=[])

    assert await procesador.procesar_pendientes(config, _deps(repo)) == 0
    assert repo.cerrados == []


# --- limites de gasto y kill-switch -------------------------------------


async def test_el_tope_se_consulta_antes_de_pagar_el_llm(config):
    """El punto de un tope de gasto es no pagarlo, no descartar la respuesta
    cuando el LLM ya se cobro."""
    repo = _Repo(eventos=[_evento()])
    orden = []

    async def permiso(config, *, tenant_id, conversacion_id):
        orden.append("permiso")
        return Permiso(permitido=True)

    async def responder(config, tenant, **kwargs):
        orden.append("llm")
        return "hola"

    deps = procesador.Dependencias(
        **{**_deps(repo).__dict__, "puede_responder": permiso, "responder": responder}
    )

    await procesador.procesar_pendientes(config, deps)

    assert orden == ["permiso", "llm"]


async def test_con_el_tope_alcanzado_no_se_llama_al_modelo(config):
    repo = _Repo(eventos=[_evento()])

    async def permiso(config, *, tenant_id, conversacion_id):
        return Permiso(permitido=False, motivo="tope diario alcanzado (200)")

    deps = procesador.Dependencias(
        **{**_deps(repo).__dict__, "puede_responder": permiso}
    )

    await procesador.procesar_pendientes(config, deps)

    assert repo.pedidos_al_cerebro == []
    assert repo.encolados == []
    # Se cierra bien: reintentarlo maniana tampoco corresponde, el mensaje ya
    # quedo guardado en la conversacion para que alguien lo lea.
    assert repo.cerrados == [("ev-1", True, "")]


async def test_el_boton_rojo_global_corta_todo(config_apagado):
    """Sin tocar la base ni desconectar canales: los mensajes siguen
    entrando y quedan en la conversacion."""
    repo = _Repo(eventos=[_evento()])

    await procesador.procesar_pendientes(config_apagado, _deps(repo))

    assert repo.pedidos_al_cerebro == []
    assert repo.encolados == []


async def test_el_boton_rojo_no_se_apaga_con_un_valor_raro():
    """Se lista lo que APAGA. Un valor mal escrito deja el agente andando en
    vez de silenciarlo sin que nadie lo note."""
    for valor in ("on", "si", "", "OFFF", "cualquier cosa"):
        assert config_mod.cargar(_entorno(RESPUESTAS_AUTOMATICAS=valor)).respuestas_automaticas

    for valor in ("off", "OFF", "no", "false", "0"):
        assert not config_mod.cargar(
            _entorno(RESPUESTAS_AUTOMATICAS=valor)
        ).respuestas_automaticas


async def test_un_audio_no_consume_tope(config):
    """Avisar que solo leemos texto no paga un LLM ni deberia gastar cupo."""
    repo = _Repo(eventos=[_evento()], turnos=(Turno("user", "  "),))
    consultas = []

    async def permiso(config, *, tenant_id, conversacion_id):
        consultas.append(1)
        return Permiso(permitido=True)

    deps = procesador.Dependencias(
        **{**_deps(repo).__dict__, "puede_responder": permiso}
    )

    await procesador.procesar_pendientes(config, deps)

    assert consultas == []
    assert repo.encolados[0]["payload"]["texto"] == procesador.SOLO_LEO_TEXTO


def test_el_limite_real_apunta_al_repositorio():
    from motor_voz.brain.tenants import repositorio

    deps = procesador.Dependencias.de_produccion()
    assert deps.puede_responder is repositorio.puede_responder
