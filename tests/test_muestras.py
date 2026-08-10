"""Los saludos pregrabados del selector de voces.

No sintetizan nada: verifican que el catalogo y los archivos no se
desincronicen. La trampa que cubren es agregar una voz en `motores.py` y
olvidarse de grabarle la muestra — el chip aparece en el widget, el visitante
lo toca y no suena nada.
"""

from pathlib import Path

import pytest

from motor_voz.voice.motores import VOCES_GEMINI, VOCES_OPENAI, ruta_de_muestra

MUESTRAS = Path(__file__).resolve().parents[1] / "frontend" / "widget" / "public" / "assets" / "muestras"

ESPERADAS = {("gemini", c) for c in VOCES_GEMINI} | {("openai", c) for c in VOCES_OPENAI}


def _nombre(motor: str, clave: str) -> str:
    return Path(ruta_de_muestra(motor, clave)).name


def _grabadas() -> set[str]:
    return {p.name for p in MUESTRAS.glob("*.mp3")} if MUESTRAS.is_dir() else set()


class TestRutaDeMuestra:
    def test_es_relativa_al_widget(self):
        """Absoluta ataria las muestras a un dominio, y el widget se sirve en varios."""
        r = ruta_de_muestra("gemini", "Puck")
        assert r == "assets/muestras/gemini-Puck.mp3"
        assert not r.startswith("/"), "Relativa: la resuelve el origen del widget"
        assert "://" not in r

    def test_el_motor_va_en_el_nombre(self):
        """Las claves no son unicas entre motores; sin el prefijo se pisarian."""
        assert ruta_de_muestra("gemini", "Kore") != ruta_de_muestra("openai", "Kore")


class TestArchivos:
    def test_no_hay_muestras_huerfanas(self):
        """Un mp3 que no corresponde a ninguna voz es catalogo viejo sin borrar."""
        sobran = sorted(_grabadas() - {_nombre(m, c) for m, c in ESPERADAS})
        assert not sobran, f"No corresponden a ninguna voz del catalogo: {sobran}"

    def test_toda_voz_del_catalogo_tiene_su_saludo(self):
        grabadas = _grabadas()
        if not grabadas:
            pytest.skip(
                "Todavia no se grabo ninguna muestra. "
                "Corre: uv run python scripts/generar_muestras.py"
            )
        faltan = sorted(_nombre(m, c) for m, c in ESPERADAS if _nombre(m, c) not in grabadas)
        assert not faltan, f"Voces sin grabar: {faltan}. Corre scripts/generar_muestras.py"
