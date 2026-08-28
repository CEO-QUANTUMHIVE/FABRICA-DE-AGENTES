"""De donde sale el access token de cada canal conectado.

`tenant_canales.secreto_ref` guarda una REFERENCIA, nunca el token. Ese
comment esta en la migracion y es deliberado: la tabla la lee el panel, se
copia a entornos de prueba y aparece en cualquier dump. Un token de WhatsApp
ahi dentro es un token filtrado.

La referencia primero se resuelve contra variables de entorno del worker:

    secreto_ref = "whatsapp_quantumhive"  ->  SECRETO_WHATSAPP_QUANTUMHIVE

Para Embedded Signup, el token se guarda en una carpeta privada y persistente
de nuestra VM (`WHATSAPP_SECRET_DIR`). Asi no depende de un proveedor externo,
no entra en la base y el resto del motor sigue viendo solo `secreto_ref`.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

PREFIJO = "SECRETO_"
VARIABLE_DIRECTORIO = "WHATSAPP_SECRET_DIR"
_NO_ALFANUMERICO = re.compile(r"[^A-Za-z0-9]+")


class SecretoNoEncontrado(RuntimeError):
    """La referencia no resuelve a ningun secreto configurado."""


class AlmacenNoConfigurado(RuntimeError):
    """No hay una carpeta privada configurada para guardar tokens nuevos."""


def almacen_configurado(entorno: dict[str, str] | None = None) -> bool:
    e = os.environ if entorno is None else entorno
    return bool((e.get(VARIABLE_DIRECTORIO) or "").strip())


def nombre_de_variable(secreto_ref: str) -> str:
    """La variable de entorno que corresponde a una referencia."""
    limpio = _NO_ALFANUMERICO.sub("_", secreto_ref.strip()).strip("_")
    return f"{PREFIJO}{limpio.upper()}"


def _ruta_del_secreto(secreto_ref: str, entorno: dict[str, str]) -> Path:
    directorio = (entorno.get(VARIABLE_DIRECTORIO) or "").strip()
    if not directorio:
        raise AlmacenNoConfigurado(
            f"falta {VARIABLE_DIRECTORIO}; configure una carpeta privada persistente"
        )
    nombre = nombre_de_variable(secreto_ref).lower() + ".token"
    return Path(directorio).expanduser().resolve() / nombre


def guardar(
    secreto_ref: str,
    token: str,
    entorno: dict[str, str] | None = None,
) -> None:
    """Guarda un token de manera atomica y con permisos solo para el worker."""
    if not secreto_ref or not secreto_ref.strip():
        raise ValueError("secreto_ref no puede estar vacio")
    if not token or not token.strip():
        raise ValueError("el token no puede estar vacio")

    e = dict(os.environ) if entorno is None else entorno
    destino = _ruta_del_secreto(secreto_ref, e)
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(destino.parent, 0o700)
    except OSError:
        logger.debug("el sistema no permite ajustar permisos del almacen")

    descriptor, temporal = tempfile.mkstemp(
        dir=destino.parent,
        prefix=f".{destino.name}.",
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            archivo.write(token.strip())
        try:
            os.chmod(temporal, 0o600)
        except OSError:
            logger.debug("el sistema no permite ajustar permisos del secreto")
        os.replace(temporal, destino)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)


def resolver(secreto_ref: str | None, entorno: dict[str, str] | None = None) -> str:
    """El token de un canal. Levanta si no esta, en vez de devolver vacio.

    Un string vacio se veria como "canal sin credencial" y terminaria
    descartando mensajes en silencio. Que falte el secreto es un problema de
    configuracion y tiene que sonar como tal.
    """
    e = os.environ if entorno is None else entorno
    if not secreto_ref or not secreto_ref.strip():
        raise SecretoNoEncontrado("el canal no tiene secreto_ref cargado")

    variable = nombre_de_variable(secreto_ref)
    valor = (e.get(variable) or "").strip()
    if valor:
        return valor

    try:
        ruta = _ruta_del_secreto(secreto_ref, e)
    except AlmacenNoConfigurado:
        ruta = None
    if ruta and ruta.is_file():
        valor = ruta.read_text(encoding="utf-8").strip()
        if valor:
            return valor

    raise SecretoNoEncontrado(
        f"no hay credencial configurada para el secreto '{secreto_ref}'"
    )
