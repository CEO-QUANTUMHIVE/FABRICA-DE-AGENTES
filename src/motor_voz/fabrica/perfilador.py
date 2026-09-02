"""Cliente server-to-server del Perfilador de Clientes.

El token del Centro de Inteligencia Comercial vive solamente en el backend.
El navegador llama a nuestra API y recibe un paquete acotado, sin credenciales
ni campos arbitrarios del servicio remoto.
"""

from __future__ import annotations

import re
from ipaddress import ip_address
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import aiohttp

from motor_voz.config import Config

Pedir = Callable[..., Awaitable[tuple[int, dict[str, Any]]]]
COLOR_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class PerfiladorNoConfigurado(RuntimeError):
    """La Fábrica todavía no tiene URL y token del servicio."""


class PerfiladorInvalido(ValueError):
    """El pedido o la respuesta no cumplen el contrato público."""


class PerfiladorNoDisponible(RuntimeError):
    """El servicio remoto rechazó o no pudo completar la investigación."""


def configuracion_publica(config: Config) -> dict[str, bool]:
    """Solo expone si el módulo está listo; nunca la URL ni el token."""
    return {
        "disponible": bool(
            _url_http(config.centro_inteligencia_url)
            and config.centro_inteligencia_token
        )
    }


async def investigar(
    config: Config,
    *,
    nombre: str,
    web: str = "",
    instagram: str = "",
    facebook: str = "",
    url_maps: str = "",
    pedir: Pedir | None = None,
) -> dict[str, Any]:
    """Investiga un negocio sin entregar la credencial al navegador."""
    base = _url_http(config.centro_inteligencia_url)
    if not base or not config.centro_inteligencia_token:
        raise PerfiladorNoConfigurado(
            "el Perfilador de Clientes todavía no está conectado al servidor"
        )

    nombre_limpio = _texto(nombre, 200)
    if not nombre_limpio:
        raise PerfiladorInvalido("el nombre del negocio es obligatorio")

    cuerpo = {
        "nombre": nombre_limpio,
        "web": _fuente(web),
        "instagram": _fuente(instagram, admite_usuario=True),
        "facebook": _fuente(
            facebook,
            admite_usuario=True,
            base_usuario="https://www.facebook.com",
        ),
        "url_maps": _fuente(url_maps),
    }
    estado, respuesta = await (pedir or _pedir)(
        "POST",
        f"{base.rstrip('/')}/clientes/investigar",
        headers={
            "Authorization": f"Bearer {config.centro_inteligencia_token}",
            "Content-Type": "application/json",
        },
        json=cuerpo,
    )
    if estado == 401:
        raise PerfiladorNoDisponible("el Perfilador rechazó la credencial interna")
    if estado < 200 or estado >= 300:
        raise PerfiladorNoDisponible(
            f"el Perfilador no pudo investigar el negocio (HTTP {estado})"
        )
    return normalizar_paquete(respuesta)


def normalizar_paquete(valor: object) -> dict[str, Any]:
    """Aplica allowlists y límites a todo lo que vuelve del scraper/LLM."""
    if not isinstance(valor, dict) or not isinstance(valor.get("negocio"), dict):
        raise PerfiladorInvalido("el Perfilador devolvió una respuesta inválida")
    negocio_crudo = valor["negocio"]
    marca_cruda = valor.get("marca") if isinstance(valor.get("marca"), dict) else {}

    negocio = {
        clave: _texto(negocio_crudo.get(clave), limite)
        for clave, limite in {
            "nombre": 200,
            "categoria": 200,
            "direccion": 500,
            "ciudad": 200,
            "telefono": 100,
            "whatsapp": 100,
            "email": 320,
            "web": 1000,
            "instagram": 1000,
            "facebook": 1000,
            "url_maps": 1000,
            "texto_web": 6000,
            "logo_url": 1000,
        }.items()
    }
    negocio["tecnologias"] = _lista_textos(negocio_crudo.get("tecnologias"), 20, 100)
    for clave in (
        "puntuacion_google",
        "cantidad_resenas",
        "web_funciona",
        "web_es_vieja",
        "web_es_plataforma",
        "tiene_chatbot",
        "tiene_reservas_online",
    ):
        dato = negocio_crudo.get(clave)
        if isinstance(dato, (bool, int, float)):
            negocio[clave] = dato

    logo_url = _url_publica(marca_cruda.get("logo_url")) or _url_publica(
        negocio.get("logo_url")
    )
    logo_generico = _es_logo_generico_de_red(logo_url)
    if logo_generico:
        logo_url = ""
    colores = [
        color.lower()
        for color in _lista_textos(marca_cruda.get("colores"), 4, 7)
        if COLOR_HEX.fullmatch(color)
    ] if not logo_generico else []
    marca = {
        "logo_url": logo_url,
        "colores": colores,
        "bio_instagram": _texto(marca_cruda.get("bio_instagram"), 1000),
        "descripcion_facebook": _texto(
            marca_cruda.get("descripcion_facebook"), 2000
        ),
        "tecnologias": _lista_textos(marca_cruda.get("tecnologias"), 20, 100),
    }
    seguidores = marca_cruda.get("seguidores")
    if isinstance(seguidores, int) and seguidores >= 0:
        marca["seguidores"] = seguidores

    return {
        "negocio": negocio,
        "servicios": _lista_textos(valor.get("servicios"), 50, 500),
        "precios": _lista_textos(valor.get("precios"), 50, 500),
        "horarios": _texto(valor.get("horarios"), 2000),
        "preguntas_frecuentes": _preguntas(valor.get("preguntas_frecuentes")),
        "marca": marca,
        "competidores": _lista_textos(valor.get("competidores"), 30, 300),
    }


