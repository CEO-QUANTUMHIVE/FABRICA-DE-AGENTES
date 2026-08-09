"""La API que emite los tokens de la demo publica.

Lo critico aca es que el navegador NO pueda elegir el motor por su cuenta:
el plan premium cuesta mas y cualquiera podria pedirlo desde la consola.
"""

import json

import pytest

from motor_voz.api import niveles
from motor_voz.api.limites import LimiteAlcanzado, Limitador
from motor_voz.api.servidor import crear_app
from motor_voz.config import cargar

ENTORNO = {
    "GROQ_API_KEY": "gsk_falsa",
    "FISH_API_KEY": "sk-falsa",
    "LIVEKIT_URL": "ws://localhost:7880",
    "LIVEKIT_API_KEY": "devkey",
    "LIVEKIT_API_SECRET": "secreto-largo-de-prueba-1234567890",
}


@pytest.fixture
def cliente(aiohttp_client):
    async def _crear(**extra):
        return await aiohttp_client(crear_app(cargar(ENTORNO | extra)))
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
            assert d["sala"].startswith(f"demo-{motor}-")

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
