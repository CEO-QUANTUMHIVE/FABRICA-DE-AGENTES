"""Contrato y defensas del CEO departamental de Fábrica de Agentes."""

from __future__ import annotations

import json

import pytest

from motor_voz.api.servidor import crear_app
from motor_voz.brain.tenants.modelos import PerfilTenant, Tenant
from motor_voz.brain.tenants.repositorio import TenantNoEncontrado
from motor_voz.ceo.departamento import REPOSITORIO, RegistroWorkers
from motor_voz.config import cargar

TOKEN_QUANTUMCORE = "qc-token-de-prueba-no-real"
ENTORNO = {
    "GROQ_API_KEY": "gsk_falsa",
    "FISH_API_KEY": "sk-falsa",
    "LIVEKIT_URL": "ws://localhost:7880",
    "LIVEKIT_API_KEY": "devkey",
    "LIVEKIT_API_SECRET": "secreto-largo-de-prueba-1234567890",
    "ENVIRONMENT": "test",
    "QUANTUMCORE_TOKEN": TOKEN_QUANTUMCORE,
}


def _tenant(slug: str, nombre: str) -> Tenant:
    return Tenant(
        id=f"id-{slug}",
        slug=slug,
        nombre=nombre,
        idioma="es",
        perfil=PerfilTenant(slug="receptor", nombre="Receptor", prompt_base="Seguro"),
        prompt_propio="",
        servicios=(),
        voz=None,
    )


TENANTS = {
    "negocio-a": _tenant("negocio-a", "Negocio A"),
    "negocio-b": _tenant("negocio-b", "Negocio B"),
}


async def _obtener_tenant(config, slug):
    if slug not in TENANTS:
        raise TenantNoEncontrado("tenant inactivo o desconocido")
    return TENANTS[slug]


async def _usuario_de_token(config, token):
    return {"sesion-a": "usuario-a", "sesion-b": "usuario-b"}.get(token)


async def _rol(config, usuario_id, tenant_id):
    permitidos = {
        ("usuario-a", "id-negocio-a"),
        ("usuario-b", "id-negocio-b"),
    }
    return "dueno" if (usuario_id, tenant_id) in permitidos else None


def _cabeceras(*, actor: str | None = None, autenticado: bool = True) -> dict[str, str]:
    headers = {}
    if autenticado:
        headers["Authorization"] = f"Bearer {TOKEN_QUANTUMCORE}"
    if actor:
        headers["X-QuantumCore-Actor-Token"] = actor
    return headers


def _solicitud(**cambios):
    base = {
        "trabajo_id": "trabajo-001",
        "clave_idempotencia": "idem-001",
        "departamento": "fabrica-de-agentes",
        "repositorio": REPOSITORIO,
        "tipo_trabajo": "implementar_codigo",
        "titulo": "Agregar una prueba segura",
        "objetivo": "Implementar el cambio estructurado que aprobo QuantumCore.",
        "resultado_esperado": "Pruebas en verde y evidencia.",
        "rama": "quantumcore/trabajo-001",
        "worker": "codex-local",
        "cerebro": "openai",
        "modelo": "codex-seleccionado-por-quantumcore",
        "tiempo_maximo_segundos": 300,
        "presupuesto_maximo_usd": 1.5,
        "herramientas_permitidas": ["leer_archivos", "editar_archivos", "pytest"],
        "rutas": ["src/motor_voz", "tests"],
        "auditoria": {
            "solicitado_por": "quantumcore",
            "correlacion_id": "corr-001",
        },
    }
    base.update(cambios)
    return base


@pytest.fixture
def cliente(aiohttp_client):
    async def crear(registro: RegistroWorkers | None = None):
        app = crear_app(
            cargar(ENTORNO),
            obtener_tenant=_obtener_tenant,
            usuario_de_token=_usuario_de_token,
            rol_de_usuario_en_tenant=_rol,
            registro_workers_ceo=registro,
        )
        return await aiohttp_client(app)

    return crear


