"""Unico punto del motor que habla con Supabase.

Ningun otro modulo instancia el cliente de Supabase ni arma una query.
Lo hace cumplir tests/test_un_solo_cliente_supabase.py, que recorre todo
src/motor_voz con AST y falla si aparece create_client/acreate_client
fuera de este archivo.

El aislamiento entre tenants depende de este archivo: cada metodo recibe
el tenant y lo aplica como filtro en cada query. Supabase se usa con la
SERVICE_ROLE_KEY, que saltea RLS por diseño, asi que RLS no es la
defensa real (spec S7) — la defensa es que ninguna query de aca sale sin
`.eq("tenant_id", ...)` o sin resolver antes el id del tenant por su slug.
"""

from __future__ import annotations

from supabase import AsyncClient, acreate_client

from datetime import datetime, timedelta, timezone

from motor_voz.brain.mensajes import (
    CanalTenant,
    ContextoConversacion,
    Conversacion,
    DestinoEnvio,
    EventoInbox,
    EventoOutbox,
    MensajeEntrante,
    MensajeGuardado,
    Permiso,
    ResultadoIngreso,
    Turno,
)
from motor_voz.brain.tenants.modelos import (
    ConocimientoTenant,
    DominioTenant,
    Lead,
    PerfilTenant,
    Servicio,
    Tenant,
    VozTenant,
)
from motor_voz.config import Config


class TenantNoEncontrado(RuntimeError):
    """No existe un tenant activo con ese slug."""


class CanalNoEncontrado(RuntimeError):
    """La cuenta externa no corresponde a un canal conectado y activo."""


class CanalYaAsignado(RuntimeError):
    """La cuenta externa ya pertenece a otro tenant.

    Se mantiene un error propio para que la API pueda fallar cerrado sin
    revelar a que negocio pertenece el numero.
    """


class ConversacionNoEncontrada(RuntimeError):
    """No hay una conversacion con ese id EN ESE TENANT.

    Un solo error para "no existe" y "es de otro negocio": distinguirlos
    confirmaria la existencia de conversaciones ajenas.
    """


async def _cliente(config: Config) -> AsyncClient:
    return await acreate_client(config.supabase_url, config.supabase_service_role_key)


async def usuario_de_token(config: Config, token: str) -> str | None:
    """Valida un access token con Supabase Auth y devuelve el usuario.

    No se decodifica ni verifica el JWT a mano. Supabase comprueba firma,
    expiracion y sesion; cualquier token sin usuario valido queda cerrado.
    """
    if not token.strip():
        return None
    cliente = await _cliente(config)
    respuesta = await cliente.auth.get_user(token)
    usuario = getattr(respuesta, "user", None)
    return str(usuario.id) if usuario and usuario.id else None


async def rol_de_usuario_en_tenant(
    config: Config, usuario_id: str, tenant_id: str
) -> str | None:
    """Rol del usuario en ESE tenant; tener sesion sola no alcanza."""
    cliente = await _cliente(config)
    respuesta = (
        await cliente.table("tenant_usuarios")
        .select("rol")
        .eq("usuario_id", usuario_id)
        .eq("tenant_id", tenant_id)
        .maybe_single()
        .execute()
    )
    if respuesta is None or respuesta.data is None:
        return None
    return respuesta.data.get("rol")


async def tenants_de_usuario(config: Config, usuario_id: str) -> list[dict]:
    """Negocios activos a los que pertenece un usuario autenticado.

    Se consulta primero la membresia y despues los tenants permitidos. Asi la
    API del panel nunca ofrece un catalogo global de negocios.
    """
    cliente = await _cliente(config)
    membresias_resp = (
        await cliente.table("tenant_usuarios")
        .select("tenant_id, rol")
        .eq("usuario_id", usuario_id)
        .execute()
    )
    membresias = membresias_resp.data or []
    if not membresias:
        return []

    rol_por_tenant = {fila["tenant_id"]: fila["rol"] for fila in membresias}
    tenants_resp = (
        await cliente.table("tenants")
        .select("id, slug, nombre, estado")
        .in_("id", list(rol_por_tenant))
        .eq("estado", "activo")
        .order("nombre")
        .execute()
    )
    return [
        {
            "id": fila["id"],
            "slug": fila["slug"],
            "nombre": fila["nombre"],
            "estado": fila["estado"],
            "rol": rol_por_tenant[fila["id"]],
        }
        for fila in (tenants_resp.data or [])
    ]


