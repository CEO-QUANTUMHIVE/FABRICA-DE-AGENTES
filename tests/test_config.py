import pytest

from motor_voz.config import Config, ConfigInvalida, cargar

ENTORNO_COMPLETO = {
    "GROQ_API_KEY": "gsk_falsa",
    "FISH_API_KEY": "sk-falsa",
    "LIVEKIT_URL": "ws://localhost:7880",
    "LIVEKIT_API_KEY": "devkey",
    "LIVEKIT_API_SECRET": "secret",
}


def test_carga_un_entorno_completo():
    config = cargar(ENTORNO_COMPLETO)
    assert isinstance(config, Config)
    assert config.groq_api_key == "gsk_falsa"
    assert config.livekit_url == "ws://localhost:7880"


def test_aplica_los_defaults_del_spec():
    config = cargar(ENTORNO_COMPLETO)
    assert config.stt_model == "whisper-large-v3-turbo"
    assert config.llm_model == "openai/gpt-oss-20b"
    assert config.fish_model == "s2.1-pro"
    assert config.fish_latency_mode == "low"
    assert config.idioma == "es"
    assert config.max_session_seconds == 240


def test_permite_pisar_los_defaults():
    entorno = ENTORNO_COMPLETO | {"FISH_MODEL": "s2.1-pro-free", "IDIOMA": "en"}
    config = cargar(entorno)
    assert config.fish_model == "s2.1-pro-free"
    assert config.idioma == "en"


def test_falla_y_nombra_todas_las_variables_faltantes():
    entorno = {"GROQ_API_KEY": "gsk_falsa"}
    with pytest.raises(ConfigInvalida) as error:
        cargar(entorno)
    mensaje = str(error.value)
    assert "FISH_API_KEY" in mensaje
    assert "LIVEKIT_URL" in mensaje
    assert "GROQ_API_KEY" not in mensaje


def test_una_variable_vacia_cuenta_como_faltante():
    entorno = ENTORNO_COMPLETO | {"FISH_API_KEY": "   "}
    with pytest.raises(ConfigInvalida) as error:
        cargar(entorno)
    assert "FISH_API_KEY" in str(error.value)


def test_la_config_es_inmutable():
    config = cargar(ENTORNO_COMPLETO)
    with pytest.raises(Exception):
        config.groq_api_key = "otra"  # type: ignore[misc]


def test_carga_los_campos_de_supabase():
    entorno = ENTORNO_COMPLETO | {
        "SUPABASE_URL": "https://xyz.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "clave-falsa",
    }
    config = cargar(entorno)
    assert config.supabase_url == "https://xyz.supabase.co"
    assert config.supabase_service_role_key == "clave-falsa"


def test_supabase_es_opcional_y_default_vacio():
    """Las fases 0-4 no necesitan Supabase: no puede romper lo que ya anda."""
    config = cargar(ENTORNO_COMPLETO)
    assert config.supabase_url == ""
    assert config.supabase_service_role_key == ""


def test_carga_la_conexion_privada_al_perfilador():
    config = cargar(
        ENTORNO_COMPLETO
        | {
            "CENTRO_INTELIGENCIA_URL": "https://inteligencia.quantumhive.test",
            "CENTRO_INTELIGENCIA_TOKEN": "token-interno",
        }
    )
    assert config.centro_inteligencia_url == "https://inteligencia.quantumhive.test"
    assert config.centro_inteligencia_token == "token-interno"
