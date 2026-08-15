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
from motor_voz.brain.mensajes import CanalTenant, ResultadoIngreso
from motor_voz.brain.tenants import repositorio
from motor_voz.brain.tenants.modelos import Tenant
from motor_voz.channels.whatsapp import firma as firma_whatsapp
from motor_voz.channels.whatsapp import payload as payload_whatsapp
from motor_voz.brain.tenants.resolver import TENANT_POR_DEFECTO
from motor_voz.config import Config, ConfigInvalida, cargar
from motor_voz.voice.motores import catalogo_de_voces, ruta_de_muestra

logger = logging.getLogger("motor-voz.api")
ORIGENES_PERMITIDOS = "*"  # la demo es publica; en produccion, el dominio propio

# Se inyecta para poder testear sin red: los tests pasan un tenant falso y la
# suite sigue sin depender de que Supabase este arriba.
ObtenerTenant = Callable[[Config, str], Awaitable[Tenant]]
TenantDeDominio = Callable[[Config, str], Awaitable[str | None]]
UsuarioDeToken = Callable[[Config, str], Awaitable[str | None]]
RolDeUsuarioEnTenant = Callable[[Config, str, str], Awaitable[str | None]]
TenantsDeUsuario = Callable[[Config, str], Awaitable[list[dict]]]
ConocimientoParaPanel = Callable[[Config, str], Awaitable[list[dict]]]
OperacionPanel = Callable[..., Awaitable[dict]]
CanalDeCuenta = Callable[..., Awaitable[CanalTenant]]
RegistrarMensajeEntrante = Callable[..., Awaitable[ResultadoIngreso]]

CATEGORIAS_CONOCIMIENTO = frozenset(
    {"horario", "precio", "servicio", "politica", "faq", "tono", "otro"}
)

# Los unicos entornos donde se puede pedir un tenant por el cuerpo. Se listan
# los que aflojan, no los que aprietan: asi un valor escrito distinto, en otro
# idioma o vacio se comporta como produccion. Falla cerrado a proposito — el
# .env local dice "development" y el de la VM podria decir "production", y
# comparar contra una sola palabra dejaba el agujero abierto.
ENTORNOS_DE_DESARROLLO = frozenset({"development", "desarrollo", "dev", "local", "test"})


def _cors(respuesta: web.StreamResponse) -> web.StreamResponse:
    respuesta.headers["Access-Control-Allow-Origin"] = ORIGENES_PERMITIDOS
    respuesta.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    respuesta.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return respuesta


def _token_bearer(peticion: web.Request) -> str:
    esquema, _, token = peticion.headers.get("Authorization", "").partition(" ")
    if esquema.lower() != "bearer" or not token.strip():
        return ""
    return token.strip()


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


async def _usuario_del_panel(peticion: web.Request) -> str | None:
    """Valida la sesion del panel. Nunca confia en datos del cuerpo."""
    token = _token_bearer(peticion)
    if not token:
        return None
    usuario_de_token: UsuarioDeToken = peticion.app["usuario_de_token"]
    try:
        return await usuario_de_token(peticion.app["config"], token)
    except Exception:
        logger.info("sesion invalida en API del panel")
        return None


async def _contexto_del_panel(
    peticion: web.Request, tenant_slug: str
) -> tuple[str | None, Tenant | None, str | None, web.Response | None]:
    """Exige sesion y membresia en el tenant pedido por la ruta."""
    usuario_id = await _usuario_del_panel(peticion)
    if not usuario_id:
        return None, None, None, _cors(
            web.json_response({"error": "Sesion requerida."}, status=401)
        )

    config: Config = peticion.app["config"]
    obtener_tenant: ObtenerTenant = peticion.app["obtener_tenant"]
    rol_de_usuario_en_tenant: RolDeUsuarioEnTenant = peticion.app[
        "rol_de_usuario_en_tenant"
    ]
    try:
        tenant = await obtener_tenant(config, tenant_slug)
    except repositorio.TenantNoEncontrado:
        return usuario_id, None, None, _cors(
            web.json_response({"error": "Negocio no encontrado."}, status=404)
        )
    except Exception:
        logger.exception("no se pudo resolver el tenant del panel")
        return usuario_id, None, None, _cors(
            web.json_response({"error": "No se pudo validar el negocio."}, status=503)
        )

    try:
        rol = await rol_de_usuario_en_tenant(config, usuario_id, tenant.id)
    except Exception:
        logger.exception("no se pudo validar la membresia del panel")
        return usuario_id, tenant, None, _cors(
            web.json_response({"error": "No se pudo validar el acceso."}, status=503)
        )
    if not rol:
        return usuario_id, tenant, None, _cors(
            web.json_response({"error": "No tienes acceso a este negocio."}, status=403)
        )
    return usuario_id, tenant, rol, None