async def canal_de_cuenta(
    config: Config, *, canal: str, cuenta_externa_id: str
) -> CanalTenant:
    """Resuelve el tenant por la cuenta que RECIBE el mensaje.

    El webhook no puede declarar un tenant. WhatsApp aporta phone_number_id;
    Instagram y Facebook, la cuenta/pagina receptora. Esa identidad externa
    es la que se mapea aca a un unico tenant activo.
    """
    cliente = await _cliente(config)
    respuesta = (
        await cliente.table("tenant_canales")
        .select("id, tenant_id, canal, cuenta_externa_id, nombre, estado, tenants!inner(estado)")
        .eq("canal", canal)
        .eq("cuenta_externa_id", cuenta_externa_id.strip())
        .eq("estado", "conectado")
        .eq("tenants.estado", "activo")
        .maybe_single()
        .execute()
    )
    if respuesta is None or respuesta.data is None:
        raise CanalNoEncontrado(
            f"No hay canal {canal!r} conectado para esa cuenta externa"
        )
    datos = respuesta.data
    return CanalTenant(
        id=datos["id"],
        tenant_id=datos["tenant_id"],
        canal=datos["canal"],
        cuenta_externa_id=datos["cuenta_externa_id"],
        nombre=datos.get("nombre", ""),
        estado=datos["estado"],
    )


async def canales_para_panel(config: Config, tenant_id: str) -> list[dict]:
    """Configuracion no secreta de los canales de UN tenant."""
    cliente = await _cliente(config)
    respuesta = (
        await cliente.table("tenant_canales")
        .select(
            "id, canal, cuenta_externa_id, nombre, estado, secreto_ref, "
            "created_at, updated_at"
        )
        .eq("tenant_id", tenant_id)
        .order("created_at")
        .execute()
    )
    return respuesta.data or []


async def configurar_whatsapp(
    config: Config,
    *,
    tenant_id: str,
    cuenta_externa_id: str,
    nombre: str,
    secreto_ref: str,
    estado: str,
) -> dict:
    """Vincula un numero a un tenant sin aceptar ni persistir su token.

    No se usa un upsert directo: el conflicto global por phone_number_id
    podria reasignar silenciosamente el numero de otro negocio.
    """
    cliente = await _cliente(config)
    existente = (
        await cliente.table("tenant_canales")
        .select("id, tenant_id, estado")
        .eq("canal", "whatsapp")
        .eq("cuenta_externa_id", cuenta_externa_id)
        .maybe_single()
        .execute()
    )
    fila = existente.data if existente is not None else None
    if fila and fila["tenant_id"] != tenant_id:
        raise CanalYaAsignado("La cuenta de WhatsApp ya esta vinculada.")

    datos = {
        "tenant_id": tenant_id,
        "canal": "whatsapp",
        "cuenta_externa_id": cuenta_externa_id,
        "nombre": nombre,
        "secreto_ref": secreto_ref,
        "estado": "conectado" if estado == "conectado" else "pendiente",
    }
    if fila:
        # Guardar de nuevo una conexion sana no la degrada a pendiente.
        if fila.get("estado") == "conectado" and estado != "conectado":
            datos["estado"] = "conectado"
        respuesta = (
            await cliente.table("tenant_canales")
            .update(datos)
            .eq("id", fila["id"])
            .eq("tenant_id", tenant_id)
            .execute()
        )
    else:
        respuesta = await cliente.table("tenant_canales").insert(datos).execute()

    creadas = respuesta.data or []
    return creadas[0] if isinstance(creadas, list) and creadas else datos


