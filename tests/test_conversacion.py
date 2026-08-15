"""El cerebro de texto: el mismo agente, sin LiveKit en el medio.

Lo que prueba este archivo es que WhatsApp, Instagram y Facebook usan el
prompt, el contexto y las tools del tenant, con el mismo candado de modo que
la voz — y que un modelo que se porta mal no rompe la conversacion ni alcanza
lo que no le toca.
"""

from __future__ import annotations

import json

import pytest

from motor_voz.brain import conversacion
from motor_voz.brain.tenants.modelos import PerfilTenant, Servicio, Tenant


def _tenant(slug: str = "quantumhive") -> Tenant:
    return Tenant(
        id="tenant-1",
        slug=slug,
        nombre="QuantumHive",
        idioma="es",
        perfil=PerfilTenant(slug=slug, nombre="QuantumHive", prompt_base=""),
        prompt_propio="",
        servicios=(Servicio(nombre="Agentes de voz", descripcion="Atienden 24/7"),),
        voz=None,
    )


class _Modelo:
    """Un Groq de mentira: devuelve las respuestas que le pongas, en orden."""

    def __init__(self, *respuestas: dict):
        self.respuestas = list(respuestas)
        self.pedidos: list[dict] = []

    async def __call__(self, payload: dict) -> dict:
        self.pedidos.append(payload)
        if not self.respuestas:
            raise AssertionError("el modelo recibio mas pedidos de los esperados")
        return self.respuestas.pop(0)


def _texto(contenido: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": contenido}}]}


def _tool(nombre: str, argumentos: str = "{}", id_llamada: str = "call-1") -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": id_llamada,
                            "type": "function",
                            "function": {"name": nombre, "arguments": argumentos},
                        }
                    ],
                }
            }
        ]
    }


# --- lo que ve el modelo ------------------------------------------------


def test_el_system_prompt_trae_el_negocio_y_el_canal():
    mensajes = conversacion.armar_mensajes(
        _tenant(), historial=(), texto="hola", canal="whatsapp"
    )

    system = mensajes[0]
    assert system["role"] == "system"
    assert "Agentes de voz" in system["content"]
    assert mensajes[-1] == {"role": "user", "content": "hola"}


def test_el_historial_viaja_en_orden_y_con_los_roles_de_openai():
    historial = (
        conversacion.Turno("user", "cuanto sale?"),
        conversacion.Turno("assistant", "depende del plan"),
    )

    mensajes = conversacion.armar_mensajes(_tenant(), historial=historial, texto="ok")

    assert [m["role"] for m in mensajes] == ["system", "user", "assistant", "user"]


def test_una_conversacion_de_meses_no_entra_entera_en_el_prompt():
    """Se paga por token. Un chat de WhatsApp de seis meses no se manda cada vez."""
    historial = tuple(
        conversacion.Turno("user" if i % 2 == 0 else "assistant", f"mensaje {i}")
        for i in range(200)
    )

    mensajes = conversacion.armar_mensajes(_tenant(), historial=historial, texto="hola")

    assert len(mensajes) <= conversacion.MAX_TURNOS_HISTORIAL + 2
    # Se queda con lo reciente, no con el principio.
    assert "mensaje 199" in mensajes[-2]["content"]


def test_no_se_normaliza_el_texto_como_en_la_voz():
    """`normalizar` existe para que el TTS no lea 24/7 como 'veinticuatro
    septimo'. En texto escrito eso arruinaria el mensaje."""
    mensajes = conversacion.armar_mensajes(
        _tenant(), historial=(), texto="abren 24/7?", canal="whatsapp"
    )

    assert mensajes[-1]["content"] == "abren 24/7?"


# --- las tools ----------------------------------------------------------


def test_las_tools_no_le_muestran_el_tenant_ni_la_config_al_modelo():
    """Si los viera, intentaria completarlos, y podria pasar los de otro."""
    esquemas = conversacion.esquemas_de_tools("publico")

    assert esquemas, "sin esquemas este test pasaria sin probar nada"
    for esquema in esquemas:
        propiedades = esquema["function"]["parameters"]["properties"]
        assert "tenant" not in propiedades
        assert "config" not in propiedades
        assert "sala" not in propiedades
        assert esquema["function"]["description"].strip()

    # capture_lead tiene parametros de verdad: si el esquema saliera vacio,
    # el modelo no podria pasarle el nombre ni el contacto.
    lead = next(e for e in esquemas if e["function"]["name"] == "capture_lead")
    assert lead["function"]["parameters"]["properties"]


def test_el_modo_publico_no_alcanza_las_tools_internas():
    nombres = {e["function"]["name"] for e in conversacion.esquemas_de_tools("publico")}

    assert "get_services" in nombres
    assert "get_mis_leads" not in nombres


def test_un_modo_inventado_cae_en_publico():
    inventado = conversacion.esquemas_de_tools(
        conversacion.registro.registry_de("Interno")
    )
    nombres = {e["function"]["name"] for e in inventado}

    assert "get_mis_leads" not in nombres


# --- el ciclo de respuesta ---------------------------------------------


