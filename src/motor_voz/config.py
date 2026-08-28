"""Unico punto del motor que lee variables de entorno.

Ningun otro modulo debe llamar a os.environ. Todo recibe un Config.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

OBLIGATORIAS = (
    "GROQ_API_KEY",
    "FISH_API_KEY",
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
)


VOCABULARIO_DE_MARCA = (
    "Conversacion en espanol rioplatense sobre QuantumHive: paginas web "
    "inteligentes, empleado virtual, catalogo vivo, avatar y clonacion de voz."
)
"""Pista de vocabulario para Whisper.

Sin esto, Groq transcribe la marca como "quantum high". Verificado el
2026-08-08 con una grabacion real de 60 segundos. Whisper usa este texto
como contexto previo y corrige los nombres propios.
"""


class ConfigInvalida(RuntimeError):
    """El entorno no tiene lo minimo para arrancar el motor."""


@dataclass(frozen=True)
class Config:
    groq_api_key: str
    fish_api_key: str
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    stt_model: str
    llm_model: str
    fish_model: str
    fish_latency_mode: str
    fish_voice_id: str
    fish_speed: float
    fish_temperature: float
    idioma: str
    stt_prompt: str
    max_session_seconds: int
    max_sesiones_por_ip_hora: int
    max_sesiones_por_dia: int
    api_puerto: int
    # Cuando el agente decide que el visitante empezo y termino de hablar.
    # Se ajustan a oido, no por calculo, y valen para los tres motores.
    vad_silencio_ms: int
    vad_relleno_ms: int
    vad_umbral: float
    # Plan comercial: que motor de conversacion usa este tenant.
    motor: str
    # Plan medio - Gemini Live. Con gcp_project va por Vertex AI y consume
    # creditos de Google Cloud; con google_api_key es pago por uso.
    gemini_model: str
    gemini_voice: str
    gemini_temperature: float
    google_api_key: str
    gcp_project: str
    gcp_location: str
    # Plan premium - OpenAI Realtime. Con azure_endpoint consume creditos de
    # Azure; con openai_api_key es pago por uso.
    openai_model: str
    openai_voice: str
    openai_api_key: str
    azure_endpoint: str
    azure_deployment: str
    azure_api_key: str
    supabase_url: str
    supabase_service_role_key: str
    # En produccion el tenant sale SOLO del dominio donde esta embebido el
    # widget. Fuera de produccion se puede pedir por el cuerpo, que es como se
    # prueba el aislamiento a oido en local.
    entorno: str
    # Comunes a la app de Meta, no a un numero. El access token de cada numero
    # NO vive aca: va al almacen de secretos y `tenant_canales` guarda solo la
    # referencia. Con default para que un despliegue viejo no deje de arrancar
    # por no tenerlos; el webhook falla cerrado si estan vacios.
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_embedded_signup_config_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_registration_pin: str = ""
    whatsapp_api_version: str = "v21.0"
    # El boton rojo. Corta las respuestas automaticas de TODOS los tenants sin
    # tocar la base ni desconectar canales. Existe para el momento en que algo
    # se desmadra y no hay tiempo de averiguar de quien es.
    respuestas_automaticas: bool = True
    # Credencial maquina-a-maquina del plano de control. Vacia = las rutas del
    # CEO existen pero fallan cerradas; nunca se reutiliza una clave de voz.
    quantumcore_token: str = ""
    # Servicio server-to-server que investiga la web y las redes públicas del
    # negocio. El token nunca se expone al frontend de la Fábrica.
    centro_inteligencia_url: str = ""
    centro_inteligencia_token: str = ""


def cargar(entorno: dict[str, str] | None = None) -> Config:
    e = dict(os.environ) if entorno is None else entorno

    faltantes = [n for n in OBLIGATORIAS if not (e.get(n) or "").strip()]
    if faltantes:
        raise ConfigInvalida(
            "Faltan variables de entorno obligatorias: "
            + ", ".join(faltantes)
            + ". Copiar .env.example a .env y completarlas."
        )

    return Config(
        groq_api_key=e["GROQ_API_KEY"].strip(),
        fish_api_key=e["FISH_API_KEY"].strip(),
        livekit_url=e["LIVEKIT_URL"].strip(),
        livekit_api_key=e["LIVEKIT_API_KEY"].strip(),
        livekit_api_secret=e["LIVEKIT_API_SECRET"].strip(),
        stt_model=e.get("GROQ_STT_MODEL", "whisper-large-v3-turbo"),
        llm_model=e.get("GROQ_LLM_MODEL", "openai/gpt-oss-20b"),
        stt_prompt=e.get("STT_PROMPT", VOCABULARIO_DE_MARCA),
        fish_model=e.get("FISH_MODEL", "s2.1-pro"),
        fish_latency_mode=e.get("FISH_LATENCY_MODE", "low"),
        fish_speed=float(e.get("FISH_SPEED", "1.25")),
        fish_temperature=float(e.get("FISH_TEMPERATURE", "1.0")),
        fish_voice_id=e.get("FISH_VOICE_ID", ""),
        idioma=e.get("IDIOMA", "es"),
        max_session_seconds=int(e.get("MAX_SESSION_SECONDS", "240")),
        max_sesiones_por_ip_hora=int(e.get("MAX_SESSIONS_PER_IP_HOUR", "20")),
        max_sesiones_por_dia=int(e.get("MAX_SESSIONS_PER_DAY", "300")),
        api_puerto=int(e.get("PORT") or e.get("API_PUERTO") or "8080"),
        # Los defaults de los tres motores cortan demasiado rapido: con un
        # ruido de fondo el agente se callaba creyendo que le hablaban.
        # 900 ms de silencio antes de dar el turno por terminado y un
        # umbral mas alto que el default (0.5) son los valores que ya venia
        # usando QUANTUM-ASISTENTE- con Gemini Live.
        vad_silencio_ms=int(e.get("VAD_SILENCIO_MS", "900")),
        vad_relleno_ms=int(e.get("VAD_RELLENO_MS", "300")),
        vad_umbral=float(e.get("VAD_UMBRAL", "0.6")),
        # El default es el estricto: si nadie dice lo contrario, se comporta
        # como produccion. Aflojar el aislamiento tiene que ser deliberado.
        entorno=e.get("ENVIRONMENT", "produccion").strip().lower(),
        motor=e.get("MOTOR", "pipeline").strip().lower(),
        gemini_model=e.get("GEMINI_MODEL", "gemini-live-2.5-flash-native-audio"),
        gemini_voice=e.get("GEMINI_VOICE", "Puck"),
        gemini_temperature=float(e.get("GEMINI_TEMPERATURE", "0.8")),
        google_api_key=e.get("GOOGLE_API_KEY", ""),
        gcp_project=e.get("GCP_PROJECT", ""),
        gcp_location=e.get("GCP_LOCATION", "us-east4"),
        openai_model=e.get("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1-mini"),
        openai_voice=e.get("OPENAI_VOICE", "alloy"),
        openai_api_key=e.get("OPENAI_API_KEY", ""),
        azure_endpoint=e.get("AZURE_OPENAI_ENDPOINT", ""),
        azure_deployment=e.get("AZURE_OPENAI_DEPLOYMENT", ""),
        azure_api_key=e.get("AZURE_OPENAI_API_KEY", ""),
        supabase_url=e.get("SUPABASE_URL", "").strip(),
        # Supabase le cambio el nombre a esta clave: antes era la service_role
        # (un JWT), ahora es la secret key (sb_secret_...). Se aceptan los dos
        # nombres porque conviven: el .env de la VM tiene solo el nuevo y el
        # local tiene los dos con el mismo valor. Sin esto, produccion arranca
        # sin quejarse y devuelve 503 en cada pedido de token.
        supabase_service_role_key=(
            e.get("SUPABASE_SERVICE_ROLE_KEY") or e.get("SUPABASE_SECRET_KEY") or ""
        ).strip(),
        meta_app_id=e.get("META_APP_ID", "").strip(),
        meta_app_secret=e.get("META_APP_SECRET", "").strip(),
        meta_embedded_signup_config_id=e.get(
            "META_EMBEDDED_SIGNUP_CONFIG_ID", ""
        ).strip(),
        whatsapp_verify_token=e.get("WHATSAPP_VERIFY_TOKEN", "").strip(),
        whatsapp_registration_pin=e.get("WHATSAPP_REGISTRATION_PIN", "").strip(),
        # Fijada explicita. "la ultima" cambia sola y rompe sin aviso.
        whatsapp_api_version=e.get("WHATSAPP_API_VERSION", "v21.0").strip(),
        # Se lista lo que APAGA, no lo que enciende: asi un valor mal escrito
        # deja el agente andando en vez de silenciarlo sin que nadie lo note.
        # Apagarlo tiene que ser deliberado; que siga andando es el default.
        respuestas_automaticas=(
            e.get("RESPUESTAS_AUTOMATICAS", "on").strip().lower()
            not in {"off", "no", "false", "0"}
        ),
        quantumcore_token=e.get("QUANTUMCORE_TOKEN", "").strip(),
        centro_inteligencia_url=e.get("CENTRO_INTELIGENCIA_URL", "").strip(),
        centro_inteligencia_token=e.get("CENTRO_INTELIGENCIA_TOKEN", "").strip(),
    )