async def registrar_mensaje_entrante(
    config: Config, *, tenant_canal_id: str, mensaje: MensajeEntrante
) -> ResultadoIngreso:
    """Persiste webhook + conversacion + mensaje en una transaccion idempotente."""
    cliente = await _cliente(config)
    respuesta = await cliente.rpc(
        "registrar_mensaje_entrante",
        {
            "p_tenant_canal_id": tenant_canal_id,
            "p_tenant_id": mensaje.tenant_id,
            "p_canal": mensaje.canal,
            "p_conversacion_externa_id": mensaje.conversacion_externa_id,
            "p_remitente_externo_id": mensaje.remitente_externo_id,
            "p_evento_externo_id": mensaje.evento_externo_id,
            "p_mensaje_externo_id": mensaje.mensaje_externo_id,
            "p_texto": mensaje.texto,
            "p_recibido_en": mensaje.recibido_en.isoformat(),
            "p_payload": mensaje.payload,
        },
    ).execute()
    datos = respuesta.data or {}
    return ResultadoIngreso(
        duplicado=bool(datos.get("duplicado")),
        inbox_id=datos.get("inbox_id"),
        conversacion_id=datos.get("conversacion_id"),
        mensaje_id=datos.get("mensaje_id"),
    )


async def conversaciones_de(
    config: Config, tenant_id: str, *, limite: int = 50
) -> list[Conversacion]:
    """Conversaciones de un solo tenant para chat y metricas del panel."""
    cliente = await _cliente(config)
    respuesta = (
        await cliente.table("conversaciones")
        .select(
            "id, canal, contacto_externo_id, nombre_contacto, "
            "modo_atencion, ultimo_mensaje_en"
        )
        .eq("tenant_id", tenant_id)
        .order("ultimo_mensaje_en", desc=True)
        .limit(max(1, min(limite, 200)))
        .execute()
    )
    return [Conversacion(**fila) for fila in (respuesta.data or [])]


async def mensajes_de_conversacion(
    config: Config, *, tenant_id: str, conversacion_id: str, limite: int = 100
) -> list[MensajeGuardado]:
    """Mensajes de una conversacion, exigiendo tambien su tenant."""
    cliente = await _cliente(config)
    respuesta = (
        await cliente.table("mensajes")
        .select("id, canal, direccion, texto, estado, ocurrido_en")
        .eq("tenant_id", tenant_id)
        .eq("conversacion_id", conversacion_id)
        .order("ocurrido_en", desc=False)
        .limit(max(1, min(limite, 500)))
        .execute()
    )
    return [MensajeGuardado(**fila) for fila in (respuesta.data or [])]


# La base guarda la direccion del mensaje; el LLM habla de roles. `sistema`
# no esta a proposito: son notas internas y no van al prompt.
_DIRECCION_A_ROL = {"entrante": "user", "saliente": "assistant"}


async def tomar_eventos_inbox(
    config: Config, *, limite: int = 10, bloqueo_segundos: int = 60
) -> list[EventoInbox]:
    """Toma un lote pendiente y lo deja bloqueado, en una sola transaccion.

    Va por RPC y no por REST porque el bloqueo tiene que pasar adentro del
    mismo UPDATE: un SELECT y despues un UPDATE dejan una ventana donde otro
    worker lee las mismas filas, y eso es contestarle dos veces al cliente.
    """
    cliente = await _cliente(config)
    respuesta = await cliente.rpc(
        "tomar_eventos_inbox",
        {
            "p_limite": max(1, min(limite, 100)),
            "p_bloqueo_segundos": max(10, bloqueo_segundos),
        },
    ).execute()
    return [
        EventoInbox(
            id=fila["id"],
            tenant_id=fila["tenant_id"],
            tenant_canal_id=fila["tenant_canal_id"],
            conversacion_id=fila.get("conversacion_id"),
            canal=fila["canal"],
            evento_externo_id=fila["evento_externo_id"],
        )
        for fila in (respuesta.data or [])
    ]