class TestDescripcionYConsultas:
    async def test_descripcion_correcta_y_sin_secretos(self, cliente):
        c = await cliente()
        respuesta = await c.get(
            "/v1/departamentos/fabrica-de-agentes/descripcion", headers=_cabeceras()
        )
        assert respuesta.status == 200
        datos = await respuesta.json()
        assert datos["codigo"] == "fabrica-de-agentes"
        assert datos["nombre"] == "Fábrica de Agentes"
        assert datos["prefijo_rama_autorizado"] == "quantumcore/"
        assert datos["version_contrato"] == "1.0"
        crudo = json.dumps(datos)
        assert TOKEN_QUANTUMCORE not in crudo
        assert "gsk_falsa" not in crudo

    async def test_consulta_autorizada_es_solo_lectura(self, cliente):
        c = await cliente()
        respuesta = await c.post(
            "/v1/consultas", json={"tipo": "arquitectura"}, headers=_cabeceras()
        )
        datos = await respuesta.json()
        assert respuesta.status == 200
        assert datos["solo_lectura"] is True
        assert "QuantumCore" in datos["resultado"]["flujo"]

    async def test_consulta_devuelve_correlacion_sin_modificar_estado(self, cliente):
        c = await cliente()
        respuesta = await c.post(
            "/v1/consultas",
            json={"tipo": "salud", "correlacion_id": "corr-lectura-001"},
            headers=_cabeceras(),
        )
        datos = await respuesta.json()
        assert respuesta.status == 200
        assert datos["solo_lectura"] is True
        assert datos["correlacion_id"] == "corr-lectura-001"

    async def test_consulta_sin_autenticacion_se_rechaza(self, cliente):
        c = await cliente()
        respuesta = await c.post("/v1/consultas", json={"tipo": "salud"})
        assert respuesta.status == 401
        assert (await respuesta.json())["error"]["codigo"] == "autenticacion_requerida"

    async def test_consulta_del_tenant_exige_identidad_y_membresia(self, cliente):
        c = await cliente()
        sin_actor = await c.post(
            "/v1/consultas",
            json={"tipo": "tenant", "tenant": "negocio-a"},
            headers=_cabeceras(),
        )
        assert sin_actor.status == 401

        cruzada = await c.post(
            "/v1/consultas",
            json={"tipo": "tenant", "tenant": "negocio-b"},
            headers=_cabeceras(actor="sesion-a"),
        )
        assert cruzada.status == 403
        assert (await cruzada.json())["error"]["codigo"] == "tenant_no_autorizado"

        propia = await c.post(
            "/v1/consultas",
            json={"tipo": "tenant", "tenant": "negocio-a"},
            headers=_cabeceras(actor="sesion-a"),
        )
        assert propia.status == 200
        datos = (await propia.json())["resultado"]
        assert datos == {
            "id": "id-negocio-a",
            "slug": "negocio-a",
            "nombre": "Negocio A",
            "idioma": "es",
            "estado": "activo",
        }

    @pytest.mark.parametrize("tenant", ["desconocido", "inactivo"])
    async def test_tenant_inactivo_o_desconocido_se_rechaza(self, cliente, tenant):
        c = await cliente()
        respuesta = await c.post(
            "/v1/consultas",
            json={"tipo": "tenant", "tenant": tenant},
            headers=_cabeceras(actor="sesion-a"),
        )
        assert respuesta.status == 404
        assert (await respuesta.json())["error"]["codigo"] == "tenant_inactivo_o_desconocido"

    async def test_consulta_no_acepta_comandos(self, cliente):
        c = await cliente()
        respuesta = await c.post(
            "/v1/consultas",
            json={"tipo": "salud", "comando": "quien-soy"},
            headers=_cabeceras(),
        )
        assert respuesta.status == 422
        assert (await respuesta.json())["error"]["codigo"] == "codigo_dinamico_prohibido"


