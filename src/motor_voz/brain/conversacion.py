"""El mismo agente, pero por texto y sin LiveKit en el medio.

La voz entra por `voice/motores.py`, donde el LLM lo pone un plugin de
livekit-agents. WhatsApp, Instagram y Facebook no pasan por ahi, y `brain/`
tiene prohibido importar livekit: sin este modulo, un canal de texto tendria
que traerse su propio cerebro, que es justo lo que el plan multicanal
prohibe.

Reusa lo que ya existe: el prompt de tres capas, el contexto del tenant con
su conocimiento publicado, y el mismo `registry_de(modo)` que decide si
alguien alcanza las tools internas.

Habla con Groq por HTTP crudo a proposito. El paquete `groq` no es
dependencia del proyecto y agregarlo obligaria a instalarlo en la VM en el
proximo deploy — trampa que ya nos costo una caida. `aiohttp` ya esta.
"""

from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import aiohttp

from motor_voz.brain import contexto as contexto_mod
from motor_voz.brain import prompt as prompt_mod
from motor_voz.brain.mensajes import Turno
from motor_voz.brain.tenants.modelos import Tenant
from motor_voz.brain.tools import registro
from motor_voz.config import Config

logger = logging.getLogger(__name__)

URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"

MAX_TURNOS_HISTORIAL = 20
"""Cuantos mensajes viejos viajan en cada pedido.

Una conversacion de WhatsApp no termina nunca: sin tope, cada mensaje nuevo
paga de nuevo los seis meses anteriores.
"""

MAX_VUELTAS = 4
"""Cuantas veces se le vuelve a preguntar al modelo tras ejecutar tools.

Un modelo puede pedir la misma tool para siempre. Sin tope, eso es una
conversacion colgada y una factura abierta.
"""

RESPUESTA_DE_EMERGENCIA = (
    "Perdon, se me complico procesar eso. ¿Me lo repetis de otra forma?"
)
"""Nunca sale un mensaje vacio.

Un globo en blanco en el chat de un cliente es peor que no contestar: parece
que el negocio esta roto.
"""

# Los que ata el servidor y el modelo no debe ver ni completar.
_ATADOS = frozenset({"tenant", "config", "sala"})

_TIPOS_JSON: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def armar_mensajes(
    tenant: Tenant,
    *,
    historial: tuple[Turno, ...] | list[Turno],
    texto: str,
    motor: str = "pipeline",
    canal: str = "whatsapp",
) -> list[dict[str, str]]:
    """El prompt completo tal como lo va a ver el modelo.

    El texto del visitante viaja **crudo**. `brain/normalizar.py` existe para
    que el TTS no lea `24/7` como "veinticuatro septimo"; aplicarlo en un
    canal escrito arruinaria el mensaje.
    """
    system = prompt_mod.construir(
        motor=motor,
        canal=canal,
        contexto_extra=contexto_mod.construir_contexto(tenant, motor=motor, canal=canal),
        identidad=tenant.prompt_propio.strip() or tenant.perfil.prompt_base.strip() or prompt_mod.IDENTIDAD,
    )

    mensajes: list[dict[str, str]] = [{"role": "system", "content": system}]
    for turno in list(historial)[-MAX_TURNOS_HISTORIAL:]:
        mensajes.append({"role": turno.rol, "content": turno.texto})
    mensajes.append({"role": "user", "content": texto})
    return mensajes


def esquemas_de_tools(registry: str) -> list[dict[str, Any]]:
    """Las tools del registry en el formato de function calling de OpenAI.

    El esquema se deriva de la firma, salteando lo que ata el servidor. Si
    `tenant` o `config` aparecieran, el modelo intentaria completarlos — y
    podria pasar los de otro negocio.
    """
    esquemas = []
    for nombre in sorted(registro.tools_de(registry)):
        funcion = registro.resolver_tool(registry, nombre)
        esquemas.append(
            {
                "type": "function",
                "function": {
                    "name": nombre,
                    "description": _descripcion(funcion),
                    "parameters": _parametros(funcion),
                },
            }
        )
    return esquemas


