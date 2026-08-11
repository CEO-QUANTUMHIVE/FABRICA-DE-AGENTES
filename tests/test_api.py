"""La API que emite los tokens de la demo publica.

Lo critico aca es que el navegador NO pueda elegir el motor por su cuenta:
el plan premium cuesta mas y cualquiera podria pedirlo desde la consola.
"""

import json

import pytest

from motor_voz.api import niveles
from motor_voz.api.limites import LimiteAlcanzado, Limitador
from motor_voz.api.servidor import crear_app
from motor_voz.brain.tenants.modelos import DominioTenant, PerfilTenant, Tenant
from motor_voz.brain.tenants.repositorio import TenantNoEncontrado
from motor_voz.config import ConfigInvalida, cargar
from motor_voz.voice import motores

ENTORNO = {
    "GROQ_API_KEY": "gsk_falsa",
    "FISH_API_KEY": "sk-falsa",
    "LIVEKIT_URL": "ws://localhost:7880",
    "LIVEKIT_API_KEY": "devkey",
    "LIVEKIT_API_SECRET": "secreto-largo-de-prueba-1234567890",
    # Casi todos los tests prueban el camino de desarrollo, donde el tenant se
    # puede pedir por el cuerpo. El de produccion tiene su propia clase.
    "ENVIRONMENT": "desarrollo",
}


def _tenant(slug, nombre):
    return Tenant(
        id=f"id-{slug}", slug=slug, nombre=nombre, idioma="es",
        perfil=PerfilTenant(slug="receptor", nombre="Receptor", prompt_base=f"Soy {nombre}."),
        prompt_propio="", servicios=(), voz=None,
    )


TENANTS = {"quantumhive": _tenant("quantumhive", "QuantumHive"),
           "demo_capilar": _tenant("demo_capilar", "Barberia Demo")}

# Que dominio es de quien. En la realidad esto vive en tenant_dominios.
# El tercero es un host propio de demos: hospeda varios rubros, asi que la
# pagina puede decir cual quiere.
DOMINIOS = {
    "www.quantumhive.com.ar": DominioTenant("quantumhive", puede_declarar=False),
    "pelo-duro.com.ar": DominioTenant("demo_capilar", puede_declarar=False),
    "demos.quantumhive.com.ar": DominioTenant("demo_capilar", puede_declarar=True),
}


async def _tenant_falso(config, slug):
    """El tenant se inyecta para que la suite no dependa de Supabase."""
    if slug not in TENANTS:
        raise TenantNoEncontrado(f"no existe el tenant '{slug}'")
    return TENANTS[slug]


async def _dominio_falso(config, dominio):
    return DOMINIOS.get(dominio)


@pytest.fixture
def cliente(aiohttp_client):
    async def _crear(**extra):
        obtener_tenant = extra.pop("obtener_tenant", _tenant_falso)
        tenant_de_dominio = extra.pop("tenant_de_dominio", _dominio_falso)
        return await aiohttp_client(
            crear_app(
                cargar(ENTORNO | extra),
                obtener_tenant=obtener_tenant,
                tenant_de_dominio=tenant_de_dominio,
            )
        )
    return _crear


class TestNiveles:
    def test_hay_exactamente_tres(self):
        assert sorted(niveles.NIVELES) == [1, 2, 3]

    def test_cada_nivel_apunta_a_un_motor_distinto(self):
        motores = [n.motor for n in niveles.NIVELES.values()]
        assert motores == ["pipeline", "gemini", "openai"]
        assert len(set(motores)) == 3

    @pytest.mark.parametrize("malo", [0, 4, -1, "premium", None, "2; DROP TABLE"])
    def test_rechaza_niveles_invalidos(self, malo):
        with pytest.raises(niveles.NivelInvalido):
            niveles.resolver(malo)

    def test_acepta_el_nivel_como_texto(self):
        """El navegador manda JSON; un "2" no deberia romper."""
        assert niveles.resolver("2").motor == "gemini"


