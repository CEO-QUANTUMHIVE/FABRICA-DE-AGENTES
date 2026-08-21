"""Rutas HTTP privadas del CEO departamental para QuantumCore."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from typing import Any

from aiohttp import web

from motor_voz.brain.tenants import repositorio
from motor_voz.brain.tenants.modelos import Tenant
from motor_voz.ceo.departamento import (
    CEODeFabricaDeAgentes,
    RegistroWorkers,
    consultar_ceo,
    describir_ceo,
    solicitud_sin_codigo_dinamico,
)
from motor_voz.config import Config

TAMANO_MAXIMO_SOLICITUD = 1_000_000
HEADER_SESION_ACTOR = "X-QuantumCore-Actor-Token"


def _bearer(peticion: web.Request) -> str:
    esquema, _, token = peticion.headers.get("Authorization", "").partition(" ")
    if esquema.lower() != "bearer":
        return ""
    return token.strip()


def _autenticado(peticion: web.Request) -> bool:
    esperado = peticion.app["config"].quantumcore_token
    recibido = _bearer(peticion)
    return bool(esperado and recibido and secrets.compare_digest(esperado, recibido))


def _error(codigo: str, mensaje: str, status: int) -> web.Response:
    return web.json_response(
        {"estado": "rechazado", "error": {"codigo": codigo, "mensaje": mensaje}},
        status=status,
    )


async def _json_estructurado(
    peticion: web.Request, *, validar_dinamico: bool = True
) -> tuple[dict[str, Any] | None, web.Response | None]:
    if peticion.content_length and peticion.content_length > TAMANO_MAXIMO_SOLICITUD:
        return None, _error("solicitud_demasiado_grande", "Solicitud excedida.", 413)
    try:
        cuerpo = await peticion.json()
    except Exception:
        return None, _error("json_invalido", "Se esperaba un objeto JSON.", 400)
    if not isinstance(cuerpo, dict):
        return None, _error("contrato_invalido", "Se esperaba un objeto JSON.", 400)
    if validar_dinamico and not solicitud_sin_codigo_dinamico(cuerpo):
        return None, _error(
            "codigo_dinamico_prohibido", "No se aceptan comandos ni codigo dinamico.", 422
        )
    return cuerpo, None


async def _tenant_autorizado(
    peticion: web.Request, slug: str
) -> tuple[str | None, Tenant | None, web.Response | None]:
    token_actor = peticion.headers.get(HEADER_SESION_ACTOR, "").strip()
    if not token_actor:
        return None, None, _error(
            "identidad_requerida",
            f"Falta la sesion del actor en {HEADER_SESION_ACTOR}.",
            401,
        )
    config: Config = peticion.app["config"]
    try:
        usuario = await peticion.app["usuario_de_token"](config, token_actor)
    except Exception:
        usuario = None
    if not usuario:
        return None, None, _error("identidad_invalida", "Sesion del actor invalida.", 401)
    try:
        tenant = await peticion.app["obtener_tenant"](config, slug)
    except repositorio.TenantNoEncontrado:
        return usuario, None, _error(
            "tenant_inactivo_o_desconocido", "Tenant no disponible.", 404
        )
    except Exception:
        return usuario, None, _error(
            "tenant_no_verificable", "No se pudo verificar el tenant.", 503
        )
    try:
        rol = await peticion.app["rol_de_usuario_en_tenant"](config, usuario, tenant.id)
    except Exception:
        return usuario, tenant, _error(
            "membresia_no_verificable", "No se pudo verificar la membresia.", 503
        )
    if not rol:
        return usuario, tenant, _error(
            "tenant_no_autorizado", "El actor no pertenece al tenant solicitado.", 403
        )
    return usuario, tenant, None


def _estado_dependencias(config: Config, registro: RegistroWorkers) -> dict[str, bool]:
    return {
        "autenticacion_quantumcore": bool(config.quantumcore_token),
        "supabase": bool(config.supabase_url and config.supabase_service_role_key),
        "livekit": bool(
            config.livekit_url and config.livekit_api_key and config.livekit_api_secret
        ),
        "groq": bool(config.groq_api_key),
        "fish": bool(config.fish_api_key),
        "gemini": bool(config.google_api_key or config.gcp_project),
        "openai_realtime": bool(config.openai_api_key or config.azure_api_key),
        "algun_worker_conectado": bool(registro.disponibles()),
    }


def _configuracion_publica(config: Config) -> dict[str, bool]:
    return {
        "QUANTUMCORE_TOKEN_configurado": bool(config.quantumcore_token),
        "SUPABASE_configurado": bool(config.supabase_url and config.supabase_service_role_key),
        "LIVEKIT_configurado": bool(
            config.livekit_url and config.livekit_api_key and config.livekit_api_secret
        ),
        "META_WEBHOOK_configurado": bool(
            config.meta_app_secret and config.whatsapp_verify_token
        ),
        "RESPUESTAS_AUTOMATICAS": bool(config.respuestas_automaticas),
    }


async def descripcion_ceo(peticion: web.Request) -> web.Response:
    if not _autenticado(peticion):
        return _error("autenticacion_requerida", "Credencial de QuantumCore invalida.", 401)
    registro: RegistroWorkers = peticion.app["registro_workers_ceo"]
    return web.json_response(
        describir_ceo(
            dependencias=_estado_dependencias(peticion.app["config"], registro),
            workers_disponibles=registro.disponibles(),
        )
    )


async def consulta_ceo(peticion: web.Request) -> web.Response:
    if not _autenticado(peticion):
        return _error("autenticacion_requerida", "Credencial de QuantumCore invalida.", 401)
    cuerpo, respuesta = await _json_estructurado(peticion)
    if respuesta or cuerpo is None:
        return respuesta
    if not set(cuerpo).issubset({"tipo", "tenant", "correlacion_id"}):
        return _error("contrato_invalido", "La consulta contiene campos no permitidos.", 422)
    tipo = cuerpo.get("tipo")
    if not isinstance(tipo, str):
        return _error("tipo_consulta_invalido", "Falta el tipo de consulta.", 422)
    correlacion_id = cuerpo.get("correlacion_id")
    if correlacion_id is not None and (
        not isinstance(correlacion_id, str) or not correlacion_id.strip() or len(correlacion_id) > 500
    ):
        return _error("correlacion_invalida", "Correlación inválida.", 422)

    tenant_datos: Mapping[str, Any] | None = None
    slug = cuerpo.get("tenant")
    if tipo == "tenant" and not slug:
        return _error("tenant_requerido", "La consulta requiere tenant.", 422)
    if slug:
        if not isinstance(slug, str):
            return _error("tenant_invalido", "Tenant invalido.", 422)
        _, tenant, rechazo = await _tenant_autorizado(peticion, slug)
        if rechazo or tenant is None:
            return rechazo
        tenant_datos = {
            "id": tenant.id,
            "slug": tenant.slug,
            "nombre": tenant.nombre,
            "idioma": tenant.idioma,
        }
    try:
        resultado = consultar_ceo(
            tipo,
            tenant=tenant_datos,
            configuracion_publica=_configuracion_publica(peticion.app["config"]),
        )
    except ValueError as error:
        return _error(str(error), "Consulta no permitida por el contrato.", 422)
    if correlacion_id is not None:
        resultado["correlacion_id"] = correlacion_id
    return web.json_response(resultado)


async def accion_ceo(peticion: web.Request) -> web.Response:
    if not _autenticado(peticion):
        return _error("autenticacion_requerida", "Credencial de QuantumCore invalida.", 401)
    cuerpo, respuesta = await _json_estructurado(peticion, validar_dinamico=False)
    if respuesta or cuerpo is None:
        return respuesta

    solicitud = dict(cuerpo)
    slug = solicitud.get("tenant")
    if slug:
        if not isinstance(slug, str):
            return _error("tenant_invalido", "Tenant invalido.", 422)
        usuario, tenant, rechazo = await _tenant_autorizado(peticion, slug)
        if rechazo or tenant is None or usuario is None:
            return rechazo
        auditoria = dict(solicitud.get("auditoria") or {})
        auditoria["solicitado_por"] = usuario
        auditoria["tenant_id"] = tenant.id
        solicitud["auditoria"] = auditoria
        solicitud["tenant"] = tenant.slug

    servicio: CEODeFabricaDeAgentes = peticion.app["ceo_fabrica_de_agentes"]
    resultado = await servicio.accionar(solicitud)
    status = 200
    if resultado["estado"] == "rechazado":
        status = 422
    elif resultado["estado"] == "error":
        status = 500
    return web.json_response(resultado, status=status)


def preparar_ceo(app: web.Application, registro: RegistroWorkers | None = None) -> None:
    registro_real = registro or RegistroWorkers()
    config: Config = app["config"]
    secretos_configurados = (
        config.quantumcore_token,
        config.groq_api_key,
        config.fish_api_key,
        config.livekit_api_key,
        config.livekit_api_secret,
        config.google_api_key,
        config.openai_api_key,
        config.azure_api_key,
        config.supabase_service_role_key,
        config.meta_app_secret,
        config.whatsapp_verify_token,
    )
    app["registro_workers_ceo"] = registro_real
    app["ceo_fabrica_de_agentes"] = CEODeFabricaDeAgentes(
        registro_real, secretos=secretos_configurados
    )


def rutas_ceo() -> list[web.RouteDef]:
    return [
        web.get("/v1/departamentos/fabrica-de-agentes/descripcion", descripcion_ceo),
        web.post("/v1/consultas", consulta_ceo),
        web.post("/v1/acciones", accion_ceo),
    ]
