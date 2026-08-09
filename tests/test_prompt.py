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


def test_el_prompt_pide_energia():
    """Sin esto el LLM escribe frases planas y Fish las dice planas."""
    texto = construir().lower()
    assert "energia" in texto or "entusiasta" in texto


def test_el_prompt_habilita_los_signos_de_exclamacion():
    """La puntuacion es la partitura del TTS: sin exclamaciones la voz no sube."""
    texto = construir()
    assert "exclamacion" in texto.lower()
    assert "¡" in texto, "Tiene que mostrar el signo, no solo nombrarlo"


def test_el_prompt_da_ejemplos_de_como_hablar():
    """Describir el tono no alcanza: el modelo copia mejor de un ejemplo."""
    texto = construir().lower()
    assert "asi hablas vos" in texto
    assert "asi no hablas" in texto


def test_el_prompt_es_compacto():
    """El costo por conversacion sube con cada token del system prompt."""
    assert len(construir()) < 2200, "El prompt fijo crecio demasiado"


def test_construir_permite_agregar_contexto():
    texto = construir("El visitante viene de la campana de Instagram.")
    assert "Instagram" in texto
    assert PROMPT_QUANTUMHIVE in texto
