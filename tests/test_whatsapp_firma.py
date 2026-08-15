"""Sin firma valida no se procesa nada.

El endpoint del webhook es publico: cualquiera puede hacerle POST. Lo unico
que separa un mensaje real de uno inventado es este HMAC.
"""

import hashlib
import hmac

from motor_voz.channels.whatsapp.firma import firma_valida

SECRETO = "app-secret-de-prueba"
CUERPO = b'{"object":"whatsapp_business_account","entry":[]}'


def _firmar(cuerpo: bytes, secreto: str = SECRETO) -> str:
    digest = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_la_firma_de_meta_se_acepta():
    assert firma_valida(CUERPO, _firmar(CUERPO), SECRETO)


def test_otro_secreto_no_pasa():
    assert not firma_valida(CUERPO, _firmar(CUERPO, "otro-secreto"), SECRETO)


def test_el_cuerpo_modificado_no_pasa():
    """Aunque la firma sea real, si el cuerpo cambio en el camino no sirve."""
    assert not firma_valida(CUERPO + b" ", _firmar(CUERPO), SECRETO)


def test_sin_cabecera_no_pasa():
    assert not firma_valida(CUERPO, None, SECRETO)
    assert not firma_valida(CUERPO, "", SECRETO)


def test_una_cabecera_sin_el_prefijo_no_pasa():
    digest = hmac.new(SECRETO.encode(), CUERPO, hashlib.sha256).hexdigest()
    assert not firma_valida(CUERPO, digest, SECRETO)
    assert not firma_valida(CUERPO, f"sha1={digest}", SECRETO)


def test_una_cabecera_basura_no_revienta():
    for cabecera in ("sha256=", "sha256=no-es-hex", "sha256=" + "f" * 63, "="):
        assert not firma_valida(CUERPO, cabecera, SECRETO)


def test_sin_secreto_configurado_se_rechaza_en_vez_de_aceptar():
    """Falla cerrado. Si el .env no tiene META_APP_SECRET, el webhook queda
    abierto a cualquiera, y eso no se nota hasta que alguien lo usa."""
    assert not firma_valida(CUERPO, _firmar(CUERPO, ""), "")
    assert not firma_valida(CUERPO, _firmar(CUERPO), "   ")