class TestLimitador:
    def test_nunca_limita_desde_la_maquina_propia(self):
        """Un limite que te frena mientras desarrollas termina borrado."""
        lim = Limitador(por_ip_hora=1, por_dia=1)
        for _ in range(50):
            lim.registrar("127.0.0.1")
            lim.registrar("192.168.1.40")

    def test_corta_por_ip_a_la_hora(self):
        lim = Limitador(por_ip_hora=2, por_dia=100)
        lim.registrar("1.1.1.1", ahora=0)
        lim.registrar("1.1.1.1", ahora=1)
        with pytest.raises(LimiteAlcanzado):
            lim.registrar("1.1.1.1", ahora=2)

    def test_otra_ip_no_se_ve_afectada(self):
        lim = Limitador(por_ip_hora=1, por_dia=100)
        lim.registrar("1.1.1.1", ahora=0)
        lim.registrar("2.2.2.2", ahora=0)

    def test_la_ventana_se_libera_pasada_la_hora(self):
        lim = Limitador(por_ip_hora=1, por_dia=100)
        lim.registrar("1.1.1.1", ahora=0)
        lim.registrar("1.1.1.1", ahora=3_601)

    def test_el_tope_diario_manda_sobre_el_de_ip(self):
        """Es el que protege la factura: no importa de que IP vengan."""
        lim = Limitador(por_ip_hora=100, por_dia=2)
        lim.registrar("1.1.1.1", ahora=0)
        lim.registrar("2.2.2.2", ahora=0)
        with pytest.raises(LimiteAlcanzado):
            lim.registrar("3.3.3.3", ahora=0)


class TestEndpoints:
    async def test_salud_responde(self, cliente):
        c = await cliente()
        r = await c.get("/api/salud")
        assert r.status == 200
        assert (await r.json())["estado"] == "ok"

    async def test_lista_los_tres_niveles(self, cliente):
        c = await cliente()
        d = await (await c.get("/api/niveles")).json()
        assert len(d["niveles"]) == 3
        assert {n["plan"] for n in d["niveles"]} == {"basico", "medio", "premium"}

    async def test_emite_un_token_valido(self, cliente):
        c = await cliente()
        r = await c.post("/api/token", json={"nivel": 1})
        d = await r.json()
        assert r.status == 200
        assert d["token"].startswith("eyJ")
        assert d["url"] == "ws://localhost:7880"

    async def test_el_motor_va_en_el_nombre_de_la_sala(self, cliente):
        """Asi lo lee el agente, y el token restringe a que sala se entra."""
        c = await cliente()
        for nivel, motor in [(1, "pipeline"), (2, "gemini"), (3, "openai")]:
            d = await (await c.post("/api/token", json={"nivel": nivel})).json()
            # demo-<tenant>-<motor>-<voz>-<aleatorio>
            assert d["sala"].startswith(f"demo-quantumhive-{motor}-")
            assert d["sala"].split("-")[3] == d["voz"]

    async def test_cada_sesion_usa_una_sala_distinta(self, cliente):
        c = await cliente()
        a = await (await c.post("/api/token", json={"nivel": 1})).json()
        b = await (await c.post("/api/token", json={"nivel": 1})).json()
        assert a["sala"] != b["sala"], "Dos visitantes no pueden caer en la misma sala"

    async def test_un_nivel_invalido_da_400(self, cliente):
        c = await cliente()
        r = await c.post("/api/token", json={"nivel": 99})
        assert r.status == 400

    async def test_cuerpo_vacio_cae_al_nivel_basico(self, cliente):
        """Nadie termina en el plan premium por un request mal armado."""
        c = await cliente()
        d = await (await c.post("/api/token", data="no es json")).json()
        assert d["nivel"] == 1

    async def test_al_pasarse_del_limite_responde_429(self, cliente):
        """Se simula una IP publica: desde localhost no se limita nunca."""
        c = await cliente(MAX_SESSIONS_PER_IP_HOUR="1")
        visitante = {"X-Forwarded-For": "200.1.2.3"}
        assert (await c.post("/api/token", json={"nivel": 1}, headers=visitante)).status == 200
        r = await c.post("/api/token", json={"nivel": 1}, headers=visitante)
        assert r.status == 429
        assert "error" in await r.json()

    async def test_desde_localhost_no_se_limita(self, cliente):
        """Probar la demo en tu propia maquina no puede bloquearte."""
        c = await cliente(MAX_SESSIONS_PER_IP_HOUR="1")
        for _ in range(5):
            assert (await c.post("/api/token", json={"nivel": 1})).status == 200

    async def test_el_token_nunca_lleva_las_claves_de_los_proveedores(self, cliente):
        c = await cliente()
        crudo = await (await c.post("/api/token", json={"nivel": 3})).text()
        for secreto in ("gsk_falsa", "sk-falsa", "secreto-largo-de-prueba"):
            assert secreto not in crudo

    async def test_responde_con_cors(self, cliente):
        c = await cliente()
        r = await c.get("/api/niveles")
        assert r.headers.get("Access-Control-Allow-Origin") == "*"


