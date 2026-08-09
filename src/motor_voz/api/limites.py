"""Control de abuso y de gasto para la demo publica.

El spec lo exige antes de exponer nada: sin esto, cualquiera hace un bucle
sobre el endpoint de token y quema los creditos de la cuenta.

Es en memoria a proposito. Un solo proceso alcanza para la demo, y meter
Redis ahora seria infraestructura antes de validar. Cuando haya mas de una
instancia, se cambia la implementacion sin tocar a quien la usa.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class LimiteAlcanzado(RuntimeError):
    """Se llego a un tope. El mensaje se le muestra al visitante."""


class Limitador:
    def __init__(self, *, por_ip_hora: int, por_dia: int) -> None:
        self.por_ip_hora = por_ip_hora
        self.por_dia = por_dia
        self._por_ip: dict[str, deque[float]] = defaultdict(deque)
        self._del_dia: deque[float] = deque()

    def registrar(self, ip: str, ahora: float | None = None) -> None:
        """Anota una sesion nueva. Falla si algun tope esta alcanzado."""
        t = time.monotonic() if ahora is None else ahora

        self._purgar(self._del_dia, t, 86_400)
        if len(self._del_dia) >= self.por_dia:
            raise LimiteAlcanzado(
                "Hoy la demo alcanzo su limite de conversaciones. "
                "Escribinos y la seguimos por chat."
            )

        cola = self._por_ip[ip]
        self._purgar(cola, t, 3_600)
        if len(cola) >= self.por_ip_hora:
            raise LimiteAlcanzado(
                "Ya probaste la demo varias veces en la ultima hora. "
                "Volve en un rato y seguimos."
            )

        cola.append(t)
        self._del_dia.append(t)

    def estado(self) -> dict[str, int]:
        self._purgar(self._del_dia, time.monotonic(), 86_400)
        return {"sesiones_hoy": len(self._del_dia), "tope_diario": self.por_dia}

    @staticmethod
    def _purgar(cola: deque[float], ahora: float, ventana: float) -> None:
        while cola and ahora - cola[0] > ventana:
            cola.popleft()
