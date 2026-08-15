"""Validacion de `X-Hub-Signature-256`.

Meta firma el cuerpo del webhook con el App Secret. Dos detalles que
convierten esto en seguridad de verdad o en decoracion:

- Se firma el **cuerpo crudo**, byte por byte. Si se parsea el JSON y se
  vuelve a serializar antes de comparar, la firma no cierra nunca (cambia un
  espacio, el orden de las claves o el escape de un acento).
- Se compara en tiempo constante. Un `==` sobre el digest filtra, medida a
  medida, cuanto prefijo acerto quien esta probando.
"""

from __future__ import annotations

import hashlib
import hmac

PREFIJO = "sha256="


def firma_valida(cuerpo: bytes, cabecera: str | None, secreto: str) -> bool:
    """True solo si la cabecera es el HMAC-SHA256 del cuerpo con ese secreto."""
    # Sin secreto no hay nada que validar, y aceptar seria dejar el webhook
    # abierto al mundo sin que se note. Falla cerrado.
    if not secreto or not secreto.strip():
        return False
    if not cabecera or not cabecera.startswith(PREFIJO):
        return False

    recibido = cabecera[len(PREFIJO) :]
    esperado = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(recibido, esperado)
