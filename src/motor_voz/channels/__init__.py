"""Adaptadores de canal.

Cada canal traduce su webhook al contrato de `brain/mensajes.py` y nada mas.
La inteligencia vive una sola vez en `brain/`: un canal nuevo no trae su
propio bot, trae su propio parser y su propio cliente de envio.
"""
