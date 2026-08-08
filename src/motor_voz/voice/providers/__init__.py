"""Proveedores externos del canal de voz.

Unico lugar del motor que conoce a Groq y a Fish Audio. Cada modulo expone
`opciones(config)` — puro y testeable sin red — y `crear(config)`, que
construye el objeto del plugin.
"""