def _texto(valor: object, limite: int) -> str | None:
    texto = str(valor or "").strip()
    return texto[:limite] if texto else None


def _lista_textos(valor: object, cantidad: int, largo: int) -> list[str]:
    if not isinstance(valor, list):
        return []
    salida: list[str] = []
    for elemento in valor[:cantidad]:
        texto = _texto(elemento, largo)
        if texto:
            salida.append(texto)
    return salida


def _preguntas(valor: object) -> list[dict[str, str]]:
    if not isinstance(valor, list):
        return []
    salida = []
    for elemento in valor[:50]:
        if not isinstance(elemento, dict):
            continue
        pregunta = _texto(elemento.get("pregunta"), 500)
        respuesta = _texto(elemento.get("respuesta"), 1500)
        if pregunta and respuesta:
            salida.append({"pregunta": pregunta, "respuesta": respuesta})
    return salida


def _url_http(valor: object) -> str:
    texto = str(valor or "").strip()[:1000]
    if not texto:
        return ""
    parsed = urlparse(texto)
    return texto if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _fuente(
    valor: object,
    *,
    admite_usuario: bool = False,
    base_usuario: str = "",
) -> str | None:
    texto = str(valor or "").strip()[:1000]
    if not texto:
        return None
    if admite_usuario:
        usuario = texto.lstrip("@")
        if re.fullmatch(r"[A-Za-z0-9._]{1,100}", usuario):
            if base_usuario:
                return f"{base_usuario.rstrip('/')}/{usuario}"
            return f"@{usuario}"
    if "://" not in texto and "." in texto:
        texto = f"https://{texto}"
    if not _url_publica(texto):
        raise PerfiladorInvalido("las fuentes deben ser URLs públicas válidas")
    return texto


def _url_publica(valor: object) -> str:
    texto = _url_http(valor)
    if not texto:
        return ""
    parsed = urlparse(texto)
    host = (parsed.hostname or "").lower()
    if not host or parsed.username or parsed.password:
        return ""
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return ""
    try:
        ip = ip_address(host)
    except ValueError:
        return texto
    if any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        )
    ):
        return ""
    return texto


def _es_logo_generico_de_red(valor: str) -> bool:
    """Descarta recursos de interfaz de Meta que no son la marca del negocio."""
    if not valor:
        return False
    parsed = urlparse(valor)
    host = (parsed.hostname or "").lower()
    return host == "static.cdninstagram.com" or (
        host.endswith(".cdninstagram.com") and parsed.path.startswith("/rsrc.php")
    )


async def _pedir(
    metodo: str, url: str, **opciones: Any
) -> tuple[int, dict[str, Any]]:
    tiempo = aiohttp.ClientTimeout(total=65)
    async with aiohttp.ClientSession(timeout=tiempo) as sesion:
        for intento in range(2):
            try:
                async with sesion.request(metodo, url, **opciones) as respuesta:
                    try:
                        cuerpo = await respuesta.json()
                    except Exception:  # noqa: BLE001
                        cuerpo = {}
                    if respuesta.status >= 500 and intento == 0:
                        continue
                    return respuesta.status, cuerpo
            except (TimeoutError, aiohttp.ClientError) as exc:
                if intento == 0:
                    continue
                if isinstance(exc, TimeoutError):
                    raise PerfiladorNoDisponible(
                        "el Perfilador superó el tiempo de espera"
                    ) from exc
                raise PerfiladorNoDisponible(
                    "no se pudo conectar con el Perfilador"
                ) from exc
    raise PerfiladorNoDisponible("no se pudo conectar con el Perfilador")