async def cerrar_evento_inbox(
    config: Config, *, evento_id: str, ok: bool, error: str = ""
) -> str:
    """Marca el evento como procesado, fallido o descartado.

    Devuelve el estado en que quedo. La funcion de la base decide el
    descarte a los cinco intentos; aca no se replica esa regla.
    """
    cliente = await _cliente(config)
    respuesta = await cliente.rpc(
        "cerrar_evento_inbox",
        {
            "p_id": evento_id,
            "p_ok": ok,
            # Un traceback entero en cada reintento infla la tabla sin
            # agregar nada: con el principio alcanza para saber que paso.
            "p_error": (error or "")[:500],
        },
    ).execute()
    return respuesta.data or ""


async def contexto_de_conversacion(
    config: Config, *, tenant_id: str, conversacion_id: str, limite: int = 40
) -> ContextoConversacion:
    """El estado de atencion y los ultimos turnos, exigiendo el tenant.

    Trae los ULTIMOS `limite` y los devuelve en orden cronologico. Pedirlos
    ascendentes y cortar daria los primeros, o sea el arranque de una charla
    de hace seis meses en vez de lo que se esta hablando ahora.
    """
    cliente = await _cliente(config)

    conversacion_resp = (
        await cliente.table("conversaciones")
        .select("modo_atencion")
        .eq("tenant_id", tenant_id)
        .eq("id", conversacion_id)
        .maybe_single()
        .execute()
    )
    if conversacion_resp is None or conversacion_resp.data is None:
        raise ConversacionNoEncontrada(
            f"No hay conversacion '{conversacion_id}' en ese tenant"
        )

    mensajes_resp = (
        await cliente.table("mensajes")
        .select("direccion, texto, ocurrido_en")
        .eq("tenant_id", tenant_id)
        .eq("conversacion_id", conversacion_id)
        .order("ocurrido_en", desc=True)
        .limit(max(1, min(limite, 200)))
        .execute()
    )
    turnos = tuple(
        Turno(rol=_DIRECCION_A_ROL[fila["direccion"]], texto=fila["texto"] or "")
        for fila in reversed(mensajes_resp.data or [])
        if fila["direccion"] in _DIRECCION_A_ROL
    )
    return ContextoConversacion(
        modo_atencion=conversacion_resp.data["modo_atencion"], turnos=turnos
    )


async def encolar_respuesta(
    config: Config,
    *,
    tenant_id: str,
    tenant_canal_id: str,
    conversacion_id: str,
    canal: str,
    clave_idempotencia: str,
    payload: dict,
) -> bool:
    """Deja la respuesta lista para que el cliente del canal la mande.

    True si se encolo, False si ya estaba. La restriccion
    `(tenant_canal_id, clave_idempotencia)` es la que hace que un worker que
    muere despues de encolar y antes de confirmar no genere una segunda
    respuesta al reanudar.
    """
    cliente = await _cliente(config)
    respuesta = (
        await cliente.table("eventos_outbox")
        .upsert(
            {
                "tenant_id": tenant_id,
                "tenant_canal_id": tenant_canal_id,
                "conversacion_id": conversacion_id,
                "canal": canal,
                "clave_idempotencia": clave_idempotencia,
                "payload": payload,
            },
            on_conflict="tenant_canal_id,clave_idempotencia",
            ignore_duplicates=True,
        )
        .execute()
    )
    return bool(respuesta.data)


