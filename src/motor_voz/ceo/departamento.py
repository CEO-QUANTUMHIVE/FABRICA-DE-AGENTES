"""Contrato departamental de Fábrica de Agentes.

Este modulo valida y despacha trabajos; no contiene un orquestador ni ejecuta
comandos. QuantumCore conserva objetivos, presupuestos y auditoria durable. Un
worker concreto se conecta por ``RegistroWorkers`` y recibe solo una solicitud
normalizada que ya paso por todas las politicas de este departamento.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PureWindowsPath
from typing import Any

logger = logging.getLogger("fabrica-agentes.ceo")

CODIGO_DEPARTAMENTO = "fabrica-de-agentes"
NOMBRE_DEPARTAMENTO = "Fábrica de Agentes"
VERSION_CONTRATO = "1.0"
ESTADO_DEPARTAMENTO = "activo"
REPOSITORIO = r"C:\Users\sergio\Desktop\FABRICA-DE-AGENTES"
PREFIJO_RAMA = "quantumcore/"
PRESUPUESTO_MAXIMO_USD = 5.0
TIEMPO_MAXIMO_SEGUNDOS = 1800

Worker = Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]


@dataclass(frozen=True)
class PoliticaTrabajo:
    workers: tuple[str, ...]
    cerebros_por_worker: Mapping[str, tuple[str, ...]]
    modelos_por_cerebro: Mapping[str, tuple[str, ...]]
    herramientas: tuple[str, ...]
    presupuesto_maximo_usd: float
    tiempo_maximo_segundos: int
    requiere_tenant: bool = False
    alternativas: tuple[str, ...] = ()


HERRAMIENTAS_CODIGO = (
    "leer_archivos",
    "editar_archivos",
    "git_local",
    "pytest",
    "build",
    "documentacion",
)
HERRAMIENTAS_MODELO = ("analizar_texto", "redactar_documentacion")
HERRAMIENTAS_POR_WORKER = {
    "codex-local": HERRAMIENTAS_CODIGO,
    "claude-local": HERRAMIENTAS_CODIGO,
    "modelo-directo": HERRAMIENTAS_MODELO,
}

POLITICAS: dict[str, PoliticaTrabajo] = {
    "analizar_codigo": PoliticaTrabajo(
        workers=("codex-local", "claude-local"),
        cerebros_por_worker={
            "codex-local": ("openai",),
            "claude-local": ("anthropic",),
        },
        modelos_por_cerebro={"openai": ("codex",), "anthropic": ("claude",)},
        herramientas=("leer_archivos",),
        presupuesto_maximo_usd=2.0,
        tiempo_maximo_segundos=600,
        alternativas=("codex-local", "claude-local"),
    ),
    "implementar_codigo": PoliticaTrabajo(
        workers=("codex-local", "claude-local"),
        cerebros_por_worker={
            "codex-local": ("openai",),
            "claude-local": ("anthropic",),
        },
        modelos_por_cerebro={"openai": ("codex",), "anthropic": ("claude",)},
        herramientas=HERRAMIENTAS_CODIGO,
        presupuesto_maximo_usd=5.0,
        tiempo_maximo_segundos=1800,
        alternativas=("codex-local", "claude-local"),
    ),
    "ejecutar_pruebas": PoliticaTrabajo(
        workers=("codex-local", "claude-local"),
        cerebros_por_worker={
            "codex-local": ("openai",),
            "claude-local": ("anthropic",),
        },
        modelos_por_cerebro={"openai": ("codex",), "anthropic": ("claude",)},
        herramientas=("leer_archivos", "pytest", "build"),
        presupuesto_maximo_usd=3.0,
        tiempo_maximo_segundos=1200,
        alternativas=("codex-local", "claude-local"),
    ),
    "actualizar_documentacion": PoliticaTrabajo(
        workers=("codex-local", "claude-local", "modelo-directo"),
        cerebros_por_worker={
            "codex-local": ("openai",),
            "claude-local": ("anthropic",),
            "modelo-directo": ("openai", "anthropic", "google", "groq"),
        },
        modelos_por_cerebro={
            "openai": ("codex", "gpt"),
            "anthropic": ("claude",),
            "google": ("gemini",),
            "groq": ("llama", "openai/gpt-oss"),
        },
        herramientas=HERRAMIENTAS_CODIGO + HERRAMIENTAS_MODELO,
        presupuesto_maximo_usd=2.0,
        tiempo_maximo_segundos=900,
        alternativas=("modelo-directo", "codex-local", "claude-local"),
    ),
    "clasificar": PoliticaTrabajo(
        workers=("modelo-directo",),
        cerebros_por_worker={
            "modelo-directo": ("openai", "anthropic", "google", "groq")
        },
        modelos_por_cerebro={
            "openai": ("gpt",),
            "anthropic": ("claude",),
            "google": ("gemini",),
            "groq": ("llama", "openai/gpt-oss"),
        },
        herramientas=("analizar_texto",),
        presupuesto_maximo_usd=0.5,
        tiempo_maximo_segundos=120,
        alternativas=(),
    ),
    "resumir": PoliticaTrabajo(
        workers=("modelo-directo",),
        cerebros_por_worker={
            "modelo-directo": ("openai", "anthropic", "google", "groq")
        },
        modelos_por_cerebro={
            "openai": ("gpt",),
            "anthropic": ("claude",),
            "google": ("gemini",),
            "groq": ("llama", "openai/gpt-oss"),
        },
        herramientas=("analizar_texto",),
        presupuesto_maximo_usd=0.5,
        tiempo_maximo_segundos=120,
        alternativas=(),
    ),
    "redactar_documentacion": PoliticaTrabajo(
        workers=("modelo-directo", "codex-local"),
        cerebros_por_worker={
            "modelo-directo": ("openai", "anthropic", "google", "groq"),
            "codex-local": ("openai",),
        },
        modelos_por_cerebro={
            "openai": ("gpt", "codex"),
            "anthropic": ("claude",),
            "google": ("gemini",),
            "groq": ("llama", "openai/gpt-oss"),
        },
        herramientas=HERRAMIENTAS_MODELO + ("documentacion",),
        presupuesto_maximo_usd=1.0,
        tiempo_maximo_segundos=300,
        alternativas=("modelo-directo", "codex-local"),
    ),
}

CONSULTAS_PERMITIDAS = frozenset(
    {
        "arquitectura",
        "capacidades",
        "estado_modulos",
        "documentacion",
        "comandos_prueba",
        "configuracion_publica",
        "salud",
        "tenant",
    }
)

CAMPOS_DINAMICOS_PROHIBIDOS = frozenset(
    {
        "command",
        "comando",
        "shell",
        "script",
        "codigo_ejecutable",
        "eval",
        "exec",
        "env",
        "variables_entorno",
    }
)
HERRAMIENTAS_PROHIBIDAS = frozenset(
    {"shell", "powershell", "cmd", "exec", "eval", "push", "deploy", "red_libre"}
)
CLAVES_SENSIBLES = (
    "secret",
    "secreto",
    "token",
    "password",
    "contrasena",
    "api_key",
    "authorization",
    "credential",
    "clave_privada",
)


class RegistroWorkers:
    """Registro explicito: declarar un perfil no lo vuelve ejecutable."""

    def __init__(self) -> None:
        self._workers: dict[str, Worker] = {}

    def registrar(self, nombre: str, worker: Worker) -> None:
        if nombre not in {w for p in POLITICAS.values() for w in p.workers}:
            raise ValueError(f"perfil de worker desconocido: {nombre}")
        self._workers[nombre] = worker

    def obtener(self, nombre: str) -> Worker | None:
        return self._workers.get(nombre)

    def disponibles(self) -> tuple[str, ...]:
        return tuple(sorted(self._workers))


def _coincide_modelo(modelo: str, prefijos: tuple[str, ...]) -> bool:
    limpio = modelo.strip().lower()
    return any(limpio == p or limpio.startswith(p + "-") for p in prefijos)


def _contiene_campo_dinamico(valor: Any) -> bool:
    if isinstance(valor, Mapping):
        for clave, contenido in valor.items():
            if str(clave).strip().lower() in CAMPOS_DINAMICOS_PROHIBIDOS:
                return True
            if _contiene_campo_dinamico(contenido):
                return True
    elif isinstance(valor, (list, tuple)):
        return any(_contiene_campo_dinamico(item) for item in valor)
    return False


def solicitud_sin_codigo_dinamico(solicitud: Mapping[str, Any]) -> bool:
    return not _contiene_campo_dinamico(solicitud)


def _ruta_permitida(ruta: str) -> bool:
    if not ruta.strip() or "*" in ruta or "?" in ruta:
        return False
    candidata = PureWindowsPath(ruta)
    if ".." in candidata.parts:
        return False
    if not candidata.is_absolute():
        candidata = PureWindowsPath(REPOSITORIO) / candidata
    try:
        candidata.relative_to(PureWindowsPath(REPOSITORIO))
    except ValueError:
        return False
    return True


def _limpiar_sensible(valor: Any, secretos: tuple[str, ...] = ()) -> Any:
    """Redacta claves y valores sensibles antes de responder o auditar."""
    secretos_reales = tuple(s for s in secretos if s)
    if isinstance(valor, Mapping):
        limpio: dict[str, Any] = {}
        for clave, contenido in valor.items():
            nombre = str(clave)
            if nombre.lower() != "tokens" and any(
                fragmento in nombre.lower() for fragmento in CLAVES_SENSIBLES
            ):
                limpio[nombre] = "[REDACTADO]"
            else:
                limpio[nombre] = _limpiar_sensible(contenido, secretos_reales)
        return limpio
    if isinstance(valor, (list, tuple)):
        return [_limpiar_sensible(item, secretos_reales) for item in valor]
    if isinstance(valor, str):
        limpio = valor
        for secreto in secretos_reales:
            limpio = limpio.replace(secreto, "[REDACTADO]")
        return limpio
    return valor


def describir_ceo(
    *, dependencias: Mapping[str, bool] | None = None, workers_disponibles: tuple[str, ...] = ()
) -> dict[str, Any]:
    """Describe solo capacidades y politicas realmente implementadas."""
    dependencias = dependencias or {}
    return {
        "codigo": CODIGO_DEPARTAMENTO,
        "nombre": NOMBRE_DEPARTAMENTO,
        "version_contrato": VERSION_CONTRATO,
        "estado": ESTADO_DEPARTAMENTO,
        "repositorio": REPOSITORIO,
        "capacidades": [
            "describir interfaz departamental",
            "consultas estructuradas de solo lectura",
            "validacion y despacho de trabajos estructurados",
            "aislamiento por identidad, membresia y tenant activo",
            "idempotencia durante la vida del proceso",
            "resultado estructurado con evidencia, costo y errores",
        ],
        "consultas_soportadas": sorted(CONSULTAS_PERMITIDAS),
        "tipos_trabajo_soportados": sorted(POLITICAS),
        "workers_permitidos": ["codex-local", "claude-local", "modelo-directo"],
        "workers_conectados": list(workers_disponibles),
        "cerebros_compatibles": {
            "openai": ["codex*", "gpt*"],
            "anthropic": ["claude*"],
            "google": ["gemini*"],
            "groq": ["llama*", "openai/gpt-oss*"],
        },
        "prefijo_rama_autorizado": PREFIJO_RAMA,
        "pruebas_disponibles": [
            "uv run pytest -q",
            "uv run pytest -q tests/test_ceo_departamental.py",
            "npm.cmd run build (frontend/panel)",
            "npm.cmd run build (frontend/widget)",
        ],
        "limites": {
            "tiempo_maximo_segundos": TIEMPO_MAXIMO_SEGUNDOS,
            "presupuesto_maximo_usd": PRESUPUESTO_MAXIMO_USD,
            "tamano_maximo_solicitud_bytes": 1_000_000,
        },
        "dependencias": {str(k): bool(v) for k, v in dependencias.items()},
        "politicas": {
            nombre: {
                "workers": list(politica.workers),
                "herramientas_por_worker": {
                    worker: sorted(
                        set(politica.herramientas) & set(HERRAMIENTAS_POR_WORKER[worker])
                    )
                    for worker in politica.workers
                },
                "tiempo_maximo_segundos": politica.tiempo_maximo_segundos,
                "presupuesto_maximo_usd": politica.presupuesto_maximo_usd,
                "alternativas": list(politica.alternativas),
            }
            for nombre, politica in POLITICAS.items()
        },
    }


def consultar_ceo(
    tipo: str,
    *,
    tenant: Mapping[str, Any] | None = None,
    configuracion_publica: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    """Resuelve una consulta cerrada sin comandos ni lecturas arbitrarias."""
    if tipo not in CONSULTAS_PERMITIDAS:
        raise ValueError("tipo_consulta_no_permitido")
    if tipo == "arquitectura":
        resultado: Any = {
            "flujo": "Dominus -> QuantumCore -> CEO Fábrica de Agentes -> worker autorizado",
            "capas": {
                "brain": "prompts, contexto, tools y repositorio de tenants; sin LiveKit",
                "voice": "LiveKit, STT, TTS y motores de voz",
                "api": "HTTP, autenticacion, limites y contrato departamental",
                "ceo": "politicas, idempotencia y despacho; sin comandos libres",
            },
        }
    elif tipo == "capacidades":
        resultado = {
            "consultas": sorted(CONSULTAS_PERMITIDAS),
            "trabajos": sorted(POLITICAS),
        }
    elif tipo == "estado_modulos":
        resultado = {
            "brain": "disponible",
            "voice": "disponible",
            "api": "disponible",
            "channels": "disponible",
            "ceo": "disponible",
        }
    elif tipo == "documentacion":
        resultado = [
            "CLAUDE.md",
            "docs/MAPA.md",
            "docs/guia-de-prompts.md",
            "docs/ceo-fabrica-de-agentes.md",
        ]
    elif tipo == "comandos_prueba":
        resultado = [
            ["uv", "run", "pytest", "-q"],
            ["npm.cmd", "run", "build", "--prefix", "frontend/panel"],
            ["npm.cmd", "run", "build", "--prefix", "frontend/widget"],
        ]
    elif tipo == "configuracion_publica":
        resultado = dict(configuracion_publica or {})
    elif tipo == "salud":
        resultado = {"estado": ESTADO_DEPARTAMENTO, "contrato": VERSION_CONTRATO}
    else:
        if tenant is None:
            raise ValueError("tenant_requerido")
        resultado = {
            "id": tenant["id"],
            "slug": tenant["slug"],
            "nombre": tenant["nombre"],
            "idioma": tenant["idioma"],
            "estado": "activo",
        }
    return {"tipo": tipo, "solo_lectura": True, "resultado": resultado}


class CEODeFabricaDeAgentes:
    def __init__(
        self, registro: RegistroWorkers | None = None, *, secretos: tuple[str, ...] = ()
    ) -> None:
        self.registro = registro or RegistroWorkers()
        self._secretos = secretos
        self._candado = asyncio.Lock()
        self._idempotencia: dict[str, tuple[str, str, asyncio.Future[dict[str, Any]]]] = {}

    @staticmethod
    def _rechazo(solicitud: Mapping[str, Any], motivo: str) -> dict[str, Any]:
        ahora = datetime.now(timezone.utc).isoformat()
        return {
            "trabajo_id": str(solicitud.get("trabajo_id", "")),
            "clave_idempotencia": str(solicitud.get("clave_idempotencia", "")),
            "estado": "rechazado",
            "resumen": "La solicitud fue rechazada antes de ejecutar.",
            "archivos_modificados": [],
            "pruebas_ejecutadas": [],
            "resultado_pruebas": "no ejecutadas",
            "rama": str(solicitud.get("rama", "")),
            "commit": None,
            "evidencia": [],
            "tokens": {},
            "costo_usd": None,
            "duracion_ms": 0,
            "motivo": motivo,
            "departamento": CODIGO_DEPARTAMENTO,
            "tenant": solicitud.get("tenant"),
            "worker": solicitud.get("worker"),
            "cerebro": solicitud.get("cerebro"),
            "modelo": solicitud.get("modelo"),
            "herramientas": solicitud.get("herramientas_permitidas", []),
            "correlacion_id": None,
            "inicio": ahora,
            "fin": ahora,
        }

    def _validar(self, s: Mapping[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
        requeridos = (
            "trabajo_id",
            "clave_idempotencia",
            "departamento",
            "repositorio",
            "tipo_trabajo",
            "titulo",
            "objetivo",
            "resultado_esperado",
            "rama",
            "worker",
            "cerebro",
            "modelo",
            "tiempo_maximo_segundos",
            "presupuesto_maximo_usd",
            "herramientas_permitidas",
            "auditoria",
        )
        if any(campo not in s or s[campo] in (None, "") for campo in requeridos):
            return "solicitud_incompleta", None
        campos_texto = (
            "trabajo_id",
            "clave_idempotencia",
            "departamento",
            "repositorio",
            "tipo_trabajo",
            "titulo",
            "objetivo",
            "resultado_esperado",
            "rama",
            "worker",
            "cerebro",
            "modelo",
        )
        if not all(isinstance(s[campo], str) and len(s[campo]) <= 10_000 for campo in campos_texto):
            return "campos_texto_invalidos", None
        if not solicitud_sin_codigo_dinamico(s):
            return "codigo_o_comando_dinamico_prohibido", None
        if s["departamento"] != CODIGO_DEPARTAMENTO:
            return "departamento_incorrecto", None
        if str(s["repositorio"]).replace("/", "\\").casefold() != REPOSITORIO.casefold():
            return "repositorio_incorrecto", None
        rama = str(s["rama"]).strip()
        if rama.casefold() == "main" or not rama.startswith(PREFIJO_RAMA):
            return "rama_no_autorizada", None
        tipo = str(s["tipo_trabajo"])
        politica = POLITICAS.get(tipo)
        if politica is None:
            return "tipo_trabajo_no_permitido", None
        worker = str(s["worker"])
        if worker not in politica.workers:
            return "worker_no_permitido", None
        cerebro = str(s["cerebro"]).strip().lower()
        if cerebro not in politica.cerebros_por_worker.get(worker, ()):
            return "cerebro_no_permitido", None
        if not _coincide_modelo(str(s["modelo"]), politica.modelos_por_cerebro[cerebro]):
            return "modelo_no_permitido", None
        try:
            tiempo = int(s["tiempo_maximo_segundos"])
            presupuesto = float(s["presupuesto_maximo_usd"])
        except (TypeError, ValueError):
            return "limites_invalidos", None
        if tiempo <= 0 or tiempo > politica.tiempo_maximo_segundos:
            return "tiempo_maximo_excedido", None
        if presupuesto < 0 or presupuesto > politica.presupuesto_maximo_usd:
            return "presupuesto_maximo_excedido", None
        herramientas = s["herramientas_permitidas"]
        if not isinstance(herramientas, list) or not all(
            isinstance(h, str) for h in herramientas
        ):
            return "herramientas_invalidas", None
        if set(herramientas) & HERRAMIENTAS_PROHIBIDAS:
            return "herramienta_prohibida", None
        herramientas_del_worker = set(HERRAMIENTAS_POR_WORKER[worker])
        if not set(herramientas).issubset(set(politica.herramientas) & herramientas_del_worker):
            return "herramienta_no_autorizada", None
        rutas = s.get("rutas", [])
        if not isinstance(rutas, list) or not all(
            isinstance(ruta, str) and _ruta_permitida(ruta) for ruta in rutas
        ):
            return "ruta_fuera_del_checkout", None
        auditoria = s["auditoria"]
        if not isinstance(auditoria, Mapping) or not all(
            auditoria.get(campo) for campo in ("solicitado_por", "correlacion_id")
        ):
            return "auditoria_incompleta", None
        campos_auditoria = {
            "solicitado_por",
            "correlacion_id",
            "causacion_id",
            "objetivo_id",
            "tenant_id",
        }
        if not set(auditoria).issubset(campos_auditoria) or not all(
            isinstance(valor, str) and len(valor) <= 500 for valor in auditoria.values()
        ):
            return "auditoria_invalida", None
        if politica.requiere_tenant and not s.get("tenant"):
            return "tenant_requerido", None

        normalizada = {
            campo: deepcopy(s[campo])
            for campo in requeridos
        }
        normalizada["rutas"] = list(rutas)
        if s.get("tenant"):
            normalizada["tenant"] = str(s["tenant"])
        normalizada["limites_validados"] = {
            "tiempo_maximo_segundos": tiempo,
            "presupuesto_maximo_usd": presupuesto,
        }
        return None, normalizada

    async def accionar(self, solicitud: Mapping[str, Any]) -> dict[str, Any]:
        motivo, normalizada = self._validar(solicitud)
        if motivo or normalizada is None:
            return self._rechazo(solicitud, motivo or "solicitud_invalida")

        clave = str(normalizada["clave_idempotencia"])
        trabajo_id = str(normalizada["trabajo_id"])
        huella = hashlib.sha256(
            json.dumps(normalizada, sort_keys=True, ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        propietario = False
        async with self._candado:
            existente = self._idempotencia.get(clave)
            if existente:
                trabajo_previo, huella_previa, futuro = existente
                if trabajo_previo != trabajo_id or huella_previa != huella:
                    return self._rechazo(solicitud, "idempotencia_conflictiva")
            else:
                futuro = asyncio.get_running_loop().create_future()
                self._idempotencia[clave] = (trabajo_id, huella, futuro)
                propietario = True

        if not propietario:
            repetida = deepcopy(await asyncio.shield(futuro))
            repetida["idempotente_repetido"] = True
            return repetida

        inicio = time.monotonic()
        inicio_utc = datetime.now(timezone.utc).isoformat()
        resultado: dict[str, Any]
        worker = self.registro.obtener(str(normalizada["worker"]))
        if worker is None:
            resultado = self._rechazo(solicitud, "worker_no_conectado")
        else:
            logger.info(
                "ceo despacha trabajo=%s worker=%s tenant=%s",
                trabajo_id,
                normalizada["worker"],
                normalizada.get("tenant", "sin-tenant"),
            )
            try:
                bruto = await asyncio.wait_for(
                    worker(deepcopy(normalizada)),
                    timeout=int(normalizada["tiempo_maximo_segundos"]),
                )
                limpio = _limpiar_sensible(bruto, self._secretos)
                archivos = list(limpio.get("archivos_modificados", []))
                if not all(isinstance(r, str) and _ruta_permitida(r) for r in archivos):
                    raise ValueError("worker_devolvio_ruta_fuera_del_checkout")
                pruebas = list(limpio.get("pruebas_ejecutadas", []))
                pruebas_ok = bool(limpio.get("pruebas_ok", not pruebas))
                costo = limpio.get("costo_usd")
                if costo is not None and float(costo) > float(
                    normalizada["presupuesto_maximo_usd"]
                ):
                    raise ValueError("worker_excedio_presupuesto")
                estado = "completado" if pruebas_ok else "error"
                resultado = {
                    "trabajo_id": trabajo_id,
                    "clave_idempotencia": clave,
                    "estado": estado,
                    "resumen": str(limpio.get("resumen", "")),
                    "archivos_modificados": archivos,
                    "pruebas_ejecutadas": pruebas,
                    "resultado_pruebas": limpio.get(
                        "resultado_pruebas", "ok" if pruebas_ok else "fallaron"
                    ),
                    "rama": normalizada["rama"],
                    "commit": limpio.get("commit"),
                    "evidencia": list(limpio.get("evidencia", [])),
                    "tokens": limpio.get("tokens", {}),
                    "costo_usd": costo,
                    "duracion_ms": 0,
                    "motivo": None if estado == "completado" else "pruebas_fallidas",
                    "departamento": CODIGO_DEPARTAMENTO,
                    "tenant": normalizada.get("tenant"),
                    "worker": normalizada["worker"],
                    "cerebro": normalizada["cerebro"],
                    "modelo": normalizada["modelo"],
                    "herramientas": normalizada["herramientas_permitidas"],
                    "correlacion_id": normalizada["auditoria"]["correlacion_id"],
                    "inicio": inicio_utc,
                    "fin": None,
                }
            except asyncio.TimeoutError:
                resultado = self._rechazo(solicitud, "worker_agoto_tiempo")
                resultado["estado"] = "error"
                resultado["resumen"] = "El worker excedio el tiempo autorizado."
            except Exception as error:
                logger.warning(
                    "ceo worker fallo trabajo=%s clase=%s", trabajo_id, type(error).__name__
                )
                resultado = self._rechazo(solicitud, "error_del_worker")
                resultado["estado"] = "error"
                resultado["resumen"] = "El worker termino con un error estructurado."

        resultado["duracion_ms"] = int((time.monotonic() - inicio) * 1000)
        resultado["fin"] = datetime.now(timezone.utc).isoformat()
        resultado["inicio"] = inicio_utc
        resultado["correlacion_id"] = normalizada["auditoria"]["correlacion_id"]
        if not futuro.done():
            futuro.set_result(deepcopy(resultado))
        return resultado
