"""Los tres niveles de realismo que el visitante puede probar en vivo.

Es la traduccion entre lo que ve el usuario y el motor que corre atras.
Existe para que el frontend nunca nombre un motor: pide un nivel, y el
backend decide y firma. Si el navegador pudiera elegir el motor, cualquiera
consumiria el plan premium desde la consola del navegador.
"""

from __future__ import annotations

from dataclasses import dataclass

from motor_voz.voice.motores import MOTORES


@dataclass(frozen=True)
class Nivel:
    numero: int
    motor: str
    plan: str
    titulo: str
    descripcion: str


NIVELES: dict[int, Nivel] = {
    1: Nivel(
        numero=1,
        motor="pipeline",
        plan="basico",
        titulo="Basico",
        descripcion="Voz sintetizada sobre texto. Clara y economica.",
    ),
    2: Nivel(
        numero=2,
        motor="gemini",
        plan="medio",
        titulo="Natural",
        descripcion="Voz a voz. Entona, duda y respira como una persona.",
    ),
    3: Nivel(
        numero=3,
        motor="openai",
        plan="premium",
        titulo="Humano",
        descripcion="Voz a voz de maxima expresividad y menor latencia.",
    ),
}


class NivelInvalido(ValueError):
    """El nivel pedido no existe."""


def resolver(numero: object) -> Nivel:
    """Traduce lo que mando el navegador a un nivel valido, o falla."""
    try:
        n = int(numero)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise NivelInvalido(f"Nivel invalido: {numero!r}. Validos: 1, 2, 3.") from None
    if n not in NIVELES:
        raise NivelInvalido(f"Nivel invalido: {n}. Validos: 1, 2, 3.")
    return NIVELES[n]


def catalogo() -> list[dict[str, object]]:
    """Lo que el frontend necesita para dibujar el selector."""
    return [
        {
            "nivel": n.numero,
            "titulo": n.titulo,
            "descripcion": n.descripcion,
            "plan": n.plan,
        }
        for n in NIVELES.values()
    ]


# Cada nivel tiene que apuntar a un motor que exista de verdad.
assert all(n.motor in MOTORES for n in NIVELES.values())
