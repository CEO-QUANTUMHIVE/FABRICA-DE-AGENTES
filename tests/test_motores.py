"""Los tres motores de conversacion, que son los tres planes comerciales.

Estos tests no llaman a ninguna API: verifican que cada motor arme las
opciones correctas y que prefiera los creditos por sobre la tarjeta.
"""

import pytest

from motor_voz.config import cargar
from motor_voz.voice import agente, motores

BASE = {
    "GROQ_API_KEY": "gsk_falsa",
    "FISH_API_KEY": "sk-falsa",
    "LIVEKIT_URL": "ws://localhost:7880",
    "LIVEKIT_API_KEY": "devkey",
    "LIVEKIT_API_SECRET": "secret",
}


class TestPlanes:
    def test_el_motor_por_defecto_es_el_basico(self):
        """Nadie paga un plan premium por accidente."""
        assert cargar(BASE).motor == "pipeline"

    def test_cada_motor_corresponde_a_un_plan(self):
        assert motores.PLANES == {
            "pipeline": "basico",
            "gemini": "medio",
            "openai": "premium",
        }

    def test_un_motor_inventado_falla_con_un_mensaje_util(self):
        with pytest.raises(motores.MotorNoDisponible) as e:
            motores.componentes(cargar(BASE | {"MOTOR": "chatgpt"}))
        assert "pipeline" in str(e.value), "El error tiene que listar los validos"


class TestGemini:
    def test_prefiere_vertex_ai_para_consumir_creditos_de_google_cloud(self):
        """Con proyecto de GCP configurado, nunca hay que ir por tarjeta."""
        o = motores.opciones_gemini(
            cargar(BASE | {"GCP_PROJECT": "quantumhive-123", "GOOGLE_API_KEY": "sobra"})
        )
        assert o["vertexai"] is True
        assert o["project"] == "quantumhive-123"
        assert "api_key" not in o, "Con Vertex no se manda la clave de pago por uso"

    def test_cae_a_pago_por_uso_si_no_hay_proyecto(self):
        o = motores.opciones_gemini(cargar(BASE | {"GOOGLE_API_KEY": "clave"}))
        assert o["api_key"] == "clave"
        assert "vertexai" not in o

    def test_sin_credenciales_dice_exactamente_que_falta(self):
        with pytest.raises(motores.MotorNoDisponible) as e:
            motores.opciones_gemini(cargar(BASE))
        assert "GCP_PROJECT" in str(e.value)
        assert "GOOGLE_API_KEY" in str(e.value)

    def test_usa_la_region_donde_vive_el_modelo(self):
        """us-east4, la misma que usa Quantum Assistant. Vertex no sirve el
        modelo Live en cualquier region."""
        o = motores.opciones_gemini(cargar(BASE | {"GCP_PROJECT": "p"}))
        assert o["location"] == "us-east4"

    def test_usa_el_nombre_de_modelo_de_vertex(self):
        """Vertex nombra los modelos distinto que ai.google.dev. Con el
        nombre de la doc publica, la conexion falla."""
        o = motores.opciones_gemini(cargar(BASE | {"GCP_PROJECT": "p"}))
        assert o["model"] == "gemini-live-2.5-flash-native-audio"


class TestOpenAI:
    def test_prefiere_azure_para_consumir_creditos(self):
        o = motores.opciones_openai(
            cargar(BASE | {
                "AZURE_OPENAI_ENDPOINT": "https://qh.openai.azure.com",
                "AZURE_OPENAI_DEPLOYMENT": "realtime",
                "AZURE_OPENAI_API_KEY": "clave-azure",
                "OPENAI_API_KEY": "sobra",
            })
        )
        assert o["_azure"] is True
        assert o["azure_endpoint"] == "https://qh.openai.azure.com"
        assert o["azure_deployment"] == "realtime"

    def test_cae_a_openai_directo_si_no_hay_azure(self):
        o = motores.opciones_openai(cargar(BASE | {"OPENAI_API_KEY": "clave"}))
        assert o["api_key"] == "clave"
        assert "_azure" not in o

    def test_usa_el_modelo_mini_por_defecto(self):
        """El mini sale 2-4x el pipeline; el completo sale 5-8x."""
        o = motores.opciones_openai(cargar(BASE | {"OPENAI_API_KEY": "c"}))
        assert "mini" in o["model"]

    def test_sin_credenciales_dice_exactamente_que_falta(self):
        with pytest.raises(motores.MotorNoDisponible) as e:
            motores.opciones_openai(cargar(BASE))
        assert "AZURE_OPENAI_ENDPOINT" in str(e.value)
        assert "OPENAI_API_KEY" in str(e.value)


class TestPipeline:
    def test_arma_los_tres_proveedores_mas_el_vad(self):
        c = motores.componentes(cargar(BASE))
        assert set(c) == {"stt", "llm", "tts", "vad"}

    def test_los_motores_de_voz_a_voz_no_usan_stt_ni_tts_separados(self):
        """Es la diferencia de arquitectura: generan el habla directamente."""
        o = motores.opciones_gemini(cargar(BASE | {"GCP_PROJECT": "p"}))
        assert "stt" not in o and "tts" not in o


