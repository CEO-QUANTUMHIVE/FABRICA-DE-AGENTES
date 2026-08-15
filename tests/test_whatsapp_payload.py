"""El webhook de Meta llega crudo y no puede elegir el tenant.

El parser solo traduce. Quien decide de quien es el mensaje es
`repositorio.canal_de_cuenta()` mirando el numero que RECIBE, y eso pasa
despues, con el resultado de aca.
"""

from datetime import datetime, timezone

import pytest

from motor_voz.channels.whatsapp.payload import leer_webhook


def _webhook(**cambios) -> dict:
    valor = {
        "messaging_product": "whatsapp",
        "metadata": {
            "display_phone_number": "5493511234567",
            "phone_number_id": "111222333",
        },
        "contacts": [{"profile": {"name": "Jaz"}, "wa_id": "5493519999999"}],
        "messages": [
            {
                "from": "5493519999999",
                "id": "wamid.HBgLAAA=",
                "timestamp": "1755200000",
                "type": "text",
                "text": {"body": "hola"},
            }
        ],
    }
    valor.update(cambios)
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA-1", "changes": [{"value": valor, "field": "messages"}]}],
    }


def test_un_mensaje_de_texto_sale_listo_para_resolver_el_tenant():
    (entrada,) = leer_webhook(_webhook())

    assert entrada.cuenta_externa_id == "111222333"
    (mensaje,) = entrada.mensajes
    assert mensaje.texto == "hola"
    assert mensaje.tipo == "text"
    assert mensaje.soportado
    assert mensaje.remitente_externo_id == "5493519999999"
    assert mensaje.conversacion_externa_id == "5493519999999"
    assert mensaje.mensaje_externo_id == "wamid.HBgLAAA="
    assert mensaje.nombre_contacto == "Jaz"
    assert mensaje.recibido_en == datetime(2025, 8, 14, 19, 33, 20, tzinfo=timezone.utc)


def test_la_cuenta_receptora_sale_del_metadata_y_no_del_remitente():
    """Si saliera del remitente, cualquiera elegiria a que negocio escribirle."""
    entrada, = leer_webhook(_webhook())
    assert entrada.cuenta_externa_id != "5493519999999"


def test_el_tenant_se_agrega_despues_y_nunca_viene_en_el_payload():
    (entrada,) = leer_webhook(_webhook())
    (crudo,) = entrada.mensajes

    mensaje = crudo.con_tenant("tenant-quantumhive")

    assert mensaje.tenant_id == "tenant-quantumhive"
    assert mensaje.canal == "whatsapp"
    assert mensaje.clave_idempotencia == "whatsapp:wamid.HBgLAAA="


def test_un_webhook_puede_traer_varios_mensajes():
    cuerpo = _webhook(
        messages=[
            {
                "from": "549351000",
                "id": "wamid.A",
                "timestamp": "1755200000",
                "type": "text",
                "text": {"body": "hola"},
            },
            {
                "from": "549351000",
                "id": "wamid.B",
                "timestamp": "1755200005",
                "type": "text",
                "text": {"body": "que precio tienen?"},
            },
        ]
    )

    (entrada,) = leer_webhook(cuerpo)

    assert [m.mensaje_externo_id for m in entrada.mensajes] == ["wamid.A", "wamid.B"]


def test_dos_numeros_distintos_no_se_mezclan_en_una_entrada():
    """Meta puede agrupar varias cuentas. Cada una resuelve su propio tenant."""
    cuerpo = _webhook()
    otro = _webhook()
    otro["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "999888777"
    cuerpo["entry"].append(otro["entry"][0])

    entradas = leer_webhook(cuerpo)

    assert [e.cuenta_externa_id for e in entradas] == ["111222333", "999888777"]


def test_un_webhook_de_estados_no_trae_mensajes():
    """Entregado/leido llega por el mismo endpoint y no se contesta."""
    cuerpo = _webhook()
    valor = cuerpo["entry"][0]["changes"][0]["value"]
    del valor["messages"]
    valor["statuses"] = [{"id": "wamid.A", "status": "delivered"}]

    assert leer_webhook(cuerpo) == []


def test_un_tipo_no_soportado_no_se_procesa_como_texto_vacio():
    """Un audio con texto '' pasaria como mensaje en blanco y el agente
    contestaria a la nada. Se marca y el procesador avisa que solo lee texto."""
    cuerpo = _webhook(
        messages=[
            {
                "from": "549351000",
                "id": "wamid.AUDIO",
                "timestamp": "1755200000",
                "type": "audio",
                "audio": {"id": "media-1"},
            }
        ]
    )

    (entrada,) = leer_webhook(cuerpo)
    (mensaje,) = entrada.mensajes

    assert mensaje.tipo == "audio"
    assert not mensaje.soportado
    assert mensaje.texto == ""


def test_el_evento_se_deduplica_por_mensaje():
    """La restriccion del inbox es (canal, evento_externo_id): si Meta reintenta
    el mismo webhook, el evento tiene que coincidir para no contestar dos veces."""
    (entrada,) = leer_webhook(_webhook())
    (mensaje,) = entrada.mensajes
    (repetido,) = leer_webhook(_webhook())[0].mensajes

    assert mensaje.evento_externo_id == repetido.evento_externo_id
    assert "wamid.HBgLAAA=" in mensaje.evento_externo_id


@pytest.mark.parametrize(
    "cuerpo",
    [
        {},
        {"entry": []},
        {"entry": [{"changes": []}]},
        {"entry": [{"changes": [{"value": {}}]}]},
        {"entry": "no es una lista"},
    ],
)
def test_un_cuerpo_raro_no_revienta_el_webhook(cuerpo):
    """Devolver 500 hace que Meta reintente para siempre."""
    assert leer_webhook(cuerpo) == []


def test_un_mensaje_sin_id_se_descarta_en_vez_de_romper_la_idempotencia():
    cuerpo = _webhook(
        messages=[{"from": "549351000", "timestamp": "1755200000", "type": "text",
                   "text": {"body": "hola"}}]
    )

    assert leer_webhook(cuerpo) == []
