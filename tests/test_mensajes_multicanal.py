from datetime import datetime, timezone

import pytest

from motor_voz.brain.mensajes import CANALES_COMERCIALES, MensajeEntrante


def _mensaje(canal: str = "whatsapp", **cambios) -> MensajeEntrante:
    datos = {
        "tenant_id": "tenant-quantumhive",
        "canal": canal,
        "conversacion_externa_id": "conversacion-1",
        "remitente_externo_id": "persona-1",
        "evento_externo_id": "evento-1",
        "mensaje_externo_id": "mensaje-1",
        "texto": "Hola",
        "recibido_en": datetime.now(timezone.utc),
    }
    datos.update(cambios)
    return MensajeEntrante(**datos)


def test_los_cuatro_canales_comparten_el_mismo_contrato():
    assert CANALES_COMERCIALES == {"web", "whatsapp", "instagram", "facebook"}
    for canal in CANALES_COMERCIALES:
        assert _mensaje(canal).canal == canal


def test_un_canal_inventado_no_entra_al_cerebro():
    with pytest.raises(ValueError, match="Canal no soportado"):
        _mensaje("meta_generico")


def test_el_tenant_resuelto_es_obligatorio():
    with pytest.raises(ValueError, match="tenant_id"):
        _mensaje(tenant_id="")


def test_la_idempotencia_incluye_canal_y_mensaje_externo():
    assert _mensaje("instagram").clave_idempotencia == "instagram:mensaje-1"