async def listar_tenants_del_panel(peticion: web.Request) -> web.Response:
    usuario_id = await _usuario_del_panel(peticion)
    if not usuario_id:
        return _cors(web.json_response({"error": "Sesion requerida."}, status=401))
    try:
        funcion: TenantsDeUsuario = peticion.app["tenants_de_usuario"]
        tenants = await funcion(peticion.app["config"], usuario_id)
    except Exception:
        logger.exception("no se pudieron listar los negocios del panel")
        return _cors(
            web.json_response({"error": "No se pudieron cargar tus negocios."}, status=503)
        )
    return _cors(web.json_response({"tenants": tenants}))


async def listar_conocimiento_del_panel(peticion: web.Request) -> web.Response:
    usuario_id, tenant, rol, error = await _contexto_del_panel(
        peticion, peticion.match_info["tenant_slug"]
    )
    if error is not None:
        return error
    try:
        funcion: ConocimientoParaPanel = peticion.app["conocimiento_para_panel"]
        piezas = await funcion(peticion.app["config"], tenant.id)
    except Exception:
        logger.exception("no se pudo cargar el conocimiento del panel")
        return _cors(
            web.json_response({"error": "No se pudo cargar el entrenamiento."}, status=503)
        )
    return _cors(
        web.json_response(
            {"tenant": tenant.slug, "rol": rol, "conocimiento": piezas}
        )
    )


async def crear_borrador_del_panel(peticion: web.Request) -> web.Response:
    usuario_id, tenant, _, error = await _contexto_del_panel(
        peticion, peticion.match_info["tenant_slug"]
    )
    if error is not None:
        return error
    try:
        cuerpo = await peticion.json()
    except Exception:
        return _cors(web.json_response({"error": "JSON invalido."}, status=400))

    categoria = str(cuerpo.get("categoria") or "").strip()
    clave = str(cuerpo.get("clave") or "").strip()
    titulo = str(cuerpo.get("titulo") or "").strip()
    contenido = cuerpo.get("contenido")
    motivo = str(cuerpo.get("motivo") or "").strip()
    if categoria not in CATEGORIAS_CONOCIMIENTO:
        return _cors(web.json_response({"error": "Categoria invalida."}, status=400))
    if not clave or not titulo or len(clave) > 100 or len(titulo) > 200:
        return _cors(
            web.json_response({"error": "Clave y titulo son obligatorios."}, status=400)
        )
    if not isinstance(contenido, dict):
        return _cors(
            web.json_response({"error": "Contenido debe ser un objeto."}, status=400)
        )
    if len(motivo) > 500:
        return _cors(web.json_response({"error": "Motivo demasiado largo."}, status=400))

    try:
        funcion: OperacionPanel = peticion.app["crear_borrador_conocimiento"]
        resultado = await funcion(
            peticion.app["config"],
            tenant_id=tenant.id,
            categoria=categoria,
            clave=clave,
            titulo=titulo,
            contenido=contenido,
            usuario_id=usuario_id,
            motivo=motivo,
        )
    except Exception:
        logger.exception("no se pudo crear el borrador de conocimiento")
        return _cors(
            web.json_response({"error": "No se pudo guardar el borrador."}, status=503)
        )
    return _cors(web.json_response({"borrador": resultado}, status=201))


async def publicar_version_del_panel(peticion: web.Request) -> web.Response:
    usuario_id, tenant, _, error = await _contexto_del_panel(
        peticion, peticion.match_info["tenant_slug"]
    )
    if error is not None:
        return error
    try:
        cuerpo = await peticion.json()
    except Exception:
        cuerpo = {}
    motivo = str(cuerpo.get("motivo") or "").strip()
    if len(motivo) > 500:
        return _cors(web.json_response({"error": "Motivo demasiado largo."}, status=400))
    try:
        funcion: OperacionPanel = peticion.app["publicar_version_conocimiento"]
        resultado = await funcion(
            peticion.app["config"],
            tenant_id=tenant.id,
            version_id=peticion.match_info["version_id"],
            usuario_id=usuario_id,
            motivo=motivo,
        )
    except Exception:
        logger.exception("no se pudo publicar la version de conocimiento")
        return _cors(
            web.json_response({"error": "No se pudo publicar la version."}, status=503)
        )
    return _cors(web.json_response({"publicacion": resultado}))