class TestVoces:
    async def test_lista_las_voces_de_gemini(self, cliente):
        c = await cliente()
        d = await (await c.get("/api/voces?motor=gemini")).json()
        assert {v["voz"] for v in d["voces"]} == set(motores.VOCES_GEMINI)

    async def test_lista_las_diez_voces_de_openai(self, cliente):
        c = await cliente()
        d = await (await c.get("/api/voces?motor=openai")).json()
        assert len(d["voces"]) == 10
        assert all({"voz", "nombre"} <= set(v) for v in d["voces"])

    async def test_cada_voz_trae_la_ruta_de_su_saludo_pregrabado(self, cliente):
        """Sin `muestra`, el widget vuelve a reconectar para preescuchar y se paga."""
        c = await cliente()
        for motor in ("gemini", "openai"):
            d = await (await c.get(f"/api/voces?motor={motor}")).json()
            for v in d["voces"]:
                assert v["muestra"] == motores.ruta_de_muestra(motor, v["voz"])

    async def test_el_pipeline_no_tiene_voces_pero_responde_200(self, cliente):
        """Ni error ni 404: el frontend puede pedir sin fijarse el motor."""
        c = await cliente()
        r = await c.get("/api/voces?motor=pipeline")
        assert r.status == 200
        assert (await r.json())["voces"] == []

    async def test_sin_parametro_motor_asume_gemini(self, cliente):
        """Compatibilidad con el selector viejo, que solo conocia gemini."""
        c = await cliente()
        d = await (await c.get("/api/voces")).json()
        assert {v["voz"] for v in d["voces"]} == set(motores.VOCES_GEMINI)

    async def test_pedir_el_nivel_3_con_una_voz_de_gemini_da_400(self, cliente):
        """Los catalogos de gemini y openai son distintos: no se cruzan."""
        c = await cliente()
        r = await c.post("/api/token", json={"nivel": 3, "voz": "Puck"})
        assert r.status == 400

    async def test_pedir_el_nivel_3_con_una_voz_valida_de_openai_funciona(self, cliente):
        c = await cliente()
        r = await c.post("/api/token", json={"nivel": 3, "voz": "coral"})
        d = await r.json()
        assert r.status == 200
        assert d["voz"] == "coral"
        assert d["nombre_voz"] == motores.VOCES_OPENAI["coral"].nombre
        assert "-coral-" in d["sala"]

    async def test_el_nivel_1_ignora_la_voz_y_la_deja_vacia(self, cliente):
        """El pipeline no tiene catalogo: lo que mande el cliente se descarta."""
        c = await cliente()
        r = await c.post("/api/token", json={"nivel": 1, "voz": "cualquiera"})
        d = await r.json()
        assert r.status == 200
        assert d["voz"] == ""
        assert d["nombre_voz"] == ""
        assert d["sala"].startswith("demo-quantumhive-pipeline--")