async def es_operador(config: Config, usuario_id: str) -> bool:
    """Si este usuario puede dar de alta negocios.

    Ser cliente de la plataforma y ser quien la opera son dos cosas distintas.
    Por eso es una lista explicita y no "el dueño de QuantumHive": el dia que
    QuantumHive tenga un empleado con acceso al panel, ese empleado no tiene
    que poder crear negocios.
    """
    cliente = await _cliente(config)
    respuesta = (
        await cliente.table("plataforma_operadores")
        .select("usuario_id")
        .eq("usuario_id", usuario_id)
        .maybe_single()
        .execute()
    )
    return bool(respuesta is not None and respuesta.data)


async def crear_negocio_borrador(
    config: Config,
    *,
    operador_id: str,
    slug: str,
    nombre: str,
    perfil_slug: str,
    prompt_propio: str = "",
    dominio: str = "",
    email_dueno: str = "",
) -> dict:
    """Da de alta un negocio EN BORRADOR. No existe para nadie hasta que se paga."""
    cliente = await _cliente(config)
    respuesta = await cliente.rpc(
        "crear_negocio_borrador",
        {
            "p_operador_id": operador_id,
            "p_slug": slug,
            "p_nombre": nombre,
            "p_perfil_slug": perfil_slug,
            "p_prompt_propio": prompt_propio,
            "p_dominio": dominio,
            "p_email_dueno": email_dueno,
        },
    ).execute()
    return respuesta.data or {}


async def activar_negocio(config: Config, *, operador_id: str, slug: str) -> dict:
    """Lo que pasa cuando el cliente paga. Activar dos veces no rompe."""
    cliente = await _cliente(config)
    respuesta = await cliente.rpc(
        "activar_negocio", {"p_operador_id": operador_id, "p_slug": slug}
    ).execute()
    return respuesta.data or {}


async def puede_responder(
    config: Config, *, tenant_id: str, conversacion_id: str
) -> Permiso:
    """Kill-switch y topes de gasto de ese negocio.

    Se consulta ANTES de llamar al LLM: el punto es no pagarlo, no descartar
    la respuesta despues de haberla generado.
    """
    cliente = await _cliente(config)
    respuesta = await cliente.rpc(
        "puede_responder",
        {"p_tenant_id": tenant_id, "p_conversacion_id": conversacion_id},
    ).execute()
    datos = respuesta.data or {}
    return Permiso(
        permitido=bool(datos.get("permitido")),
        motivo=str(datos.get("motivo") or ""),
    )


async def tomar_eventos_outbox(
    config: Config, *, limite: int = 10, bloqueo_segundos: int = 60
) -> list[EventoOutbox]:
    """Espejo de `tomar_eventos_inbox`. Aca el duplicado le llega al cliente."""
    cliente = await _cliente(config)
    respuesta = await cliente.rpc(
        "tomar_eventos_outbox",
        {
            "p_limite": max(1, min(limite, 100)),
            "p_bloqueo_segundos": max(10, bloqueo_segundos),
        },
    ).execute()
    return [
        EventoOutbox(
            id=fila["id"],
            tenant_id=fila["tenant_id"],
            tenant_canal_id=fila["tenant_canal_id"],
            conversacion_id=fila["conversacion_id"],
            canal=fila["canal"],
            clave_idempotencia=fila["clave_idempotencia"],
            payload=fila.get("payload") or {},
        )
        for fila in (respuesta.data or [])
    ]


async def cerrar_evento_outbox(
    config: Config,
    *,
    evento_id: str,
    ok: bool,
    error: str = "",
    reintentable: bool = True,
) -> str:
    """Cierra un envio. `reintentable=False` lo descarta sin gastar intentos."""
    cliente = await _cliente(config)
    respuesta = await cliente.rpc(
        "cerrar_evento_outbox",
        {
            "p_id": evento_id,
            "p_ok": ok,
            "p_error": (error or "")[:500],
            "p_reintentable": reintentable,
        },
    ).execute()
    return respuesta.data or ""


