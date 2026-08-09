import pytest

from motor_voz.brain.normalizar import normalizar, numero_en_palabras


class TestNumeros:
    @pytest.mark.parametrize(
        "n,esperado",
        [
            (0, "cero"), (7, "siete"), (15, "quince"), (21, "veintiuno"),
            (30, "treinta"), (45, "cuarenta y cinco"), (100, "cien"),
            (101, "ciento uno"), (500, "quinientos"), (999, "novecientos noventa y nueve"),
            (1000, "mil"), (1500, "mil quinientos"), (2000, "dos mil"),
            (25000, "veinticinco mil"),
        ],
    )
    def test_deletrea_enteros(self, n, esperado):
        assert numero_en_palabras(n) == esperado


class TestElBugQueEncontroSergio:
    def test_24_7_ya_no_se_lee_como_veinticuatro_septimo(self):
        """El agente decia '24 septimo' en produccion. Este es EL test."""
        assert "las veinticuatro horas" in normalizar("Atiende 24/7 sin parar")
        assert "/" not in normalizar("Atiende 24/7 sin parar")

    def test_tambien_con_espacios_alrededor_de_la_barra(self):
        assert "las veinticuatro horas" in normalizar("Atiende 24 / 7")

    def test_no_queda_ninguna_barra_suelta(self):
        assert "/" not in normalizar("Vamos p/ alla y c/u paga lo suyo")


class TestSimbolos:
    def test_borra_lo_que_no_se_puede_pronunciar(self):
        limpio = normalizar("Mira *esto* #importante (de verdad) [ya]")
        for simbolo in "*#()[]":
            assert simbolo not in limpio

    def test_conserva_los_signos_de_entonacion(self):
        """Son la partitura del TTS: sin ellos la voz sale plana."""
        limpio = normalizar("¡Hola! ¿Cómo andás?")
        assert "¡" in limpio and "!" in limpio
        assert "¿" in limpio and "?" in limpio

    def test_conserva_las_tildes_y_la_enie(self):
        limpio = normalizar("El año que viene se hará la peluquería")
        assert "año" in limpio
        assert "hará" in limpio


class TestConversiones:
    def test_porcentaje(self):
        assert "por ciento" in normalizar("Subio 20%")
        assert "%" not in normalizar("Subio 20%")

    def test_horas(self):
        assert "catorce y media" in normalizar("Te espero a las 14:30")
        assert "nueve en punto" in normalizar("Abrimos 9:00")
        assert "diez y cuarto" in normalizar("Cierra 10:15")

    def test_precios_con_separador_de_miles(self):
        assert "mil quinientos" in normalizar("Sale $1.500")

    def test_abreviaturas(self):
        assert "aproximadamente" in normalizar("Tarda 20 min aprox")
        assert "etcétera" in normalizar("Cortes, barba, etc")


class TestIntegridad:
    def test_no_rompe_una_frase_normal(self):
        frase = "¡Claro que sí! ¿Querés que te lo muestre funcionando?"
        assert normalizar(frase) == frase

    def test_texto_vacio(self):
        assert normalizar("") == ""
        assert normalizar("   ") == ""

    def test_no_deja_espacios_dobles(self):
        assert "  " not in normalizar("Sale $1.500  y  tarda 20 min")
