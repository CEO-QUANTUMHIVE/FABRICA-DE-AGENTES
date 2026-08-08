"""La frontera dura del motor.

brain/ contiene el cerebro: contexto, prompts, tools y datos del negocio.
voice/ contiene el canal: LiveKit, STT, TTS y la sesion de audio.

brain/ NO puede depender de voice/ ni de livekit. Si lo hiciera, el modo
asincrono (WhatsApp, Telegram) y el asistente de escritorio no podrian
reusar el cerebro, porque esos canales no pasan por LiveKit.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
BRAIN = RAIZ / "src" / "motor_voz" / "brain"
PROHIBIDOS = ("livekit", "motor_voz.voice")


def modulos_del_brain() -> list[pathlib.Path]:
    return sorted(BRAIN.rglob("*.py"))


def imports_de(ruta: pathlib.Path) -> list[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    nombres: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nombres.append(nodo.module)
    return nombres


def test_el_paquete_brain_existe_y_tiene_modulos():
    """Sin esta guarda, el test de abajo pasaria sin revisar nada."""
    assert BRAIN.is_dir(), f"No existe el paquete brain en {BRAIN}"
    assert modulos_del_brain(), "brain/ no tiene ningun modulo .py para revisar"


@pytest.mark.parametrize("ruta", modulos_del_brain(), ids=lambda p: p.name)
def test_brain_no_importa_livekit_ni_voice(ruta: pathlib.Path):
    for nombre in imports_de(ruta):
        for prohibido in PROHIBIDOS:
            assert not (nombre == prohibido or nombre.startswith(prohibido + ".")), (
                f"{ruta.relative_to(RAIZ)} importa '{nombre}'.\n"
                f"brain/ no puede depender de '{prohibido}'. "
                f"Si el cerebro necesita algo del canal, se pasa como argumento."
            )
