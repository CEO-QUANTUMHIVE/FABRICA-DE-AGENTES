"""El test que bloquea el merge de la Fase 9.

Quien habla desde una landing publica no puede alcanzar una tool interna,
aunque el modelo la invente o alguien la inyecte por prompt. La defensa es
que el resolver no la devuelva: no hay ninguna otra.
"""

from __future__ import annotations

import pytest

from motor_voz.brain.tools.registro import (
    MODO_POR_DEFECTO,
    RegistryDesconocido,
    ToolNoPermitida,
    registry_de,
    resolver_tool,
    tools_de,
)

PUBLICAS = {"get_services", "get_business_info", "capture_lead", "transfer_to_human"}
INTERNAS = {"get_mis_leads", "get_mis_metricas", "get_mis_conversaciones"}


class TestQueRegistryLeToca:
    def test_el_modo_interno_alcanza_el_registry_interno(self):
        assert registry_de("interno") == "interno"

    @pytest.mark.parametrize("modo", ["publico", "", "  ", "INTERNO", "Interno", "admin", "x"])
    def test_cualquier_otra_cosa_es_publica(self, modo):
        """Falla cerrado: un modo vacio, mal escrito o inventado es publico.

        Es lo que decide si alguien ve los leads de un negocio. Un typo no
        puede abrirlo.
        """
        assert registry_de(modo) == "publico"

    def test_el_default_es_publico(self):
        assert MODO_POR_DEFECTO == "publico"


class TestDesdeLaLandingNoSeAlcanzaLoInterno:
    @pytest.mark.parametrize("nombre", sorted(INTERNAS))
    def test_no_resuelve_las_internas(self, nombre):
        with pytest.raises(ToolNoPermitida):
            resolver_tool("publico", nombre)

    @pytest.mark.parametrize("nombre", sorted(PUBLICAS))
    def test_si_resuelve_las_publicas(self, nombre):
        assert resolver_tool("publico", nombre) is not None

    def test_el_modo_interno_alcanza_las_dos(self):
        for nombre in PUBLICAS | INTERNAS:
            assert resolver_tool("interno", nombre) is not None

    def test_una_tool_inventada_no_se_resuelve(self):
        """El modelo alucina nombres de tools. No puede alcanzar nada."""
        with pytest.raises(ToolNoPermitida):
            resolver_tool("interno", "borrar_todo")

    def test_el_error_no_distingue_inexistente_de_prohibida(self):
        """Distinguirlas le diria al que prueba cuales existen.

        Una tool que no existe y una que existe pero no alcanza tienen que
        dar el mismo tipo de error y la misma forma de mensaje: lo unico que
        cambia es el nombre, que lo puso el que pregunto.
        """
        with pytest.raises(ToolNoPermitida) as inexistente:
            resolver_tool("publico", "no_existe_esta_tool")
        with pytest.raises(ToolNoPermitida) as prohibida:
            resolver_tool("publico", "get_mis_leads")

        assert type(inexistente.value) is type(prohibida.value)
        sin_nombre = lambda e: str(e.value).replace("no_existe_esta_tool", "X").replace(  # noqa: E731
            "get_mis_leads", "X"
        )
        assert sin_nombre(inexistente) == sin_nombre(prohibida)


class TestNadieCreaNegociosHablando:
    """La regla de Sergio, 2026-08-11: ni el visitante ni el dueño crean nada.

    Dar de alta un negocio es una operacion de la fabrica detras de login. Si
    alguna vez aparece como tool, este test se rompe. **No se arregla el test:
    se discute la decision.**
    """

    @pytest.mark.parametrize(
        "nombre",
        ["crear_negocio", "crear_agente", "crear_tenant", "disparar_web_factory"],
    )
    @pytest.mark.parametrize("modo", ["publico", "interno"])
    def test_ningun_modo_alcanza_una_tool_que_cree(self, modo, nombre):
        with pytest.raises(ToolNoPermitida):
            resolver_tool(modo, nombre)

    def test_ninguna_tool_declarada_tiene_nombre_de_creacion(self):
        """Por si alguien la agrega con otro nombre parecido."""
        prohibidos = ("crear", "alta_", "nuevo_", "borrar", "eliminar")
        for nombre in tools_de("interno"):
            assert not nombre.startswith(prohibidos), f"'{nombre}' parece crear o borrar"


class TestElCatalogo:
    def test_lo_interno_incluye_lo_publico(self):
        """El dueño tambien atiende: es un superconjunto, no otro juego."""
        assert PUBLICAS < tools_de("interno")

    def test_el_publico_es_exactamente_lo_esperado(self):
        assert tools_de("publico") == PUBLICAS

    def test_ningun_registry_esta_vacio(self):
        """Sin esta guarda, un resolver roto pasaria los tests de arriba."""
        assert tools_de("publico")
        assert tools_de("interno")

    def test_un_registry_que_no_existe_falla(self):
        with pytest.raises(RegistryDesconocido):
            tools_de("inventado")

    def test_resolver_con_un_registry_que_no_existe_falla(self):
        with pytest.raises(RegistryDesconocido):
            resolver_tool("inventado", "get_services")
