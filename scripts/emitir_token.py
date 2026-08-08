"""Emite un token de acceso a una sala de LiveKit.

En produccion esto vive en un endpoint del backend que ademas valida el
tenant y aplica los limites. Para desarrollo alcanza con este script.

Uso:
    uv run python scripts/emitir_token.py sala-demo visitante

NO renombrar este archivo a `token.py`. Al correrlo, Python pone `scripts/`
al principio de sys.path, y un `token.py` ahi le hace sombra al modulo
`token` de la stdlib que importa `tokenize`. El sintoma es un error de
import circular en `logging` que no tiene nada que ver con la causa real.
"""

from __future__ import annotations

import sys

from livekit import api

from motor_voz.config import cargar


def emitir(sala: str, identidad: str) -> str:
    config = cargar()
    concesion = api.VideoGrants(room_join=True, room=sala, can_publish=True, can_subscribe=True)
    token = (
        api.AccessToken(config.livekit_api_key, config.livekit_api_secret)
        .with_identity(identidad)
        .with_name(identidad)
        .with_grants(concesion)
    )
    return token.to_jwt()


if __name__ == "__main__":
    sala = sys.argv[1] if len(sys.argv) > 1 else "sala-demo"
    identidad = sys.argv[2] if len(sys.argv) > 2 else "visitante"
    print(emitir(sala, identidad))