async def destino_de_envio(
    config: Config, *, tenant_id: str, tenant_canal_id: str, conversacion_id: str
) -> DestinoEnvio:
    """Desde que cuenta y a quien, en una sola consulta.

    Va con join y no con tres consultas sueltas porque las tres tendrian que
    filtrar por tenant y alcanza con olvidarse en una para cruzar negocios.
    """
    cliente = await _cliente(config)
    respuesta = (
        await cliente.table("conversaciones")
        .select(
            "contacto_externo_id, "
            "tenant_canales!inner(cuenta_externa_id, secreto_ref, estado)"
        )
        .eq("tenant_id", tenant_id)
        .eq("id", conversacion_id)
        .eq("tenant_canal_id", tenant_canal_id)
        .maybe_single()
        .execute()
    )
    if respuesta is None or respuesta.data is None:
        raise ConversacionNoEncontrada(
            f"No hay conversacion '{conversacion_id}' en ese tenant y canal"
        )
    datos = respuesta.data
    canal = datos["tenant_canales"]
    return DestinoEnvio(
        cuenta_externa_id=canal["cuenta_externa_id"],
        secreto_ref=canal.get("secreto_ref") or "",
        contacto_externo_id=datos["contacto_externo_id"],
        estado_canal=canal["estado"],
    )


