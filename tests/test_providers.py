from motor_voz.config import cargar
from motor_voz.voice.providers import stt

ENTORNO = {
    "GROQ_API_KEY": "gsk_falsa",
    "FISH_API_KEY": "sk-falsa",
    "LIVEKIT_URL": "ws://localhost:7880",
    "LIVEKIT_API_KEY": "devkey",
    "LIVEKIT_API_SECRET": "secret",
}


def test_opciones_stt_fuerzan_espanol():
    """El default del plugin es 'en'. Si no lo forzamos, transcribe mal."""
    opciones = stt.opciones(cargar(ENTORNO))
    assert opciones["language"] == "es"


def test_opciones_stt_usan_el_modelo_del_spec():
    opciones = stt.opciones(cargar(ENTORNO))
    assert opciones["model"] == "whisper-large-v3-turbo"


def test_opciones_stt_pasan_la_clave():
    opciones = stt.opciones(cargar(ENTORNO))
    assert opciones["api_key"] == "gsk_falsa"


def test_crear_stt_devuelve_un_stt_de_groq():
    from livekit.plugins import groq

    assert isinstance(stt.crear(cargar(ENTORNO)), groq.STT)


from motor_voz.voice.providers import llm


def test_opciones_llm_usan_gpt_oss_y_no_el_default_del_plugin():
    """El default del plugin es llama-3.3-70b-versatile."""
    opciones = llm.opciones(cargar(ENTORNO))
    assert opciones["model"] == "openai/gpt-oss-20b"


def test_opciones_llm_pasan_la_clave():
    opciones = llm.opciones(cargar(ENTORNO))
    assert opciones["api_key"] == "gsk_falsa"


def test_crear_llm_devuelve_un_llm_de_groq():
    from livekit.plugins import groq

    assert isinstance(llm.crear(cargar(ENTORNO)), groq.LLM)
