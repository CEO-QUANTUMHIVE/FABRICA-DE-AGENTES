"""De donde sale el access token de cada canal conectado.

`tenant_canales.secreto_ref` guarda una REFERENCIA, nunca el token. Ese
comment esta en la migracion y es deliberado: la tabla la lee el panel, se
copia a entornos de prueba y aparece en cualquier dump. Un token de WhatsApp
ahi dentro es un token filtrado.

Hoy la referencia se resuelve contra variables de entorno del worker:

    secreto_ref = "whatsapp_quantumhive"  ->  SECRETO_WHATSAPP_QUANTUMHIVE

Alcanza mientras los canales los damos de alta nosotros y corren en una VM.
Cuando entre Embedded Signup y los tokens los emita cada cliente, esto pasa a
Secret Manager: cambia este modulo y nada mas, porque nadie fuera de aca sabe
como se guarda un secreto.
"""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)

PREFIJO = "SECRETO_"
_NO_ALFANUMERICO = re.compile(r"[^A-Za-z0-9]+")


class SecretoNoEncontrado(RuntimeError):
    """La referencia no resuelve a ningun secreto configurado."""


def nombre_de_variable(secreto_ref: str) -> str:
    """La variable de entorno que corresponde a una referencia."""
    limpio = _NO_ALFANUMERICO.sub("_", secreto_ref.strip()).strip("_")
    return f"{PREFIJO}{limpio.upper()}"


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
    if not valor:
        raise SecretoNoEncontrado(
            f"falta la variable {variable} para el secreto '{secreto_ref}'"
        )
    return valor
