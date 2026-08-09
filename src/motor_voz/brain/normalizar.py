"""Convierte el texto del LLM en texto que se puede pronunciar.

El TTS lee literal: ante "24/7" pronuncia "veinticuatro septimo", y ante
"$1500" dice "dolar mil quinientos". Pedirle al LLM que escriba bien no
alcanza — falla una de cada varias veces, y en produccion eso son errores
delante de clientes. Se normaliza en codigo, que siempre acierta.

Este modulo es texto puro: no sabe que existe la voz ni LiveKit.
"""

from __future__ import annotations

import re

UNIDADES = (
    "cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho",
    "nueve", "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis",
    "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós",
    "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete",
    "veintiocho", "veintinueve",
)
DECENAS = ("", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta",
           "ochenta", "noventa")
CENTENAS = ("", "ciento", "doscientos", "trescientos", "cuatrocientos",
            "quinientos", "seiscientos", "setecientos", "ochocientos", "novecientos")

# Patrones que el TTS pronuncia mal si llegan tal cual.
ABREVIATURAS = (
    (r"\b24\s*/\s*7\b", "las veinticuatro horas"),
    (r"\b24\s*hs?\b", "veinticuatro horas"),
    (r"\bhs\b", "horas"),
    (r"\bhr?s?\.", "horas"),
    (r"\baprox\b\.?", "aproximadamente"),
    (r"\betc\b\.?", "etcétera"),
    (r"\bp/\b", "para"),
    (r"\bc/u\b", "cada uno"),
    (r"\bx\b", "por"),
    (r"\bN°|\bNro\b\.?|\bnº", "número"),
)

# Todo lo que no sea letra, numero, espacio o puntuacion hablable se borra.
# Se conservan los signos de entonacion porque son la partitura del TTS.
PERMITIDOS = re.compile(r"[^0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s\.,;:¿\?¡!'\-]")
ESPACIOS = re.compile(r"[ \t]+")


def numero_en_palabras(n: int) -> str:
    """Deletrea un entero en español. Cubre de 0 a 999.999."""
    if n < 0:
        return "menos " + numero_en_palabras(-n)
    if n < 30:
        return UNIDADES[n]
    if n < 100:
        d, u = divmod(n, 10)
        return DECENAS[d] + (f" y {UNIDADES[u]}" if u else "")
    if n == 100:
        return "cien"
    if n < 1000:
        c, r = divmod(n, 100)
        return CENTENAS[c] + (f" {numero_en_palabras(r)}" if r else "")
    if n < 1_000_000:
        miles, r = divmod(n, 1000)
        cabeza = "mil" if miles == 1 else f"{numero_en_palabras(miles)} mil"
        return cabeza + (f" {numero_en_palabras(r)}" if r else "")
    return str(n)


def _hora(m: re.Match[str]) -> str:
    h, mi = int(m.group(1)), int(m.group(2))
    if mi == 0:
        return f"{numero_en_palabras(h)} en punto"
    if mi == 30:
        return f"{numero_en_palabras(h)} y media"
    if mi == 15:
        return f"{numero_en_palabras(h)} y cuarto"
    return f"{numero_en_palabras(h)} y {numero_en_palabras(mi)}"


def normalizar(texto: str) -> str:
    """Deja el texto listo para que el TTS lo lea sin equivocarse."""
    t = texto

    for patron, reemplazo in ABREVIATURAS:
        t = re.sub(patron, reemplazo, t, flags=re.IGNORECASE)

    t = re.sub(r"\b(\d{1,2}):(\d{2})\b", _hora, t)          # 14:30 -> catorce y media
    t = re.sub(r"(\d)\s*%", lambda m: m.group(1) + " por ciento", t)
    t = re.sub(r"[$]\s*(\d)", lambda m: m.group(1), t)      # el "pesos" lo agrega abajo
    t = re.sub(r"\bUSD\b|\bU\$S\b", "dólares", t)

    # Miles con punto o coma: 1.500 -> 1500, para poder deletrearlo entero.
    t = re.sub(r"\b(\d{1,3})[.,](\d{3})\b", r"\1\2", t)
    t = re.sub(r"\d+", lambda m: numero_en_palabras(int(m.group())), t)

    t = PERMITIDOS.sub(" ", t)
    t = ESPACIOS.sub(" ", t)
    return t.strip()
