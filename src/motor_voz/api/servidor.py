"""Servidor HTTP: emite tokens firmados y expone los catalogos de niveles y voces.

    GET  /api/salud          estado del servicio
    GET  /api/niveles        los tres niveles, para dibujar el selector
    GET  /api/voces          catalogo de voces del motor pedido (?motor=gemini|openai)
    POST /api/token          {"nivel": 1|2|3, "voz"?: "Puck"|...} -> token de LiveKit

El nivel y la voz viajan FIRMADOS dentro del token, en la metadata del
participante y en el nombre de sala. El agente lee de ahi, no de lo que
diga el navegador: si el cliente pudiera elegirlos por su cuenta,
cualquiera consumiria el plan premium o pediria una voz que no existe.

Se usa aiohttp porque ya viene con LiveKit. No suma dependencias.
"""

from __future__ import annotations

import json
import logging
import secrets

from aiohttp import web
from livekit import api

from motor_voz.api import niveles as catalogo_niveles
from motor_voz.api.limites import LimiteAlcanzado, Limitador
from motor_voz.config import Config, cargar
from motor_voz.voice.motores import catalogo_de_voces

logger = logging.getLogger("motor-voz.api")
ORIGENES_PERMITIDOS = "*"  # la demo es publica; en produccion, el dominio propio


def _cors(respuesta: web.StreamResponse) -> web.StreamResponse:
    respuesta.headers["Access-Control-Allow-Origin"] = ORIGENES_PERMITIDOS
    respuesta.headers["Access-Control-Allow-Headers"] = "Content-Type"
    respuesta.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return respuesta


def _ip_de(peticion: web.Request) -> str:
    reenviado = peticion.headers.get("X-Forwarded-For", "")
    if reenviado:
        return reenviado.split(",")[0].strip()
    return peticion.remote or "desconocida"


async def salud(peticion: web.Request) -> web.Response:
    limitador: Limitador = peticion.app["limitador"]
    return _cors(web.json_response({"estado": "ok", **limitador.estado()}))


async def listar_niveles(peticion: web.Request) -> web.Response:
    return _cors(web.json_response({"niveles": catalogo_niveles.catalogo()}))


async def listar_voces(peticion: web.Request) -> web.Response:
    motor = peticion.rel_url.query.get("motor", "gemini")
    catalogo, _ = catalogo_de_voces(motor)
    return _cors(
        web.json_response(
            {"voces": [{"voz": clave, "nombre": nombre} for clave, nombre in catalogo.items()]}
        )
    )


async def emitir_token(peticion: web.Request) -> web.Response:
    config: Config = peticion.app["config"]
    limitador: Limitador = peticion.app["limitador"]

    try:
        cuerpo = await peticion.json()
    except json.JSONDecodeError:
        cuerpo = {}

    try:
        nivel = catalogo_niveles.resolver(cuerpo.get("nivel", 1))
    except catalogo_niveles.NivelInvalido as e:
        return _cors(web.json_response({"error": str(e)}, status=400))

    # La voz solo tiene sentido en los motores de voz a voz; en el pipeline
    # se ignora (su voz es la clonada de Fish, por tenant). Igual que el
    # motor, viaja firmada adentro del nombre de sala: el navegador no puede
    # pedir una voz que no exista, ni cruzar una voz de un motor con otro.
    catalogo, voz_por_defecto = catalogo_de_voces(nivel.motor)
    if not catalogo:
        # campo vacio (no ausente): asi el nombre de sala mantiene siempre
        # las mismas posiciones sin importar el motor, y el parser de
        # agente.py no tiene que ramificar por eso.
        voz = ""
    else:
        voz = str(cuerpo.get("voz") or voz_por_defecto)
        if voz not in catalogo:
            return _cors(
                web.json_response(
                    {"error": f"Voz invalida. Validas: {', '.join(catalogo)}"}, status=400
                )
            )

    ip = _ip_de(peticion)
    try:
        limitador.registrar(ip)
    except LimiteAlcanzado as e:
        logger.info("limite alcanzado para %s", ip)
        return _cors(web.json_response({"error": str(e)}, status=429))

    sala = f"demo-{nivel.motor}-{voz}-{secrets.token_hex(6)}"
    identidad = f"visitante-{secrets.token_hex(4)}"

    token = (
        api.AccessToken(config.livekit_api_key, config.livekit_api_secret)
        .with_identity(identidad)
        .with_name("Visitante")
        # El motor y la voz van firmados: el agente lee de aca, no del navegador.
        .with_metadata(json.dumps({"motor": nivel.motor, "nivel": nivel.numero, "voz": voz}))
        .with_grants(
            api.VideoGrants(
                room_join=True, room=sala, can_publish=True, can_subscribe=True
            )
        )
        .to_jwt()
    )

    logger.info(
        "token emitido | nivel=%s motor=%s voz=%s sala=%s", nivel.numero, nivel.motor, voz, sala
    )
    return _cors(
        web.json_response(
            {
                "token": token,
                "url": config.livekit_url,
                "sala": sala,
                "nivel": nivel.numero,
                "plan": nivel.plan,
                "voz": voz,
                "nombre_voz": catalogo.get(voz, ""),
                "duracion_maxima_seg": config.max_session_seconds,
            }
        )
    )


async def preflight(peticion: web.Request) -> web.Response:
    return _cors(web.Response(status=204))


def crear_app(config: Config | None = None) -> web.Application:
    cfg = config or cargar()
    app = web.Application()
    app["config"] = cfg
    app["limitador"] = Limitador(
        por_ip_hora=cfg.max_sesiones_por_ip_hora,
        por_dia=cfg.max_sesiones_por_dia,
    )
    app.add_routes(
        [
            web.get("/api/salud", salud),
            web.get("/api/niveles", listar_niveles),
            web.get("/api/voces", listar_voces),
            web.post("/api/token", emitir_token),
            web.options("/api/{resto:.*}", preflight),
        ]
    )
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cfg = cargar()
    logger.info(
        "API en http://localhost:%s | limites: %s/IP/hora, %s/dia",
        cfg.api_puerto,
        cfg.max_sesiones_por_ip_hora,
        cfg.max_sesiones_por_dia,
    )
    web.run_app(crear_app(cfg), port=cfg.api_puerto, print=None)


if __name__ == "__main__":
    main()