class TestCatalogoDeVoces:
    """El resto del codigo (servidor.py, agente.py) no debe ramificar por
    motor: le pide el catalogo a esta funcion y listo."""

    def test_devuelve_el_catalogo_de_gemini(self):
        catalogo, default = motores.catalogo_de_voces("gemini")
        assert catalogo == motores.VOCES_GEMINI
        assert default == motores.VOZ_GEMINI_POR_DEFECTO

    def test_devuelve_el_catalogo_de_openai(self):
        catalogo, default = motores.catalogo_de_voces("openai")
        assert catalogo == motores.VOCES_OPENAI
        assert default == motores.VOZ_OPENAI_POR_DEFECTO
        assert len(catalogo) == 10

    def test_el_pipeline_no_tiene_catalogo(self):
        """Su voz es la clonada de Fish, configurada por tenant, no una lista."""
        assert motores.catalogo_de_voces("pipeline") == ({}, "")

    def test_un_motor_inventado_tampoco_tiene_catalogo(self):
        assert motores.catalogo_de_voces("chatgpt") == ({}, "")

    def test_las_voces_de_openai_son_las_del_sdk_instalado(self):
        """Verificadas contra
        openai/types/realtime/realtime_audio_config_output.py el 2026-08-09."""
        assert set(motores.VOCES_OPENAI) == {
            "alloy", "ash", "ballad", "coral", "echo",
            "sage", "shimmer", "verse", "marin", "cedar",
        }

    def test_los_nombres_de_openai_no_se_repiten_con_gemini(self):
        """Si se repitieran, el visitante no podria distinguir de que motor
        es la voz al ver el nombre solo."""
        assert set(motores.VOCES_OPENAI.values()).isdisjoint(motores.VOCES_GEMINI.values())


class TestVozDeLaSala:
    """Formato: demo-<tenant>-<motor>-<voz>-<aleatorio>."""

    def test_extrae_la_voz_de_gemini(self):
        assert (
            agente.voz_de_la_sala("demo-quantumhive-gemini-Charon-ab12cd", "gemini", "x")
            == "Charon"
        )

    def test_extrae_la_voz_de_openai(self):
        assert (
            agente.voz_de_la_sala("demo-quantumhive-openai-coral-ab12cd", "openai", "x")
            == "coral"
        )

    def test_no_cruza_una_voz_de_gemini_en_una_sala_de_openai(self):
        """Un nombre de sala armado a mano no le puede pedir a OpenAI una voz
        que es de Gemini."""
        assert (
            agente.voz_de_la_sala("demo-quantumhive-openai-Puck-ab12cd", "openai", "marin")
            == "marin"
        )

    def test_el_pipeline_cae_siempre_al_default(self):
        assert agente.voz_de_la_sala("demo-quantumhive-pipeline--ab12cd", "pipeline", "") == ""

    def test_un_slug_con_guion_bajo_no_rompe_el_parseo(self):
        """Los slugs usan guion bajo justamente para que partir por - sea seguro."""
        assert (
            agente.voz_de_la_sala("demo-demo_capilar-gemini-Leda-ab12cd", "gemini", "x") == "Leda"
        )

    def test_el_formato_viejo_sin_tenant_cae_al_default(self):
        """Una sala de antes de la Fase 8 no se interpreta mal: cae al default."""
        assert agente.voz_de_la_sala("demo-gemini-Charon-ab12cd", "gemini", "Puck") == "Puck"

    def test_un_nombre_mal_formado_cae_al_default(self):
        assert agente.voz_de_la_sala("sala-manual", "gemini", "Puck") == "Puck"


class TestMotorDeLaSala:
    def test_extrae_el_motor(self):
        assert agente.motor_de_la_sala("demo-quantumhive-gemini-Leda-ab12cd", "pipeline") == "gemini"

    def test_un_motor_inventado_cae_al_de_config(self):
        """Nadie se cuela a un plan mas caro armando el nombre de sala."""
        assert agente.motor_de_la_sala("demo-quantumhive-chatgpt-x-ab12cd", "pipeline") == "pipeline"

    def test_el_formato_viejo_cae_al_de_config(self):
        assert agente.motor_de_la_sala("demo-gemini-Leda-ab12cd", "pipeline") == "pipeline"


class TestVozDelTenant:
    """La voz del tenant llega hasta el TTS sin pasar por Config (spec S8)."""

    def test_componentes_pipeline_propaga_la_voz_del_tenant(self):
        config = cargar(BASE | {"MOTOR": "pipeline"})
        comps = motores.componentes(config, voice_id_override="voz-del-tenant")
        assert comps["tts"].voice_id == "voz-del-tenant"

    def test_componentes_sin_override_usa_la_voz_de_config(self):
        config = cargar(BASE | {"MOTOR": "pipeline", "FISH_VOICE_ID": "voz-de-config"})
        comps = motores.componentes(config)
        assert comps["tts"].voice_id == "voz-de-config"
