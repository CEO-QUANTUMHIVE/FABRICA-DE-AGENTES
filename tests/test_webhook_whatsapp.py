"""El webhook es publico: cualquiera puede hacerle POST.

Lo que se prueba aca es que un pedido sin firma no llega a la base, que la
cuenta receptora es la unica que decide el tenant, y que Meta nunca recibe
algo que la haga reintentar para siempre.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from motor_voz import config as config_mod
from motor_voz.api import servidor
from motor_voz.brain.mensajes import CanalTenant, ResultadoIngreso

SECRETO = "app-secret"
VERIFY = "token-que-invente-yo"
CUENTA = "111222333"


def _config(**cambios):
    entorno = {
        "GROQ_API_KEY": "x",
        "FISH_API_KEY": "x",
        "LIVEKIT_URL": "wss://ejemplo",
        "LIVEKIT_API_KEY": "x",
        "LIVEKIT_API_SECRET": "x",
        "SUPABASE_URL": "https://ejemplo.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "x",
        "META_APP_SECRET": SECRETO,
        "WHATSAPP_VERIFY_TOKEN": VERIFY,
    }
    entorno.update(cambios)
    return config_mod.cargar(entorno)


def _cuerpo(cuenta: str = CUENTA, mensaje_id: str = "wamid.A") -> bytes:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": cuenta},
                            "contacts": [
                                {"profile": {"name": "Jaz"}, "wa_id": "549351000"}
                            ],
                            "messages": [
                                {
                                    "from": "549351000",
                                    "id": mensaje_id,
                                    "timestamp": "1755200000",
                                    "type": "text",
                                    "text": {"body": "hola"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    return json.dumps(payload).encode()


def _firma(cuerpo: bytes, secreto: str = SECRETO) -> str:
    return "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


class _Espia:
    """Reemplaza al repositorio: registra que se le pidio y que devolvio."""

    def __init__(self, canal: CanalTenant | None = None, duplicado: bool = False):
        self.canal = canal or CanalTenant(
            id="canal-1",
            tenant_id="tenant-quantumhive",
            canal="whatsapp",
            cuenta_externa_id=CUENTA,
            nombre="QuantumHive",
            estado="conectado",
        )
        self.duplicado = duplicado
        self.cuentas_consultadas: list[str] = []
        self.ingresados: list = []

    async def canal_de_cuenta(self, config, *, canal, cuenta_externa_id):
        self.cuentas_consultadas.append(cuenta_externa_id)
        if cuenta_externa_id != self.canal.cuenta_externa_id:
            from motor_voz.brain.tenants.repositorio import CanalNoEncontrado

            raise CanalNoEncontrado("no hay canal para esa cuenta")
        return self.canal

    async def registrar_mensaje_entrante(self, config, *, tenant_canal_id, mensaje):
        self.ingresados.append(mensaje)
        return ResultadoIngreso(duplicado=self.duplicado, inbox_id="inbox-1")


@pytest.fixture
def espia():
    return _Espia()


@pytest.fixture
async def cliente(aiohttp_client, espia):
    app = servidor.crear_app(
        _config(),
        obtener_tenant=_sin_uso,
        canal_de_cuenta=espia.canal_de_cuenta,
        registrar_mensaje_entrante=espia.registrar_mensaje_entrante,
    )
    return await aiohttp_client(app)


async def _sin_uso(*args, **kwargs):
    raise AssertionError("este test no deberia resolver un tenant por slug")


# --- GET: la verificacion de Meta ---------------------------------------


async def test_meta_verifica_el_webhook_con_el_challenge(cliente):
    r = await cliente.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY,
            "hub.challenge": "12345",
        },
    )

    assert r.status == 200
    assert await r.text() == "12345"


async def test_un_verify_token_distinto_no_verifica_nada(cliente):
    r = await cliente.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "adivinado",
            "hub.challenge": "12345",
        },
    )

    assert r.status == 403


async def test_sin_verify_token_configurado_no_se_verifica(aiohttp_client, espia):
    """Falla cerrado: un token vacio no puede coincidir con un pedido vacio."""
    app = servidor.crear_app(
        _config(WHATSAPP_VERIFY_TOKEN=""),
        obtener_tenant=_sin_uso,
        canal_de_cuenta=espia.canal_de_cuenta,
        registrar_mensaje_entrante=espia.registrar_mensaje_entrante,
    )
    cliente = await aiohttp_client(app)

    r = await cliente.get(
        "/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "1"},
    )

    assert r.status == 403


# --- POST: la recepcion --------------------------------------------------


async def test_un_mensaje_firmado_se_persiste(cliente, espia):
    cuerpo = _cuerpo()

    r = await cliente.post(
        "/webhooks/whatsapp", data=cuerpo, headers={"X-Hub-Signature-256": _firma(cuerpo)}
    )

    assert r.status == 200
    assert len(espia.ingresados) == 1
    mensaje = espia.ingresados[0]
    assert mensaje.tenant_id == "tenant-quantumhive"
    assert mensaje.texto == "hola"
    assert mensaje.canal == "whatsapp"


async def test_sin_firma_no_se_toca_la_base(cliente, espia):
    r = await cliente.post("/webhooks/whatsapp", data=_cuerpo())

    assert r.status == 403
    assert espia.ingresados == []
    assert espia.cuentas_consultadas == []


async def test_una_firma_de_otro_secreto_no_pasa(cliente, espia):
    cuerpo = _cuerpo()

    r = await cliente.post(
        "/webhooks/whatsapp",
        data=cuerpo,
        headers={"X-Hub-Signature-256": _firma(cuerpo, "otro")},
    )

    assert r.status == 403
    assert espia.ingresados == []


async def test_el_tenant_sale_de_la_cuenta_receptora_y_de_nada_mas(cliente, espia):
    """Aunque el payload traiga un tenant escrito adentro."""
    payload = json.loads(_cuerpo())
    payload["tenant"] = "demo_capilar"
    payload["entry"][0]["changes"][0]["value"]["tenant_id"] = "demo_capilar"
    cuerpo = json.dumps(payload).encode()

    r = await cliente.post(
        "/webhooks/whatsapp", data=cuerpo, headers={"X-Hub-Signature-256": _firma(cuerpo)}
    )

    assert r.status == 200
    assert espia.cuentas_consultadas == [CUENTA]
    assert espia.ingresados[0].tenant_id == "tenant-quantumhive"


async def test_una_cuenta_desconocida_responde_200_y_no_persiste(cliente, espia):
    """404 haria que Meta reintente el mismo evento para siempre."""
    cuerpo = _cuerpo(cuenta="999-no-existe")

    r = await cliente.post(
        "/webhooks/whatsapp", data=cuerpo, headers={"X-Hub-Signature-256": _firma(cuerpo)}
    )

    assert r.status == 200
    assert espia.ingresados == []


async def test_un_evento_repetido_responde_200_sin_duplicar(aiohttp_client):
    espia = _Espia(duplicado=True)
    app = servidor.crear_app(
        _config(),
        obtener_tenant=_sin_uso,
        canal_de_cuenta=espia.canal_de_cuenta,
        registrar_mensaje_entrante=espia.registrar_mensaje_entrante,
    )
    cliente = await aiohttp_client(app)
    cuerpo = _cuerpo()

    r = await cliente.post(
        "/webhooks/whatsapp", data=cuerpo, headers={"X-Hub-Signature-256": _firma(cuerpo)}
    )

    assert r.status == 200


async def test_un_webhook_de_estados_responde_200_sin_hacer_nada(cliente, espia):
    payload = json.loads(_cuerpo())
    valor = payload["entry"][0]["changes"][0]["value"]
    del valor["messages"]
    valor["statuses"] = [{"id": "wamid.A", "status": "delivered"}]
    cuerpo = json.dumps(payload).encode()

    r = await cliente.post(
        "/webhooks/whatsapp", data=cuerpo, headers={"X-Hub-Signature-256": _firma(cuerpo)}
    )

    assert r.status == 200
    assert espia.ingresados == []


async def test_un_cuerpo_que_no_es_json_responde_200(cliente, espia):
    cuerpo = b"esto no es json"

    r = await cliente.post(
        "/webhooks/whatsapp", data=cuerpo, headers={"X-Hub-Signature-256": _firma(cuerpo)}
    )

    assert r.status == 200
    assert espia.ingresados == []


async def test_si_la_base_falla_se_devuelve_500_para_que_meta_reintente(
    aiohttp_client, espia
):
    """El unico caso donde SI queremos el reintento: el mensaje es valido y
    lo perdimos por un problema nuestro."""

    async def explota(config, *, tenant_canal_id, mensaje):
        raise RuntimeError("supabase caido")

    app = servidor.crear_app(
        _config(),
        obtener_tenant=_sin_uso,
        canal_de_cuenta=espia.canal_de_cuenta,
        registrar_mensaje_entrante=explota,
    )
    cliente = await aiohttp_client(app)
    cuerpo = _cuerpo()

    r = await cliente.post(
        "/webhooks/whatsapp", data=cuerpo, headers={"X-Hub-Signature-256": _firma(cuerpo)}
    )

    assert r.status == 500