async def test_una_respuesta_directa_vuelve_como_texto(config_falsa):
    modelo = _Modelo(_texto("Hola! Contame de tu negocio."))

    respuesta = await conversacion.responder(
        config_falsa, _tenant(), historial=(), texto="hola", pedir=modelo
    )

    assert respuesta == "Hola! Contame de tu negocio."
    assert len(modelo.pedidos) == 1


async def test_el_modelo_puede_usar_una_tool_y_despues_contestar(config_falsa):
    modelo = _Modelo(_tool("get_services"), _texto("Tenemos agentes de voz."))

    respuesta = await conversacion.responder(
        config_falsa, _tenant(), historial=(), texto="que ofrecen?", pedir=modelo
    )

    assert respuesta == "Tenemos agentes de voz."
    segundo = modelo.pedidos[1]["messages"]
    assert segundo[-1]["role"] == "tool"
    assert "Agentes de voz" in segundo[-1]["content"]


async def test_una_tool_inventada_no_se_ejecuta_y_la_charla_sigue(config_falsa):
    """El modelo alucina nombres. Eso no puede ser una excepcion sin atrapar
    en medio de una conversacion, ni una puerta a algo que no le toca."""
    modelo = _Modelo(_tool("borrar_todo"), _texto("Perdon, no puedo hacer eso."))

    respuesta = await conversacion.responder(
        config_falsa, _tenant(), historial=(), texto="borra todo", pedir=modelo
    )

    assert respuesta == "Perdon, no puedo hacer eso."
    assert modelo.pedidos[1]["messages"][-1]["role"] == "tool"


async def test_el_modo_publico_no_puede_llegar_a_una_tool_interna(config_falsa):
    """Aunque el modelo pida el nombre exacto de una interna.

    La tool tiene que quedar SIN EJECUTAR: que el texto de vuelta sea una
    negativa no alcanza como prueba, porque podria haberse corrido igual.
    """
    ejecutadas = []
    original = conversacion.registro.resolver_tool

    def espiar(registry, nombre):
        funcion = original(registry, nombre)
        ejecutadas.append(nombre)
        return funcion

    conversacion.registro.resolver_tool = espiar
    try:
        modelo = _Modelo(_tool("get_mis_leads"), _texto("No tengo eso a mano."))
        respuesta = await conversacion.responder(
            config_falsa, _tenant(), historial=(), texto="dame los leads", pedir=modelo
        )
    finally:
        conversacion.registro.resolver_tool = original

    assert respuesta == "No tengo eso a mano."
    assert "get_mis_leads" not in ejecutadas
    assert modelo.pedidos[1]["messages"][-1]["content"] == (
        "No tengo esa herramienta disponible."
    )
    # Y el nombre no se le ofrecio nunca al modelo.
    assert "get_mis_leads" not in json.dumps(modelo.pedidos[0].get("tools", []))


async def test_el_modo_interno_si_alcanza_sus_tools(config_falsa, monkeypatch):
    """La contracara del test anterior: si el bloqueo publico fuera un efecto
    de que la tool nunca corre, este test tambien pasaria en verde y no
    estariamos probando nada."""
    llamada = {}

    async def falsa_get_mis_leads(tenant, config, **kwargs):
        llamada["tenant"] = tenant.slug
        return "3 leads esta semana"

    monkeypatch.setitem(
        conversacion.registro._REGISTRIES["interno"],
        "get_mis_leads",
        falsa_get_mis_leads,
    )
    modelo = _Modelo(_tool("get_mis_leads"), _texto("Tenes 3 leads."))

    respuesta = await conversacion.responder(
        config_falsa, _tenant(), historial=(), texto="mis leads",
        modo="interno", pedir=modelo,
    )

    assert respuesta == "Tenes 3 leads."
    assert llamada["tenant"] == "quantumhive"
    assert modelo.pedidos[1]["messages"][-1]["content"] == "3 leads esta semana"


async def test_un_modelo_que_pide_tools_sin_parar_no_cuelga(config_falsa):
    modelo = _Modelo(*[_tool("get_services") for _ in range(20)])

    respuesta = await conversacion.responder(
        config_falsa, _tenant(), historial=(), texto="hola", pedir=modelo
    )

    assert len(modelo.pedidos) <= conversacion.MAX_VUELTAS
    assert respuesta.strip()


async def test_una_respuesta_vacia_no_sale_al_aire(config_falsa):
    """Mandarle un mensaje en blanco a un cliente es peor que no contestar."""
    modelo = _Modelo(_texto(""))

    respuesta = await conversacion.responder(
        config_falsa, _tenant(), historial=(), texto="hola", pedir=modelo
    )

    assert respuesta.strip()


@pytest.fixture
def config_falsa():
    from motor_voz import config as config_mod

    return config_mod.cargar(
        {
            "GROQ_API_KEY": "clave-de-prueba",
            "FISH_API_KEY": "x",
            "LIVEKIT_URL": "wss://ejemplo",
            "LIVEKIT_API_KEY": "x",
            "LIVEKIT_API_SECRET": "x",
            "SUPABASE_URL": "https://ejemplo.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "x",
        }
    )