class TestAcciones:
    async def test_accion_valida_llega_al_worker_autorizado(self, cliente):
        recibidas = []

        async def worker(solicitud):
            recibidas.append(solicitud)
            return {
                "resumen": "Cambio terminado.",
                "archivos_modificados": ["tests/test_nuevo.py"],
                "pruebas_ejecutadas": ["uv run pytest -q"],
                "pruebas_ok": True,
                "resultado_pruebas": "1 passed",
                "evidencia": [{"tipo": "test", "resultado": "ok"}],
                "tokens": {"entrada": 10, "salida": 5},
                "costo_usd": 0.01,
                "commit": "abc123",
            }

        registro = RegistroWorkers()
        registro.registrar("codex-local", worker)
        c = await cliente(registro)
        respuesta = await c.post(
            "/v1/acciones", json=_solicitud(), headers=_cabeceras()
        )
        datos = await respuesta.json()
        assert respuesta.status == 200
        assert datos["estado"] == "completado"
        assert datos["resultado_pruebas"] == "1 passed"
        assert len(recibidas) == 1
        assert "comando" not in recibidas[0]

    @pytest.mark.parametrize(
        ("cambio", "motivo"),
        [
            ({"departamento": "otro"}, "departamento_incorrecto"),
            ({"repositorio": r"C:\otro"}, "repositorio_incorrecto"),
            ({"rama": "feature/no"}, "rama_no_autorizada"),
            ({"rama": "main"}, "rama_no_autorizada"),
            ({"worker": "worker-libre"}, "worker_no_permitido"),
            ({"cerebro": "desconocido"}, "cerebro_no_permitido"),
            ({"modelo": "modelo-no-admitido"}, "modelo_no_permitido"),
            ({"presupuesto_maximo_usd": 99}, "presupuesto_maximo_excedido"),
            ({"tiempo_maximo_segundos": 9999}, "tiempo_maximo_excedido"),
            ({"rutas": [r"C:\Windows\System32"]}, "ruta_fuera_del_checkout"),
            ({"herramientas_permitidas": ["shell"]}, "herramienta_prohibida"),
            ({"comando": "borrar-todo"}, "codigo_o_comando_dinamico_prohibido"),
        ],
    )
    async def test_rechazos_ocurren_antes_del_worker(self, cliente, cambio, motivo):
        llamadas = 0

        async def worker(solicitud):
            nonlocal llamadas
            llamadas += 1
            return {"resumen": "no deberia ejecutarse"}

        registro = RegistroWorkers()
        registro.registrar("codex-local", worker)
        c = await cliente(registro)
        respuesta = await c.post(
            "/v1/acciones", json=_solicitud(**cambio), headers=_cabeceras()
        )
        datos = await respuesta.json()
        assert respuesta.status == 422
        assert datos["estado"] == "rechazado"
        assert datos["motivo"] == motivo
        assert llamadas == 0

    async def test_accion_de_tenant_no_cruza_membresias(self, cliente):
        registro = RegistroWorkers()

        async def worker(solicitud):
            return {"resumen": "ok", "pruebas_ok": True}

        registro.registrar("codex-local", worker)
        c = await cliente(registro)
        respuesta = await c.post(
            "/v1/acciones",
            json=_solicitud(tenant="negocio-b"),
            headers=_cabeceras(actor="sesion-a"),
        )
        assert respuesta.status == 403

    async def test_accion_de_tenant_ata_identidad_y_tenant_validados(self, cliente):
        recibida = None

        async def worker(solicitud):
            nonlocal recibida
            recibida = solicitud
            return {"resumen": "ok", "pruebas_ok": True}

        registro = RegistroWorkers()
        registro.registrar("codex-local", worker)
        c = await cliente(registro)
        respuesta = await c.post(
            "/v1/acciones",
            json=_solicitud(tenant="negocio-a"),
            headers=_cabeceras(actor="sesion-a"),
        )
        assert respuesta.status == 200
        assert recibida["tenant"] == "negocio-a"
        assert recibida["auditoria"]["tenant_id"] == "id-negocio-a"
        assert recibida["auditoria"]["solicitado_por"] == "usuario-a"

    async def test_modelo_directo_no_puede_editar_ni_usar_git(self, cliente):
        c = await cliente()
        solicitud = _solicitud(
            tipo_trabajo="actualizar_documentacion",
            worker="modelo-directo",
            cerebro="openai",
            modelo="gpt-seleccionado",
            herramientas_permitidas=["editar_archivos"],
        )
        respuesta = await c.post(
            "/v1/acciones", json=solicitud, headers=_cabeceras()
        )
        assert respuesta.status == 422
        assert (await respuesta.json())["motivo"] == "herramienta_no_autorizada"

    async def test_idempotencia_no_ejecuta_dos_veces(self, cliente):
        llamadas = 0

        async def worker(solicitud):
            nonlocal llamadas
            llamadas += 1
            return {"resumen": "ok", "pruebas_ok": True}

        registro = RegistroWorkers()
        registro.registrar("codex-local", worker)
        c = await cliente(registro)
        primera = await c.post("/v1/acciones", json=_solicitud(), headers=_cabeceras())
        segunda = await c.post("/v1/acciones", json=_solicitud(), headers=_cabeceras())
        assert primera.status == 200
        assert segunda.status == 200
        assert (await segunda.json())["idempotente_repetido"] is True
        assert llamadas == 1

    async def test_misma_clave_con_otro_trabajo_se_rechaza(self, cliente):
        async def worker(solicitud):
            return {"resumen": "ok", "pruebas_ok": True}

        registro = RegistroWorkers()
        registro.registrar("codex-local", worker)
        c = await cliente(registro)
        await c.post("/v1/acciones", json=_solicitud(), headers=_cabeceras())
        conflicto = await c.post(
            "/v1/acciones",
            json=_solicitud(trabajo_id="trabajo-otro"),
            headers=_cabeceras(),
        )
        assert conflicto.status == 422
        assert (await conflicto.json())["motivo"] == "idempotencia_conflictiva"

    async def test_error_del_worker_es_estructurado(self, cliente):
        async def worker(solicitud):
            raise RuntimeError("detalle privado")

        registro = RegistroWorkers()
        registro.registrar("codex-local", worker)
        c = await cliente(registro)
        respuesta = await c.post(
            "/v1/acciones", json=_solicitud(), headers=_cabeceras()
        )
        datos = await respuesta.json()
        assert respuesta.status == 500
        assert datos["estado"] == "error"
        assert datos["motivo"] == "error_del_worker"
        assert "detalle privado" not in json.dumps(datos)

    async def test_secretos_del_worker_se_redactan(self, cliente, caplog):
        async def worker(solicitud):
            return {
                "resumen": f"el valor era {TOKEN_QUANTUMCORE}",
                "pruebas_ok": True,
                "api_key": "otra-clave-privada",
                "evidencia": [{"authorization": TOKEN_QUANTUMCORE}],
            }

        registro = RegistroWorkers()
        registro.registrar("codex-local", worker)
        c = await cliente(registro)
        respuesta = await c.post(
            "/v1/acciones", json=_solicitud(), headers=_cabeceras()
        )
        crudo = json.dumps(await respuesta.json())
        assert TOKEN_QUANTUMCORE not in crudo
        assert "otra-clave-privada" not in crudo
        assert TOKEN_QUANTUMCORE not in caplog.text

    async def test_prueba_fallida_impide_declarar_exito(self, cliente):
        async def worker(solicitud):
            return {
                "resumen": "La prueba fallo.",
                "pruebas_ejecutadas": ["uv run pytest -q"],
                "pruebas_ok": False,
                "resultado_pruebas": "1 failed",
            }

        registro = RegistroWorkers()
        registro.registrar("codex-local", worker)
        c = await cliente(registro)
        respuesta = await c.post(
            "/v1/acciones", json=_solicitud(), headers=_cabeceras()
        )
        datos = await respuesta.json()
        assert respuesta.status == 500
        assert datos["estado"] == "error"
        assert datos["motivo"] == "pruebas_fallidas"
