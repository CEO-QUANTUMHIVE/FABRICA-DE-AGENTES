"""El adaptador que le entrega las tools al modelo.

Lo que se fija aca es que el modelo NO vea el tenant ni la sala. Si los viera
podria pasarle el de otro negocio, y el modelo le hace caso a quien le habla.
"""

from __future__ import annotations

import inspect

import pytest

from motor_voz.brain.tenants.modelos import PerfilTenant, Servicio, Tenant
from motor_voz.config import cargar
from motor_voz.voice import herramientas
from motor_voz.voice.agente import modo_de_metadata

ENTORNO = {
    "GROQ_API_KEY": "gsk_falsa",
    "FISH_API_KEY": "sk-falsa",
    "LIVEKIT_URL": "ws://localhost:7880",
    "LIVEKIT_API_KEY": "devkey",
    "LIVEKIT_API_SECRET": "secreto-largo-de-prueba-1234567890",
}

PUBLICAS = {"get_services", "get_business_info", "capture_lead", "transfer_to_human"}
INTERNAS = {"get_mis_leads", "get_mis_metricas", "get_mis_conversaciones"}

SALA = "demo-demo_capilar-pipeline--abc123"


def _tenant() -> Tenant:
    return Tenant(
        id="tenant-de-prueba",
        slug="demo_capilar",
        nombre="Barberia Demo",
        idioma="es",
        perfil=PerfilTenant(slug="capilar", nombre="Barberia", prompt_base="Sos de una barberia."),
        prompt_propio="",
        servicios=(Servicio(nombre="Corte clasico", descripcion="Corte tradicional"),),
        voz=None,
    )


def _nombres(tools) -> set[str]:
    return {getattr(t, "__livekit_tool_info").name for t in tools}


def _armar(modo: str):
    return herramientas.para(modo, _tenant(), cargar(ENTORNO), SALA)


class TestQueToolsRecibeElModelo:
    def test_en_publico_solo_las_publicas(self):
        assert _nombres(_armar("publico")) == PUBLICAS

    def test_en_interno_las_dos(self):
        assert _nombres(_armar("interno")) == PUBLICAS | INTERNAS

    @pytest.mark.parametrize("modo", ["", "  ", "INTERNO", "inventado"])
    def test_un_modo_raro_entrega_solo_las_publicas(self, modo):
        """Es lo que decide si alguien ve los leads. Un typo no puede abrirlo."""
        assert _nombres(_armar(modo)) == PUBLICAS


class TestModoFirmadoDeLaSesion:
    def test_interno_exacto_abre_el_modo_interno(self):
        assert modo_de_metadata('{"modo":"interno"}') == "interno"

    @pytest.mark.parametrize(
        "metadata",
        ["", "no-es-json", "[]", "{}", '{"modo":"INTERNO"}', '{"modo":"inventado"}'],
    )
    def test_metadata_ausente_rota_o_rara_falla_cerrado(self, metadata):
        assert modo_de_metadata(metadata) == "publico"

class TestElModeloNoVeLoQueNoDebe:
    @pytest.mark.parametrize("modo", ["publico", "interno"])
    def test_ninguna_tool_expone_tenant_config_ni_sala(self, modo):
        """Si el modelo viera el tenant, podria pasarle el de otro negocio."""
        for tool in _armar(modo):
            visibles = set(inspect.signature(tool).parameters)
            assert not (visibles & {"tenant", "config", "sala"}), (
                f"{getattr(tool, '__livekit_tool_info').name} expone {visibles}"
            )

    def test_las_tools_tienen_descripcion(self):
        """Sin descripcion el modelo no sabe cuando llamarla y no la usa."""
        for tool in _armar("publico"):
            info = getattr(tool, "__livekit_tool_info")
            assert info.description, f"{info.name} no tiene descripcion"


class TestLoQueQuedoAtado:
    async def test_la_tool_responde_con_los_datos_del_tenant_atado(self):
        """El tenant no viaja como argumento: quedo atado al armarla."""
        tool = next(
            t for t in _armar("publico") if getattr(t, "__livekit_tool_info").name == "get_services"
        )
        respuesta = await tool()
        assert "Corte clasico" in respuesta
        assert "Barberia Demo" in respuesta
