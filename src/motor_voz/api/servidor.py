"""Servidor HTTP: emite tokens firmados y expone el catalogo de niveles.

    GET  /api/salud     estado del servicio
    GET  /api/niveles   los tres niveles, para dibujar el selector
    POST /api/token     {"nivel": 1|2|3} -> token de LiveKit

El nivel viaja FIRMADO dentro del token, en la metadata del participante.
El agente lee de ahi, no de lo que diga el navegador: si el cliente pudiera
elegir el motor por su cuenta, cualquiera consumiria el plan premium.

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

    ip = _ip_de(peticion)
    try:
        limitador.registrar(ip)
    except LimiteAlcanzado as e:
        logger.info("limite alcanzado para %s", ip)
        return _cors(web.json_response({"error": str(e)}, status=429))

    sala = f"demo-{nivel.motor}-{secrets.token_hex(6)}"
    identidad = f"visitante-{secrets.token_hex(4)}"

    token = (
        api.AccessToken(config.livekit_api_key, config.livekit_api_secret)
        .with_identity(identidad)
        .with_name("Visitante")
        # El motor va firmado: el agente lee de aca y no del navegador.
        .with_metadata(json.dumps({"motor": nivel.motor, "nivel": nivel.numero}))
        .with_grants(
            api.VideoGrants(
                room_join=True, room=sala, can_publish=True, can_subscribe=True
            )
        )
        .to_jwt()
    )

    logger.info("token emitido | nivel=%s motor=%s sala=%s", nivel.numero, nivel.motor, sala)
    return _cors(
        web.json_response(
            {
                "token": token,
                "url": config.livekit_url,
                "sala": sala,
                "nivel": nivel.numero,
                "plan": nivel.plan,
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
