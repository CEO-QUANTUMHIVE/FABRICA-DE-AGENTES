from motor_voz.brain.prompt import PROMPT_QUANTUMHIVE, construir


def test_el_prompt_pide_respuestas_habladas_y_breves():
    texto = construir().lower()
    assert "breve" in texto or "corta" in texto
    assert "voz" in texto or "hablado" in texto


def test_el_prompt_prohibe_markdown_y_emojis():
    texto = construir().lower()
    assert "markdown" in texto
    assert "emoji" in texto


def test_el_prompt_prohibe_inventar_datos():
    texto = construir().lower()
    assert "invent" in texto


def test_el_prompt_es_compacto():
    """El costo por conversacion sube con cada token del system prompt."""
    assert len(construir()) < 1600, "El prompt fijo crecio demasiado"


def test_construir_permite_agregar_contexto():
    texto = construir("El visitante viene de la campana de Instagram.")
    assert "Instagram" in texto
    assert PROMPT_QUANTUMHIVE in texto