async def responder(
    config: Config,
    tenant: Tenant,
    *,
    historial: tuple[Turno, ...] | list[Turno] = (),
    texto: str,
    modo: str = "publico",
    canal: str = "whatsapp",
    pedir: Callable[[dict], Awaitable[dict]] | None = None,
) -> str:
    """Lo que el agente contesta. Nunca vacio, nunca una excepcion al aire.

    `pedir` se inyecta en los tests. En produccion es el POST a Groq.
    """
    registry = registro.registry_de(modo)
    mensajes = armar_mensajes(tenant, historial=historial, texto=texto, canal=canal)
    esquemas = esquemas_de_tools(registry)
    llamar = pedir or _cliente_groq(config)

    for vuelta in range(MAX_VUELTAS):
        payload: dict[str, Any] = {
            "model": config.llm_model,
            "messages": mensajes,
            "temperature": 0.6,
        }
        # En la ultima vuelta se le sacan las tools: si no, puede pedir una mas
        # y quedarnos sin texto que mandarle al cliente.
        if esquemas and vuelta < MAX_VUELTAS - 1:
            payload["tools"] = esquemas

        try:
            respuesta = await llamar(payload)
        except Exception:
            logger.exception("groq | tenant=%s canal=%s", tenant.slug, canal)
            return RESPUESTA_DE_EMERGENCIA

        mensaje = _mensaje_de(respuesta)
        llamadas = mensaje.get("tool_calls") or []
        if not llamadas:
            contenido = (mensaje.get("content") or "").strip()
            return contenido or RESPUESTA_DE_EMERGENCIA

        mensajes.append(mensaje)
        for llamada in llamadas:
            mensajes.append(await _ejecutar(llamada, registry, tenant, config))

    return RESPUESTA_DE_EMERGENCIA


async def _ejecutar(
    llamada: dict[str, Any], registry: str, tenant: Tenant, config: Config
) -> dict[str, str]:
    """Corre una tool y devuelve su resultado como mensaje `tool`.

    Nada de lo que pase adentro puede cortar la conversacion. Un nombre
    inventado, un JSON roto o una tool que explota vuelven como texto para el
    modelo, que sigue hablando.
    """
    funcion_pedida = llamada.get("function") or {}
    nombre = str(funcion_pedida.get("name") or "")
    resultado = ""
    try:
        funcion = registro.resolver_tool(registry, nombre)
        argumentos = json.loads(funcion_pedida.get("arguments") or "{}")
        if not isinstance(argumentos, dict):
            raise ValueError("los argumentos no son un objeto")
        argumentos = {k: v for k, v in argumentos.items() if k not in _ATADOS}
        resultado = str(await funcion(tenant, config, **argumentos))
    except registro.ToolNoPermitida:
        # Mismo texto exista o no: distinguirlo le diria al modelo —y a quien
        # lo este empujando— cuales tools hay del otro lado.
        logger.warning("tool fuera de registry | %s | registry=%s", nombre, registry)
        resultado = "No tengo esa herramienta disponible."
    except Exception:
        logger.exception("tool fallo | %s | tenant=%s", nombre, tenant.slug)
        resultado = "No pude obtener ese dato ahora."

    return {
        "role": "tool",
        "tool_call_id": str(llamada.get("id") or ""),
        "content": resultado,
    }


def _mensaje_de(respuesta: dict[str, Any]) -> dict[str, Any]:
    opciones = respuesta.get("choices") or []
    if not opciones:
        return {}
    mensaje = opciones[0].get("message")
    return mensaje if isinstance(mensaje, dict) else {}


def _descripcion(funcion: Callable) -> str:
    """La primera linea del docstring. Es lo que el modelo lee para decidir."""
    doc = inspect.getdoc(funcion) or ""
    return doc.split("\n", 1)[0].strip() or funcion.__name__


def _parametros(funcion: Callable) -> dict[str, Any]:
    propiedades: dict[str, Any] = {}
    obligatorios: list[str] = []
    for nombre, parametro in inspect.signature(funcion).parameters.items():
        if nombre in _ATADOS or parametro.kind is inspect.Parameter.VAR_KEYWORD:
            continue
        propiedades[nombre] = {"type": _TIPOS_JSON.get(parametro.annotation, "string")}
        if parametro.default is inspect.Parameter.empty:
            obligatorios.append(nombre)
    return {"type": "object", "properties": propiedades, "required": obligatorios}


def _cliente_groq(config: Config) -> Callable[[dict], Awaitable[dict]]:
    async def pedir(payload: dict) -> dict:
        cabeceras = {"Authorization": f"Bearer {config.groq_api_key}"}
        tiempo = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=tiempo) as sesion:
            async with sesion.post(URL_GROQ, json=payload, headers=cabeceras) as r:
                r.raise_for_status()
                return await r.json()

    return pedir
