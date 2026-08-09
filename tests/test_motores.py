"""Los tres motores de conversacion, que son los tres planes comerciales.

Estos tests no llaman a ninguna API: verifican que cada motor arme las
opciones correctas y que prefiera los creditos por sobre la tarjeta.
"""

import pytest

from motor_voz.config import cargar
from motor_voz.voice import motores

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

    def test_la_region_tiene_un_default_razonable(self):
        o = motores.opciones_gemini(cargar(BASE | {"GCP_PROJECT": "p"}))
        assert o["location"] == "us-central1"


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
