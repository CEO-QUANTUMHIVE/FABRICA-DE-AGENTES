"""Alta oficial de un numero mediante WhatsApp Embedded Signup.

El navegador recibe solo el codigo temporal de Facebook Login for Business.
Este modulo lo canjea del lado servidor, descubre el numero que pertenece al
WABA autorizado, lo registra y suscribe nuestra app a sus webhooks. Nunca
devuelve el access token a una respuesta HTTP ni lo escribe en logs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import aiohttp

from motor_voz.config import Config

URL_BASE = "https://graph.facebook.com"
ID_META = re.compile(r"^[0-9]{6,30}$")

Pedir = Callable[..., Awaitable[tuple[int, dict[str, Any]]]]


class OnboardingNoConfigurado(RuntimeError):
    """Faltan datos de la app Meta en el servidor."""


class OnboardingInvalido(ValueError):
    """La sesión de Embedded Signup no contiene activos validos."""


class MetaRechazo(RuntimeError):
    """Meta rechazo una operación del alta."""


@dataclass(frozen=True)
class ConexionAutorizada:
    waba_id: str
    phone_number_id: str
    numero: str
    nombre: str
    access_token: str = field(repr=False)


def configuracion_publica(config: Config) -> dict[str, Any]:
    """Datos que el SDK oficial necesita y que no son secretos."""
    listo = bool(
        config.meta_app_id
        and config.meta_app_secret
        and config.meta_embedded_signup_config_id
        and config.whatsapp_verify_token
        and re.fullmatch(r"[0-9]{6}", config.whatsapp_registration_pin)
    )
    return {
        "disponible": listo,
        "app_id": config.meta_app_id,
        "configuration_id": config.meta_embedded_signup_config_id,
        "api_version": config.whatsapp_api_version,
        "feature_type": "whatsapp_business_app_onboarding",
    }


async def completar(
    config: Config,
    *,
    code: str,
    waba_id: str,
    phone_number_id: str = "",
    pedir: Pedir | None = None,
) -> ConexionAutorizada:
    """Canjea el código temporal y deja el numero operativo en Cloud API."""
    if not configuracion_publica(config)["disponible"]:
        raise OnboardingNoConfigurado(
            "la app Meta, el webhook, el PIN o el almacén todavía no están configurados"
        )
    if not code.strip():
        raise OnboardingInvalido("Meta no devolvió el código temporal")
    if not ID_META.fullmatch(waba_id.strip()):
        raise OnboardingInvalido("Meta no devolvió un WABA válido")
    if phone_number_id and not ID_META.fullmatch(phone_number_id.strip()):
        raise OnboardingInvalido("Meta no devolvió un número válido")

    llamar = pedir or _pedir
    token = await _canjear_codigo(config, code.strip(), llamar)
    numeros = await _listar_numeros(config, waba_id.strip(), token, llamar)
    numero = _elegir_numero(numeros, phone_number_id.strip())

    await _operacion_meta(
        llamar,
        "POST",
        f"{URL_BASE}/{config.whatsapp_api_version}/{numero['id']}/register",
        token,
        json={
            "messaging_product": "whatsapp",
            "pin": config.whatsapp_registration_pin,
        },
        accion="registrar el número",
    )
    await _operacion_meta(
        llamar,
        "POST",
        f"{URL_BASE}/{config.whatsapp_api_version}/{waba_id}/subscribed_apps",
        token,
        json={},
        accion="suscribir el webhook",
    )

    return ConexionAutorizada(
        waba_id=waba_id,
        phone_number_id=str(numero["id"]),
        numero=str(numero.get("display_phone_number") or ""),
        nombre=str(numero.get("verified_name") or "WhatsApp principal")[:100],
        access_token=token,
    )


async def _canjear_codigo(config: Config, code: str, pedir: Pedir) -> str:
    estado, cuerpo = await pedir(
        "GET",
        f"{URL_BASE}/{config.whatsapp_api_version}/oauth/access_token",
        params={
            "client_id": config.meta_app_id,
            "client_secret": config.meta_app_secret,
            "redirect_uri": "",
            "code": code,
        },
    )
    token = str(cuerpo.get("access_token") or "").strip()
    if estado != 200 or not token:
        raise MetaRechazo(_mensaje_seguro(cuerpo, "Meta rechazó la autorización"))
    return token


async def _listar_numeros(
    config: Config, waba_id: str, token: str, pedir: Pedir
) -> list[dict[str, Any]]:
    cuerpo = await _operacion_meta(
        pedir,
        "GET",
        f"{URL_BASE}/{config.whatsapp_api_version}/{waba_id}/phone_numbers",
        token,
        params={"fields": "id,display_phone_number,verified_name"},
        accion="consultar los números autorizados",
    )
    numeros = cuerpo.get("data") or []
    if not isinstance(numeros, list) or not numeros:
        raise OnboardingInvalido("el WABA autorizado no contiene ningún número")
    return [fila for fila in numeros if isinstance(fila, dict) and fila.get("id")]


def _elegir_numero(
    numeros: list[dict[str, Any]], phone_number_id: str
) -> dict[str, Any]:
    if phone_number_id:
        for numero in numeros:
            if str(numero.get("id")) == phone_number_id:
                return numero
        raise OnboardingInvalido("el número no pertenece al WABA autorizado")
    if len(numeros) != 1:
        raise OnboardingInvalido(
            "Meta autorizó más de un número y no indicó cuál fue seleccionado"
        )
    return numeros[0]


async def _operacion_meta(
    pedir: Pedir,
    metodo: str,
    url: str,
    token: str,
    *,
    accion: str,
    **opciones: Any,
) -> dict[str, Any]:
    estado, cuerpo = await pedir(
        metodo,
        url,
        headers={"Authorization": f"Bearer {token}"},
        **opciones,
    )
    if estado < 200 or estado >= 300 or cuerpo.get("error"):
        raise MetaRechazo(_mensaje_seguro(cuerpo, f"Meta no pudo {accion}"))
    return cuerpo


def _mensaje_seguro(cuerpo: dict[str, Any], predeterminado: str) -> str:
    error = cuerpo.get("error") if isinstance(cuerpo, dict) else None
    codigo = error.get("code") if isinstance(error, dict) else None
    return f"{predeterminado} (código {codigo})" if codigo else predeterminado


async def _pedir(
    metodo: str, url: str, **opciones: Any
) -> tuple[int, dict[str, Any]]:
    tiempo = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=tiempo) as sesion:
        async with sesion.request(metodo, url, **opciones) as respuesta:
            try:
                cuerpo = await respuesta.json()
            except Exception:  # noqa: BLE001
                cuerpo = {}
            return respuesta.status, cuerpo