async def registrar_mensaje_saliente(
    config: Config,
    *,
    tenant_id: str,
    tenant_canal_id: str,
    conversacion_id: str,
    canal: str,
    mensaje_externo_id: str,
    texto: str,
) -> None:
    """Guarda lo que contesto el agente, para el historial y el panel.

    Sin esto el proximo turno no ve lo que ya dijo y se repite. Es idempotente
    por `(tenant_canal_id, mensaje_externo_id)`: reenviar el mismo id no
    duplica la fila.
    """
    cliente = await _cliente(config)
    await (
        cliente.table("mensajes")
        .upsert(
            {
                "tenant_id": tenant_id,
                "tenant_canal_id": tenant_canal_id,
                "conversacion_id": conversacion_id,
                "canal": canal,
                "mensaje_externo_id": mensaje_externo_id,
                "direccion": "saliente",
                "texto": texto,
                "estado": "enviado",
                "ocurrido_en": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="tenant_canal_id,mensaje_externo_id",
            ignore_duplicates=True,
        )
        .execute()
    )


async def tenant_por_id(config: Config, tenant_id: str) -> Tenant:
    """El tenant completo, buscado por id en vez de por slug.

    El webhook resuelve un id, no un slug. Se traduce y se delega en
    `obtener_tenant` para no tener dos caminos que carguen un tenant y se
    desincronicen cuando uno sume un dato y el otro no.
    """
    cliente = await _cliente(config)
    respuesta = (
        await cliente.table("tenants")
        .select("slug")
        .eq("id", tenant_id)
        .maybe_single()
        .execute()
    )
    if respuesta is None or respuesta.data is None:
        raise TenantNoEncontrado(f"No hay tenant con id '{tenant_id}'")
    return await obtener_tenant(config, respuesta.data["slug"])


async def crear_borrador_conocimiento(
    config: Config,
    *,
    tenant_id: str,
    categoria: str,
    clave: str,
    titulo: str,
    contenido: dict,
    usuario_id: str | None = None,
    motivo: str = "",
) -> dict:
    """Crea una version que aun NO afecta las respuestas del agente."""
    cliente = await _cliente(config)
    respuesta = await cliente.rpc(
        "crear_borrador_conocimiento",
        {
            "p_tenant_id": tenant_id,
            "p_categoria": categoria,
            "p_clave": clave,
            "p_titulo": titulo,
            "p_contenido": contenido,
            "p_creado_por": usuario_id,
            "p_motivo": motivo,
        },
    ).execute()
    return respuesta.data or {}


async def publicar_version_conocimiento(
    config: Config,
    *,
    tenant_id: str,
    version_id: str,
    usuario_id: str | None = None,
    motivo: str = "",
) -> dict:
    """Publica o restaura una version, siempre dentro del tenant indicado."""
    cliente = await _cliente(config)
    respuesta = await cliente.rpc(
        "publicar_version_conocimiento",
        {
            "p_tenant_id": tenant_id,
            "p_version_id": version_id,
            "p_publicado_por": usuario_id,
            "p_motivo": motivo,
        },
    ).execute()
    return respuesta.data or {}


async def conocimiento_para_panel(config: Config, tenant_id: str) -> list[dict]:
    """Piezas y todas sus versiones, siempre limitadas a un tenant."""
    cliente = await _cliente(config)
    piezas_resp = (
        await cliente.table("conocimiento_tenant")
        .select(
            "id, categoria, clave, titulo, estado, version_publicada_id, "
            "created_at, updated_at"
        )
        .eq("tenant_id", tenant_id)
        .order("updated_at", desc=True)
        .limit(500)
        .execute()
    )
    piezas = piezas_resp.data or []
    if not piezas:
        return []

    ids = [fila["id"] for fila in piezas]
    versiones_resp = (
        await cliente.table("versiones_conocimiento")
        .select("id, conocimiento_id, numero, contenido, motivo, creado_por, created_at")
        .eq("tenant_id", tenant_id)
        .in_("conocimiento_id", ids)
        .order("numero", desc=True)
        .limit(2000)
        .execute()
    )
    versiones_por_pieza: dict[str, list[dict]] = {pieza_id: [] for pieza_id in ids}
    for version in versiones_resp.data or []:
        versiones_por_pieza.setdefault(version["conocimiento_id"], []).append(version)

    return [
        {
            **pieza,
            "versiones": versiones_por_pieza.get(pieza["id"], []),
        }
        for pieza in piezas
    ]


async def guardar_lead(
    config: Config,
    *,
    tenant_id: str,
    nombre: str = "",
    contacto: str = "",
    interes: str = "",
    sala: str = "",
) -> None:
    """Guarda un interesado.

    `tenant_id` es obligatorio y va por nombre, no posicional: un lead
    guardado contra el negocio equivocado es el dato de un cliente adentro de
    la lista de otro.
    """
    cliente = await _cliente(config)
    await (
        cliente.table("leads")
        .insert(
            {
                "tenant_id": tenant_id,
                "nombre": nombre,
                "contacto": contacto,
                "interes": interes,
                "sala": sala,
            }
        )
        .execute()
    )


async def leads_de(config: Config, tenant_id: str, *, desde_dias: int = 30) -> list[Lead]:
    """Los leads de UN tenant, del mas nuevo al mas viejo.

    El filtro por tenant no tiene default ni se puede omitir: no existe forma
    de llamar a esto y traer los de todos.
    """
    desde = (datetime.now(timezone.utc) - timedelta(days=desde_dias)).isoformat()
    cliente = await _cliente(config)
    resp = (
        await cliente.table("leads")
        .select("nombre, contacto, interes, created_at")
        .eq("tenant_id", tenant_id)
        .gte("created_at", desde)
        .order("created_at", desc=True)
        .execute()
    )
    return [
        Lead(
            nombre=fila.get("nombre", ""),
            contacto=fila.get("contacto", ""),
            interes=fila.get("interes", ""),
            creado_en=fila.get("created_at", ""),
        )
        for fila in (resp.data or [])
    ]


async def tenant_de_dominio(config: Config, dominio: str) -> DominioTenant | None:
    """De quien es este dominio, o None si no esta registrado.

    Es la defensa contra que cualquiera se lleve el agente de otro negocio.
    El dominio sale de la cabecera Origin, que el codigo de una pagina no
    puede falsear: una landing solo puede invocar al agente de su dueño.
    """
    if not dominio.strip():
        return None
    cliente = await _cliente(config)
    resp = (
        await cliente.table("tenant_dominios")
        .select("puede_declarar_tenant, tenants(slug)")
        .eq("dominio", dominio.strip().lower())
        .maybe_single()
        .execute()
    )
    if resp is None or resp.data is None:
        return None
    return DominioTenant(
        tenant_slug=resp.data["tenants"]["slug"],
        puede_declarar=bool(resp.data.get("puede_declarar_tenant")),
    )


async def obtener_tenant(config: Config, slug: str) -> Tenant:
    """Trae un tenant completo: perfil, prompt propio, servicios y voz.

    Todo lo que trae esta filtrado por el tenant que se pide. No hay
    parametro ni camino que permita traer una fila de otro tenant.
    """
    cliente = await _cliente(config)

    tenant_resp = (
        await cliente.table("tenants")
        .select("id, slug, nombre, idioma, estado, perfil_slug")
        .eq("slug", slug)
        .eq("estado", "activo")
        .maybe_single()
        .execute()
    )
    if tenant_resp is None or tenant_resp.data is None:
        raise TenantNoEncontrado(f"No hay tenant activo con slug '{slug}'")
    datos_tenant = tenant_resp.data
    tenant_id = datos_tenant["id"]

    perfil_resp = (
        await cliente.table("agent_profiles")
        .select("slug, nombre, prompt_base")
        .eq("slug", datos_tenant["perfil_slug"])
        .single()
        .execute()
    )
    perfil = PerfilTenant(**perfil_resp.data)

    config_resp = (
        await cliente.table("tenant_configs")
        .select("prompt_propio")
        .eq("tenant_id", tenant_id)
        .maybe_single()
        .execute()
    )
    prompt_propio = (config_resp.data or {}).get("prompt_propio", "") if config_resp else ""

    servicios_resp = (
        await cliente.table("services")
        .select("nombre, descripcion")
        .eq("tenant_id", tenant_id)
        .eq("activo", True)
        .execute()
    )
    servicios = tuple(Servicio(**fila) for fila in servicios_resp.data)

    voz_resp = (
        await cliente.table("voice_profiles")
        .select("proveedor, voice_id, consentimiento_aprobado")
        .eq("tenant_id", tenant_id)
        .eq("estado", "aprobado")
        .maybe_single()
        .execute()
    )
    voz = VozTenant(**voz_resp.data) if voz_resp and voz_resp.data else None

    conocimiento_resp = (
        await cliente.table("conocimiento_tenant")
        .select("id, categoria, clave, titulo, version_publicada_id")
        .eq("tenant_id", tenant_id)
        .eq("estado", "activo")
        .limit(200)
        .execute()
    )
    piezas = [
        fila for fila in (conocimiento_resp.data or [])
        if fila.get("version_publicada_id")
    ]
    versiones_por_id: dict[str, dict] = {}
    if piezas:
        ids_version = [fila["version_publicada_id"] for fila in piezas]
        versiones_resp = (
            await cliente.table("versiones_conocimiento")
            .select("id, numero, contenido")
            .eq("tenant_id", tenant_id)
            .in_("id", ids_version)
            .execute()
        )
        versiones_por_id = {
            fila["id"]: fila for fila in (versiones_resp.data or [])
        }
    conocimiento = tuple(
        ConocimientoTenant(
            id=pieza["id"],
            categoria=pieza["categoria"],
            clave=pieza["clave"],
            titulo=pieza["titulo"],
            version_id=pieza["version_publicada_id"],
            numero=versiones_por_id[pieza["version_publicada_id"]]["numero"],
            contenido=versiones_por_id[pieza["version_publicada_id"]]["contenido"],
        )
        for pieza in piezas
        if pieza["version_publicada_id"] in versiones_por_id
    )

    return Tenant(
        id=tenant_id,
        slug=datos_tenant["slug"],
        nombre=datos_tenant["nombre"],
        idioma=datos_tenant["idioma"],
        perfil=perfil,
        prompt_propio=prompt_propio,
        servicios=servicios,
        voz=voz,
        conocimiento=conocimiento,
    )