async def emitir_token(peticion: web.Request) -> web.Response:
    config: Config = peticion.app["config"]
    limitador: Limitador = peticion.app["limitador"]
    obtener_tenant: ObtenerTenant = peticion.app["obtener_tenant"]
    tenant_de_dominio: TenantDeDominio = peticion.app["tenant_de_dominio"]
    usuario_de_token: UsuarioDeToken = peticion.app["usuario_de_token"]
    rol_de_usuario_en_tenant: RolDeUsuarioEnTenant = peticion.app[
        "rol_de_usuario_en_tenant"
    ]

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
    pedido = (cuerpo.get("tenant") or "").strip()
    try:
        registrado = await tenant_de_dominio(config, dominio)
        if registrado is not None:
            # Nuestros sitios de demos hospedan varios rubros en un mismo host
            # —ocho plantillas de barberia, ocho de gastronomia— y el Origin no
            # distingue la pagina. Solo esos pueden decir que agente quieren.
            # El dominio de un cliente real mapea a uno solo y no declara nada.
            tenant_slug = pedido if (registrado.puede_declarar and pedido) else registrado.tenant_slug
        elif config.entorno in ENTORNOS_DE_DESARROLLO:
            # Dominio sin registrar, fuera de produccion: se honra el cuerpo,
            # que es como se prueba el aislamiento a oido en local.
            tenant_slug = pedido or TENANT_POR_DEFECTO
        else:
            # Sin registrar y en produccion: nuestro propio agente, nunca el
            # de otro. Pedirlo por nombre no alcanza para llevarselo.
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

    # El modo interno nunca viene del cuerpo. Solo se concede cuando Supabase
    # valida el JWT y ese usuario pertenece al tenant que ya resolvio el
    # dominio. Cualquier error de auth falla cerrado sin tirar la landing.
    modo = "publico"
    token_sesion = _token_bearer(peticion)
    if token_sesion:
        try:
            usuario_id = await usuario_de_token(config, token_sesion)
            if usuario_id and await rol_de_usuario_en_tenant(
                config, usuario_id, tenant.id
            ):
                modo = "interno"
        except Exception:
            logger.info("sesion de panel invalida; se emite modo publico")

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
                    "modo": modo,
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
        "token emitido | nivel=%s motor=%s tenant=%s modo=%s voz=%s sala=%s",
        nivel.numero, nivel.motor, tenant.slug, modo, voz, sala,
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


async def verificar_webhook_whatsapp(pedido: web.Request) -> web.Response:
    """El GET que Meta hace una sola vez al dar de alta el webhook.

    Devuelve `hub.challenge` en texto plano si el token coincide. La
    comparacion es en tiempo constante y un token vacio no valida nunca: si
    `WHATSAPP_VERIFY_TOKEN` no esta configurado, un pedido con el parametro
    vacio se daria por bueno.
    """
    cfg: Config = pedido.app["config"]
    esperado = cfg.whatsapp_verify_token
    recibido = pedido.query.get("hub.verify_token", "")

    if not esperado or not secrets.compare_digest(recibido, esperado):
        logger.warning("whatsapp | verificacion rechazada")
        raise web.HTTPForbidden(text="verificacion rechazada")

    return web.Response(text=pedido.query.get("hub.challenge", ""))


async def recibir_webhook_whatsapp(pedido: web.Request) -> web.Response:
    """Valida la firma, resuelve el tenant por la cuenta receptora y persiste.

    Responde 200 apenas guarda. La respuesta del agente no se genera aca: si
    tardara, Meta reintentaria el mismo evento. El trabajo real queda en
    `eventos_inbox` y lo levanta el procesador.

    El unico 500 es cuando el mensaje es valido y lo perdimos por un problema
    nuestro: ahi el reintento de Meta es lo que queremos. Un payload que no
    entendemos o una cuenta que no es de nadie devuelven 200, porque un error
    haria que Meta lo reintente para siempre.
    """
    cfg: Config = pedido.app["config"]
    crudo = await pedido.read()

    if not firma_whatsapp.firma_valida(
        crudo, pedido.headers.get("X-Hub-Signature-256"), cfg.meta_app_secret
    ):
        logger.warning("whatsapp | firma invalida | %s bytes", len(crudo))
        raise web.HTTPForbidden(text="firma invalida")

    try:
        cuerpo = json.loads(crudo)
    except ValueError:
        logger.warning("whatsapp | cuerpo que no es json")
        return web.json_response({"recibido": True})

    canal_de_cuenta = pedido.app["canal_de_cuenta"]
    registrar = pedido.app["registrar_mensaje_entrante"]

    for entrada in payload_whatsapp.leer_webhook(cuerpo):
        try:
            canal = await canal_de_cuenta(
                cfg, canal="whatsapp", cuenta_externa_id=entrada.cuenta_externa_id
            )
        except repositorio.CanalNoEncontrado:
            # Un numero que no es de ningun tenant. No es un error nuestro y
            # no hay a quien contestarle: se registra y se sigue.
            logger.warning(
                "whatsapp | cuenta sin tenant | %s", entrada.cuenta_externa_id
            )
            continue

        for crudo_mensaje in entrada.mensajes:
            resultado = await registrar(
                cfg,
                tenant_canal_id=canal.id,
                mensaje=crudo_mensaje.con_tenant(canal.tenant_id),
            )
            logger.info(
                "whatsapp | entrante | tenant=%s duplicado=%s",
                canal.tenant_id,
                resultado.duplicado,
            )

    return web.json_response({"recibido": True})


