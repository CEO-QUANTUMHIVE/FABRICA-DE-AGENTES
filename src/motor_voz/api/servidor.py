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
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from aiohttp import web
from livekit import api

from motor_voz.api import niveles as catalogo_niveles
from motor_voz.api.limites import LimiteAlcanzado, Limitador
from motor_voz.brain.tenants import repositorio
from motor_voz.brain.tenants.modelos import Tenant
from motor_voz.brain.tenants.resolver import TENANT_POR_DEFECTO
from motor_voz.config import Config, cargar
from motor_voz.voice.motores import catalogo_de_voces, ruta_de_muestra

logger = logging.getLogger("motor-voz.api")
ORIGENES_PERMITIDOS = "*"  # la demo es publica; en produccion, el dominio propio

# Se inyecta para poder testear sin red: los tests pasan un tenant falso y la
# suite sigue sin depender de que Supabase este arriba.
ObtenerTenant = Callable[[Config, str], Awaitable[Tenant]]
TenantDeDominio = Callable[[Config, str], Awaitable[str | None]]

# Los unicos entornos donde se puede pedir un tenant por el cuerpo. Se listan
# los que aflojan, no los que aprietan: asi un valor escrito distinto, en otro
# idioma o vacio se comporta como produccion. Falla cerrado a proposito — el
# .env local dice "development" y el de la VM podria decir "production", y
# comparar contra una sola palabra dejaba el agujero abierto.
ENTORNOS_DE_DESARROLLO = frozenset({"development", "desarrollo", "dev", "local", "test"})


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
            {
                "voces": [
                    {
                        "voz": clave,
                        "nombre": v.nombre,
                        "genero": v.genero,
                        # El saludo pregrabado, para que preescuchar una voz
                        # no cueste una sintesis. La ruta la decide el
                        # backend, que ya es dueño del catalogo: el navegador
                        # no arma nombres de archivo por convencion.
                        "muestra": ruta_de_muestra(motor, clave),
                    }
                    for clave, v in catalogo.items()
                ]
            }
        )
    )


async def emitir_token(peticion: web.Request) -> web.Response:
    config: Config = peticion.app["config"]
    limitador: Limitador = peticion.app["limitador"]
    obtener_tenant: ObtenerTenant = peticion.app["obtener_tenant"]
    tenant_de_dominio: TenantDeDominio = peticion.app["tenant_de_dominio"]

    try:
        cuerpo = await peticion.json()
    except json.JSONDecodeError:
        cuerpo = {}

    try:
        nivel = catalogo_niveles.resolver(cuerpo.get("nivel", 1))
    except catalogo_niveles.NivelInvalido as e:
        return _cors(web.json_response({"error": str(e)}, status=400))

    # El tenant sale del DOMINIO donde esta embebido el widget, no de lo que
    # mande el navegador. La cabecera Origin la pone el navegador y el codigo
    # de la pagina no la puede cambiar, asi que una landing solo puede
    # invocar al agente de su dueño. Antes salia del cuerpo, y con eso
    # cualquiera se llevaba el agente real de otro negocio con un curl.
    origen = peticion.headers.get("Origin", "")
    dominio = (urlparse(origen).hostname or "") if origen else ""

    # Se resuelve ANTES de gastar el cupo del limitador: pedir un negocio que
    # no existe no le tiene que consumir intentos a la IP.
    try:
        tenant_slug = await tenant_de_dominio(config, dominio)
        if tenant_slug is None:
            # Dominio no registrado. En produccion cae a nuestro propio agente
            # y el cuerpo se ignora por completo. Fuera de produccion si se
            # honra, que es como se prueba el aislamiento a oido en local.
            if config.entorno in ENTORNOS_DE_DESARROLLO:
                tenant_slug = (cuerpo.get("tenant") or "").strip() or TENANT_POR_DEFECTO
            else:
                tenant_slug = TENANT_POR_DEFECTO
        tenant = await obtener_tenant(config, tenant_slug)
    except repositorio.TenantNoEncontrado as e:
        return _cors(web.json_response({"error": str(e)}, status=404))
    except Exception:
        # 503 y no 500: que Supabase se caiga no es un error del que pide, y
        # el mensaje tiene que invitar a reintentar en vez de asustar.
        logger.exception("no se pudo resolver el tenant '%s'", tenant_slug)
        return _cors(
            web.json_response(
                {"error": "No se pudo validar el negocio. Reintenta en un momento."},
                status=503,
            )
        )

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

    sala = f"demo-{tenant.slug}-{nivel.motor}-{voz}-{secrets.token_hex(6)}"
    identidad = f"visitante-{secrets.token_hex(4)}"

    token = (
        api.AccessToken(config.livekit_api_key, config.livekit_api_secret)
        .with_identity(identidad)
        .with_name("Visitante")
        # El motor, la voz y el tenant van firmados: el agente lee de aca, no
        # del navegador. Ademas el tenant queda fijado en el nombre de sala
        # (ver brain/tenants/resolver.py), que VideoGrants restringe.
        .with_metadata(
            json.dumps(
                {
                    "motor": nivel.motor,
                    "nivel": nivel.numero,
                    "voz": voz,
                    "tenant": tenant.slug,
                }
            )
        )
        .with_grants(
            api.VideoGrants(
                room_join=True, room=sala, can_publish=True, can_subscribe=True
            )
        )
        .to_jwt()
    )

    logger.info(
        "token emitido | nivel=%s motor=%s tenant=%s voz=%s sala=%s",
        nivel.numero, nivel.motor, tenant.slug, voz, sala,
    )
    return _cors(
        web.json_response(
            {
                "token": token,
                "url": config.livekit_url,
                "sala": sala,
                "nivel": nivel.numero,
                "plan": nivel.plan,
                "tenant": tenant.slug,
                "voz": voz,
                "nombre_voz": catalogo[voz].nombre if voz in catalogo else "",
                "duracion_maxima_seg": config.max_session_seconds,
            }
        )
    )


async def preflight(peticion: web.Request) -> web.Response:
    return _cors(web.Response(status=204))


def crear_app(
    config: Config | None = None,
    obtener_tenant: ObtenerTenant | None = None,
    tenant_de_dominio: TenantDeDominio | None = None,
) -> web.Application:
    cfg = config or cargar()
    app = web.Application()
    app["config"] = cfg
    app["obtener_tenant"] = obtener_tenant or repositorio.obtener_tenant
    app["tenant_de_dominio"] = tenant_de_dominio or repositorio.tenant_de_dominio
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
