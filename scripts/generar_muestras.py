"""Graba un saludo por cada voz del catalogo, una sola vez.

Antes, tocar un nombre en el selector del widget reconectaba la sesion
entera y se pagaba una sintesis. Con 10 voces por motor, un curioso quemaba
10 saludos en 30 segundos, y el TTS es el 86% del costo variable. Estas
muestras se generan una vez, se sirven como estaticos y esa preescucha pasa
a costar cero.

Uso:
    uv run python scripts/generar_muestras.py                # las que falten
    uv run python scripts/generar_muestras.py --motor gemini # solo un motor
    uv run python scripts/generar_muestras.py --solo Puck    # una sola voz
    uv run python scripts/generar_muestras.py --forzar       # regenerar todo

Por defecto NO regenera lo que ya existe. Es a proposito: cada muestra de
OpenAI cuesta una sesion Realtime contra una suscripcion FreeTrial con tope,
y correr el script dos veces no puede costar dos veces.

El catalogo no se repite aca: se lee de `motor_voz.voice.motores`. Si se
agrega una voz alla, aparece aca sola, y el test de `test_muestras.py` avisa
si quedo sin grabar.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import subprocess
import sys
from pathlib import Path

from motor_voz.config import cargar
from motor_voz.voice.motores import VOCES_GEMINI, VOCES_OPENAI, Voz

# El mismo molde que usa el agente de verdad en `Receptor.on_enter`: saludo
# y pregunta, una oracion. La preescucha no promete algo distinto de lo que
# pasa despues. Sin adjetivos con genero, asi el texto sirve para las 18.
TEXTO = "Hola, soy {nombre}, de QuantumHive. ¿En qué te puedo ayudar?"

# Los dos motores entregan PCM crudo a 24 kHz, mono, 16 bits.
FRECUENCIA = 24_000

# El TTS de Gemini NO vive donde vive el modelo Live. `GCP_LOCATION` apunta a
# us-east4, que es donde esta gemini-live-2.5-flash-native-audio, y ahi el TTS
# no existe: da 404 diciendo "model was not found", que se lee como nombre
# equivocado y en realidad es la region. Verificado el 2026-08-10 probando las
# tres regiones: la unica que responde es us-central1. Tampoco sirve el modelo
# por defecto del plugin (gemini-3.1-flash-tts-preview): no esta habilitado en
# el proyecto.
MODELO_GEMINI_TTS = "gemini-2.5-flash-preview-tts"
REGION_GEMINI_TTS = "us-central1"

# Pedir las ocho de corrido agota la cuota del modelo preview a la septima
# (RESOURCE_EXHAUSTED). Como esto se corre una vez en la vida, dos segundos
# entre voces no le molestan a nadie y evitan tener que reintentar.
PAUSA_ENTRE_VOCES = 2.0

DESTINO = Path(__file__).resolve().parents[1] / "frontend" / "widget" / "public" / "assets" / "muestras"


def _a_mp3(pcm: bytes, salida: Path) -> None:
    """Convierte PCM crudo a MP3 mono de 48 kbps (~25 KB por muestra).

    MP3 y no Opus porque es lo unico que reproduce todo iPhone sin
    excepciones, y el widget se usa sobre todo desde el celular.
    """
    salida.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "s16le", "-ar", str(FRECUENCIA), "-ac", "1", "-i", "-",
            # Sin normalizar, las voces salen con hasta 15 dB de diferencia
            # entre si (medido: alloy -18,6 dB contra sage -33,5 dB). El
            # selector existe para comparar voces, y una que suena mas bajo
            # se juzga peor aunque no lo sea. -16 LUFS es el estandar de voz.
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-codec:a", "libmp3lame", "-b:a", "48k",
            "-y", str(salida),
        ],
        input=pcm,
        check=True,
    )


async def _pcm_gemini(clave: str, texto: str) -> bytes:
    """Sintetiza con GeminiTTS, que trae exactamente nuestras 8 voces.

    Va por Vertex AI con las mismas credenciales que el motor en produccion
    (`opciones_gemini`), asi consume creditos de Google Cloud y no tarjeta.
    """
    from livekit.agents import utils
    from livekit.plugins.google.beta import gemini_tts

    from motor_voz.voice import motores

    opciones = motores.opciones_gemini(cargar())
    # De todo lo que arma `opciones_gemini` (que apunta al modelo Realtime)
    # aca solo sirve como facturar: Vertex para creditos, api_key para
    # tarjeta. El modelo y la voz los pone el TTS.
    credenciales = {k: v for k, v in opciones.items() if k in ("vertexai", "project", "api_key")}
    if credenciales.get("vertexai"):
        credenciales["location"] = REGION_GEMINI_TTS
    # El plugin abre sesiones HTTP con el helper de livekit-agents. Fuera de
    # un worker ese contexto no existe y falla, la misma trampa que ya nos
    # costo horas con el plugin de Fish.
    async with utils.http_context.open():
        tts = gemini_tts.TTS(model=MODELO_GEMINI_TTS, voice_name=clave, **credenciales)
        trozos = bytearray()
        async for evento in tts.synthesize(texto):
            trozos.extend(evento.frame.data.tobytes())
        await tts.aclose()
    return bytes(trozos)


async def _pcm_openai(clave: str, texto: str) -> bytes:
    """Sintetiza con una sesion Realtime contra Azure.

    Las 10 voces salen por aca, no por `gpt-4o-mini-tts`: `marin` y `cedar`
    solo existen en Realtime, y el deployment de Realtime es el unico que ya
    esta creado y verificado en la suscripcion. Un solo camino en vez de dos.
    """
    from openai import AsyncAzureOpenAI

    config = cargar()
    cliente = AsyncAzureOpenAI(
        api_key=config.azure_api_key.strip(),
        azure_endpoint=config.azure_endpoint.strip(),
        api_version="2025-04-01-preview",
    )
    trozos = bytearray()
    async with cliente.realtime.connect(model=config.azure_deployment.strip()) as conexion:
        await conexion.session.update(
            session={
                "modalities": ["audio", "text"],
                "voice": clave,
                "output_audio_format": "pcm16",
                # Que lea el texto tal cual. Si se lo dejamos a criterio del
                # modelo, cada voz saluda distinto y las muestras dejan de
                # ser comparables entre si.
                "instructions": f"Decí exactamente esto, sin agregar ni quitar nada: {texto}",
            }
        )
        await conexion.response.create()
        async for evento in conexion:
            if evento.type == "response.audio.delta":
                trozos.extend(base64.b64decode(evento.delta))
            elif evento.type == "response.done":
                break
            elif evento.type == "error":
                raise RuntimeError(f"Realtime devolvio error: {evento.error}")
    await cliente.close()
    return bytes(trozos)


async def generar(motores_pedidos: list[str], solo: str | None, forzar: bool) -> int:
    trabajos: list[tuple[str, str, Voz]] = []
    if "gemini" in motores_pedidos:
        trabajos += [("gemini", c, v) for c, v in VOCES_GEMINI.items()]
    if "openai" in motores_pedidos:
        trabajos += [("openai", c, v) for c, v in VOCES_OPENAI.items()]
    if solo:
        trabajos = [t for t in trabajos if t[1] == solo]
        if not trabajos:
            print(f"No existe la voz {solo!r} en el catalogo.", file=sys.stderr)
            return 1

    fallaron = 0
    intentadas = 0
    for motor, clave, voz in trabajos:
        salida = DESTINO / f"{motor}-{clave}.mp3"
        if salida.exists() and not forzar:
            print(f"  ya esta   {salida.name}")
            continue

        if intentadas:
            await asyncio.sleep(PAUSA_ENTRE_VOCES)
        intentadas += 1

        texto = TEXTO.format(nombre=voz.nombre)
        try:
            pcm = await (_pcm_gemini(clave, texto) if motor == "gemini" else _pcm_openai(clave, texto))
            if not pcm:
                raise RuntimeError("no devolvio audio")
            _a_mp3(pcm, salida)
        except Exception as e:  # noqa: BLE001 - una voz que falla no frena a las otras
            fallaron += 1
            print(f"  FALLO     {salida.name}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        print(f"  grabada   {salida.name}  ({salida.stat().st_size // 1024} KB)  {voz.nombre}")

    return 1 if fallaron else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--motor", choices=["gemini", "openai"], help="solo este motor")
    p.add_argument("--solo", help="solo esta voz, por su clave de API (Puck, marin, ...)")
    p.add_argument("--forzar", action="store_true", help="regenerar lo que ya existe")
    args = p.parse_args()

    pedidos = [args.motor] if args.motor else ["gemini", "openai"]
    print(f"Destino: {DESTINO}")
    return asyncio.run(generar(pedidos, args.solo, args.forzar))


if __name__ == "__main__":
    raise SystemExit(main())
