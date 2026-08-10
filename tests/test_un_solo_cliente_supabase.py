"""Nadie fuera de repositorio.py instancia el cliente de Supabase.

Supabase se usa con SERVICE_ROLE_KEY, que saltea RLS (spec S7). El
aislamiento entre tenants depende de que TODA query pase por
brain/tenants/repositorio.py y filtre por tenant_id ahi. Si otro modulo
pudiera instanciar el cliente, esa garantia desaparece.
"""

from __future__ import annotations

import ast
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SRC = RAIZ / "src" / "motor_voz"
PERMITIDO = SRC / "brain" / "tenants" / "repositorio.py"
PROHIBIDOS = ("create_client", "acreate_client")


def modulos_del_src() -> list[pathlib.Path]:
    return sorted(p for p in SRC.rglob("*.py") if p != PERMITIDO)


def nombres_llamados(ruta: pathlib.Path) -> list[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    nombres: list[str] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        objetivo = nodo.func
        if isinstance(objetivo, ast.Name):
            nombres.append(objetivo.id)
        elif isinstance(objetivo, ast.Attribute):
            nombres.append(objetivo.attr)
    return nombres


def test_repositorio_existe():
    """Sin esta guarda, el test de abajo pasaria sin revisar nada."""
    assert PERMITIDO.exists(), f"No existe {PERMITIDO}"


def test_ningun_otro_modulo_crea_el_cliente_de_supabase():
    infractores = [
        str(ruta.relative_to(RAIZ))
        for ruta in modulos_del_src()
        if any(llamado in PROHIBIDOS for llamado in nombres_llamados(ruta))
    ]
    assert not infractores, (
        "Estos modulos instancian el cliente de Supabase fuera de "
        f"repositorio.py: {infractores}. Todo acceso a Supabase pasa por "
        "brain/tenants/repositorio.py."
    )
