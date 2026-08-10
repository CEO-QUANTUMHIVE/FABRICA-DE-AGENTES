"""Resuelve que tenant atiende una sala.

El slug del tenant viaja en el nombre de sala, exactamente como el motor
(ver voice/agente.py:motor_de_la_sala). El nombre de sala queda fijado en
el token via VideoGrants(room=...) al emitirlo, asi que el navegador no
lo puede falsear: solo se puede unir a la sala que el backend eligio.

Formato de hoy, antes de la Task 9:

    demo - gemini - Leda - a1b2c3
     [0]     [1]    [2]     [3]

Formato al que lo lleva la Task 9, con el tenant adelante:

    demo - quantumhive - gemini - Leda - a1b2c3
     [0]       [1]        [2]     [3]     [4]

Por eso la condicion es `>= 4` y no `== 5`: el resolver ya funciona con el
formato nuevo y no se rompe con el viejo mientras la Task 9 no este hecha.
Los slugs de tenant no llevan guiones (`demo_capilar` usa guion bajo), asi
que partir por `-` es seguro.

Esta funcion no sabe que existe livekit: recibe un string y devuelve
otro. La frontera la cumple tests/test_frontera.py.
"""

from __future__ import annotations

TENANT_POR_DEFECTO = "quantumhive"


def tenant_de_la_sala(nombre_sala: str) -> str:
    """Extrae el tenant del nombre `demo-<tenant>-<motor>-...`.

    Si el nombre no sigue ese formato — una sala creada a mano, por
    ejemplo — se usa el tenant por defecto. Nunca se devuelve lo que venga
    en la cadena sin verificar el prefijo: caer en un tenant equivocado es
    peor que caer en el default.
    """
    partes = nombre_sala.split("-")
    if len(partes) >= 4 and partes[0] == "demo":
        return partes[1]
    return TENANT_POR_DEFECTO