def crear_app(
    config: Config | None = None,
    obtener_tenant: ObtenerTenant | None = None,
    tenant_de_dominio: TenantDeDominio | None = None,
    usuario_de_token: UsuarioDeToken | None = None,
    rol_de_usuario_en_tenant: RolDeUsuarioEnTenant | None = None,
    tenants_de_usuario: TenantsDeUsuario | None = None,
    conocimiento_para_panel: ConocimientoParaPanel | None = None,
    crear_borrador_conocimiento: OperacionPanel | None = None,
    publicar_version_conocimiento: OperacionPanel | None = None,
    canal_de_cuenta: CanalDeCuenta | None = None,
    registrar_mensaje_entrante: RegistrarMensajeEntrante | None = None,
) -> web.Application:
    cfg = config or cargar()

    # Desde las Fases 5-8 no hay token sin resolver el tenant, y eso es una
    # consulta a Supabase. Sin credenciales el servicio arrancaba igual y
    # devolvia 503 en cada pedido: la demo entera caida y en silencio. Mejor
    # no arrancar. Solo aplica cuando se usa el repositorio real; los tests
    # inyectan los suyos y no necesitan base.
    if obtener_tenant is None and not (cfg.supabase_url and cfg.supabase_service_role_key):
        raise ConfigInvalida(
            "La API necesita SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY (o "
            "SUPABASE_SECRET_KEY) para resolver el tenant de cada sesion. "
            "Sin eso, POST /api/token devuelve 503 siempre."
        )

    app = web.Application()
    app["config"] = cfg
    app["obtener_tenant"] = obtener_tenant or repositorio.obtener_tenant
    app["tenant_de_dominio"] = tenant_de_dominio or repositorio.tenant_de_dominio
    app["usuario_de_token"] = usuario_de_token or repositorio.usuario_de_token
    app["rol_de_usuario_en_tenant"] = (
        rol_de_usuario_en_tenant or repositorio.rol_de_usuario_en_tenant
    )
    app["tenants_de_usuario"] = tenants_de_usuario or repositorio.tenants_de_usuario
    app["conocimiento_para_panel"] = (
        conocimiento_para_panel or repositorio.conocimiento_para_panel
    )
    app["crear_borrador_conocimiento"] = (
        crear_borrador_conocimiento or repositorio.crear_borrador_conocimiento
    )
    app["publicar_version_conocimiento"] = (
        publicar_version_conocimiento or repositorio.publicar_version_conocimiento
    )
    app["canal_de_cuenta"] = canal_de_cuenta or repositorio.canal_de_cuenta
    app["registrar_mensaje_entrante"] = (
        registrar_mensaje_entrante or repositorio.registrar_mensaje_entrante
    )
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
            web.get("/api/panel/tenants", listar_tenants_del_panel),
            web.get(
                "/api/panel/{tenant_slug}/conocimiento",
                listar_conocimiento_del_panel,
            ),
            web.post(
                "/api/panel/{tenant_slug}/conocimiento/borradores",
                crear_borrador_del_panel,
            ),
            web.post(
                "/api/panel/{tenant_slug}/conocimiento/{version_id}/publicar",
                publicar_version_del_panel,
            ),
            # Fuera de /api/ a proposito: no lo llama un navegador, no lleva
            # CORS y no comparte los limites por IP con la demo.
            web.get("/webhooks/whatsapp", verificar_webhook_whatsapp),
            web.post("/webhooks/whatsapp", recibir_webhook_whatsapp),
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