class TestTenant:
    """El tenant se resuelve en el backend y viaja firmado, como el motor."""

    async def test_por_defecto_usa_quantumhive(self, cliente):
        c = await cliente()
        d = await (await c.post("/api/token", json={"nivel": 1})).json()
        assert d["tenant"] == "quantumhive"

    async def test_tenant_inexistente_da_404(self, cliente):
        c = await cliente()
        r = await c.post("/api/token", json={"nivel": 1, "tenant": "no-existe"})
        assert r.status == 404

    async def test_supabase_caido_da_503_no_500(self, cliente):
        """Que se caiga la base no es culpa del que pide: 503 e invita a reintentar."""

        async def _falla(config, slug):
            raise RuntimeError("timeout de red")

        c = await cliente(obtener_tenant=_falla)
        r = await c.post("/api/token", json={"nivel": 1})
        assert r.status == 503

    async def test_el_tenant_va_en_la_metadata_firmada(self, cliente):
        """El agente lo lee de aca, no de lo que diga el navegador."""
        import base64
        import json as jsonlib

        c = await cliente()
        d = await (await c.post("/api/token", json={"nivel": 1})).json()
        payload = d["token"].split(".")[1]
        while len(payload) % 4:
            payload += "="
        claims = jsonlib.loads(base64.urlsafe_b64decode(payload))
        metadata = jsonlib.loads(claims["metadata"])
        assert metadata["tenant"] == "quantumhive"


