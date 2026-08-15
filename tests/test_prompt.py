"""El prompt en tres capas: identidad, entrega y canal.

Estos tests son la memoria de los errores que ya cometimos en produccion.
Cada uno existe porque algo sono mal delante de Sergio.
"""

import pytest

from motor_voz.brain.prompt import ENTREGA_LIVE, ENTREGA_PIPELINE, IDENTIDAD, construir


class TestIdentidad:
    def test_es_la_misma_en_todos_los_motores(self):
        """Si se duplicara por motor, derivaria: tocas uno y te olvidas del otro."""
        for motor in ("pipeline", "gemini", "openai"):
            assert IDENTIDAD in construir(motor=motor)

    def test_prohibe_inventar_datos(self):
        assert "invent" in construir().lower()

    def test_habla_de_vos(self):
        texto = construir().lower()
        assert "rioplatense" in texto
        assert "nunca de tu ni de usted" in texto


class TestAgenteActivo:
    """El agente contestaba una frase y dejaba al visitante colgado."""

    def test_prohibe_terminar_sin_pregunta(self):
        texto = construir().lower()
        assert "nunca termines sin una pregunta" in texto

    def test_pide_reaccionar_antes_de_informar(self):
        assert "reacciona antes de contestar" in construir().lower()

    def test_pide_ofrecer_informacion_no_pedida(self):
        assert "ofrece informacion que no te pidieron" in construir().lower()

    def test_pide_tener_opiniones(self):
        """Un vendedor que dice que si a todo aburre."""
        assert "opiniones" in construir().lower()

    def test_muestra_ejemplos_de_lo_que_NO_hay_que_hacer(self):
        """Describir el error no alcanza: hay que mostrarlo."""
        texto = construir()
        assert "Asi NO hablas" in texto
        assert "colgado" in texto


class TestEntregaPorMotor:
    def test_el_pipeline_recibe_reglas_de_puntuacion(self):
        """El TTS lee literal: la puntuacion es su partitura."""
        p = construir(motor="pipeline")
        assert ENTREGA_PIPELINE in p
        assert "24/7" in p, "Tiene que nombrar el caso concreto que fallo"
        assert "veinticuatro horas" in p

    @pytest.mark.parametrize("motor", ["gemini", "openai"])
    def test_los_live_reciben_reglas_de_actitud(self, motor):
        """Generan el habla: la puntuacion no les dice nada."""
        p = construir(motor=motor)
        assert ENTREGA_LIVE in p
        assert "puntuacion" not in p.lower().split("no pienses en puntuacion")[-1][:200]

    def test_los_live_no_reciben_las_reglas_de_texto_del_pipeline(self):
        assert ENTREGA_PIPELINE not in construir(motor="gemini")

    def test_un_motor_desconocido_cae_al_pipeline(self):
        """Nunca sin reglas de entrega: seria peor que las equivocadas."""
        assert ENTREGA_PIPELINE in construir(motor="inventado")


class TestCanal:
    def test_la_web_avisa_que_lo_pueden_interrumpir(self):
        assert "interrumpir" in construir(canal="web").lower()

    @pytest.mark.parametrize(
        "canal", ["whatsapp", "instagram", "facebook", "telegram"]
    )
    def test_mensajeria_avisa_que_no_hay_interrupcion(self, canal):
        assert "no hay interrupcion" in construir(canal=canal).lower()

    def test_mensajeria_avisa_que_puede_pasar_tiempo(self):
        """En WhatsApp el visitante puede volver a los tres dias."""
        assert "puede pasar tiempo" in construir(canal="whatsapp").lower()


class TestComposicion:
    def test_las_cuatro_capas_estan_presentes(self):
        p = construir(motor="pipeline", canal="web")
        assert IDENTIDAD in p
        assert ENTREGA_PIPELINE in p
        assert "interrumpir" in p
        assert "Asi hablas vos" in p

    def test_acepta_contexto_de_sesion(self):
        p = construir(contexto_extra="El visitante viene de Instagram.")
        assert "Instagram" in p

    def test_no_agrega_ruido_si_no_hay_contexto(self):
        assert "Contexto de esta conversacion" not in construir()

    def test_sigue_siendo_compacto(self):
        """Cada token del system prompt se paga en cada turno."""
        for motor in ("pipeline", "gemini", "openai"):
            largo = len(construir(motor=motor))
            assert largo < 3200, f"{motor}: {largo} caracteres, crecio demasiado"