class TestCredencialesDeSupabase:
    """Sin credenciales no hay token, asi que no se arranca sin ellas."""

    def test_acepta_el_nombre_nuevo_de_la_clave(self):
        """Supabase renombro service_role a secret key. La VM tiene solo el
        nuevo; el .env local, los dos. Aceptar uno solo rompia produccion."""
        c = cargar(ENTORNO | {"SUPABASE_SECRET_KEY": "sb_secret_loquesea"})
        assert c.supabase_service_role_key == "sb_secret_loquesea"

    def test_el_nombre_viejo_le_gana_al_nuevo(self):
        c = cargar(
            ENTORNO
            | {"SUPABASE_SERVICE_ROLE_KEY": "la-vieja", "SUPABASE_SECRET_KEY": "la-nueva"}
        )
        assert c.supabase_service_role_key == "la-vieja"

    def test_no_arranca_sin_credenciales_en_vez_de_dar_503_siempre(self):
        """El modo silencioso era el peligroso: arrancaba y no atendia a nadie."""
        with pytest.raises(ConfigInvalida) as e:
            crear_app(cargar(ENTORNO))
        assert "SUPABASE" in str(e.value)

    def test_con_credenciales_arranca(self):
        app = crear_app(
            cargar(ENTORNO | {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SECRET_KEY": "k"})
        )
        assert app["config"].supabase_service_role_key == "k"


class TestElDominioMandaSobreElTenant:
    """Nadie se lleva el agente de otro negocio pidiendolo por nombre.

    El Origin lo pone el navegador y el codigo de una pagina no lo puede
    cambiar, asi que una landing solo puede invocar al agente de su dueño.
    """

    async def test_el_dominio_registrado_define_el_tenant(self, cliente):
        c = await cliente()
        r = await c.post(
            "/api/token", json={"nivel": 1}, headers={"Origin": "https://pelo-duro.com.ar"}
        )
        assert (await r.json())["tenant"] == "demo_capilar"

    async def test_el_dominio_le_gana_al_cuerpo(self, cliente):
        """Aunque pidas otro negocio por el cuerpo, manda de donde venis."""
        c = await cliente()
        r = await c.post(
            "/api/token",
            json={"nivel": 1, "tenant": "demo_capilar"},
            headers={"Origin": "https://www.quantumhive.com.ar"},
        )
        assert (await r.json())["tenant"] == "quantumhive"

    async def test_un_host_de_demos_si_puede_declarar_el_rubro(self, cliente):
        """Nuestros sitios de demos hospedan varios rubros en un solo host y
        el Origin no distingue la pagina: ahi la pagina elige."""
        c = await cliente()
        r = await c.post(
            "/api/token",
            json={"nivel": 1, "tenant": "quantumhive"},
            headers={"Origin": "https://demos.quantumhive.com.ar"},
        )
        assert (await r.json())["tenant"] == "quantumhive"

    async def test_un_host_de_demos_sin_declarar_usa_el_suyo(self, cliente):
        c = await cliente()
        r = await c.post(
            "/api/token", json={"nivel": 1}, headers={"Origin": "https://demos.quantumhive.com.ar"}
        )
        assert (await r.json())["tenant"] == "demo_capilar"

    async def test_el_permiso_de_declarar_no_lo_hereda_un_dominio_de_cliente(self, cliente):
        """Lo que separa un host de demos de la landing de un cliente."""
        c = await cliente()
        r = await c.post(
            "/api/token",
            json={"nivel": 1, "tenant": "quantumhive"},
            headers={"Origin": "https://pelo-duro.com.ar"},
        )
        assert (await r.json())["tenant"] == "demo_capilar"

    async def test_el_puerto_no_rompe_el_dominio(self, cliente):
        """Solo se compara el host: el Origin trae protocolo y a veces puerto."""
        c = await cliente()
        r = await c.post(
            "/api/token", json={"nivel": 1}, headers={"Origin": "https://pelo-duro.com.ar:443"}
        )
        assert (await r.json())["tenant"] == "demo_capilar"

    async def test_un_dominio_desconocido_cae_a_nuestro_agente(self, cliente):
        """Una landing sin registrar no se lleva el agente de nadie."""
        c = await cliente()
        r = await c.post(
            "/api/token", json={"nivel": 1}, headers={"Origin": "https://sitio-cualquiera.com"}
        )
        assert (await r.json())["tenant"] == "quantumhive"

    async def test_en_produccion_el_cuerpo_no_puede_elegir_tenant(self, cliente):
        """El agujero que esto cierra: un curl con el slug de otro negocio."""
        c = await cliente(ENVIRONMENT="produccion")
        r = await c.post("/api/token", json={"nivel": 1, "tenant": "demo_capilar"})
        assert (await r.json())["tenant"] == "quantumhive"

    async def test_fuera_de_produccion_el_cuerpo_sirve_para_probar(self, cliente):
        """Sin esto no se puede validar el aislamiento a oido en local."""
        c = await cliente()
        r = await c.post("/api/token", json={"nivel": 1, "tenant": "demo_capilar"})
        assert (await r.json())["tenant"] == "demo_capilar"

    async def test_el_default_es_produccion(self):
        """Aflojar el aislamiento tiene que ser deliberado, no un olvido."""
        sin_declarar = {k: v for k, v in ENTORNO.items() if k != "ENVIRONMENT"}
        assert cargar(sin_declarar).entorno == "produccion"

    @pytest.mark.parametrize("valor", ["production", "prod", "staging", "", "PRODUCCION "])
    async def test_cualquier_entorno_raro_se_comporta_como_produccion(self, cliente, valor):
        """Falla cerrado: el .env local dice development y el de la VM podria
        decir production. Comparar contra una sola palabra dejaba el agujero."""
        c = await cliente(ENVIRONMENT=valor)
        r = await c.post("/api/token", json={"nivel": 1, "tenant": "demo_capilar"})
        assert (await r.json())["tenant"] == "quantumhive"

    @pytest.mark.parametrize("valor", ["development", "desarrollo", "dev", "local", "test"])
    async def test_los_entornos_de_desarrollo_si_permiten_elegir(self, cliente, valor):
        c = await cliente(ENVIRONMENT=valor)
        r = await c.post("/api/token", json={"nivel": 1, "tenant": "demo_capilar"})
        assert (await r.json())["tenant"] == "demo_capilar"
