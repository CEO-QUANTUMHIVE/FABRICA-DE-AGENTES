# Motor de Voz — Fase 9: tools y registries — Plan de Implementación

**Escrito:** 2026-08-11
**Depende de:** Fases 5-8 cerradas y verificadas en producción ✅
**Spec:** [§6](../specs/2026-08-08-motor-voz-design.md) y §11 del diseño

---

## Una advertencia sobre este plan

**Los snippets de código que siguen son de lo que hay HOY, no de lo que
habrá cuando los apliques.** El plan de las Fases 5-8 se escribió un día antes
de ejecutarse y sus snippets ya borraban cuatro cosas que funcionaban: la
calibración del VAD, la ruta `/api/voces`, la configuración de interrupción y
la resolución de voz.

Por eso este plan **da código completo solo donde el código es sutil** — el
resolver, el test que bloquea, la migración — y en el resto dice qué cambiar y
dónde, para que abras el archivo real.

**Leé el archivo antes de aplicar un snippet. Siempre.**

---

## Alcance

Hoy el agente **sabe** cosas (su prompt, sus servicios) pero no **puede hacer**
nada: no tiene herramientas. Esta fase le da capacidades, y las separa en dos
juegos según con quién habla.

```text
registry_publico   el visitante que llega a la landing
                   get_services, get_business_info,
                   capture_lead, transfer_to_human

registry_interno   el dueño del negocio, en su panel de control
                   registry_publico
                   + get_mis_leads, get_mis_metricas, get_mis_conversaciones
```

### Divergencia deliberada con el spec

**El §6 del spec le da `crear_negocio`, `guardar_expediente` y
`disparar_web_factory` al registry del receptor. Este plan NO las implementa
como tools, por decisión de Sergio el 2026-08-11:**

> Nadie puede crear negocios ni agentes salvo el dueño de QuantumHive. El
> dueño de un negocio, hablando con su agente en modo interno, tampoco puede
> crear nada.

Es más seguro que lo que decía el spec. Si crear un negocio fuera una tool
conversacional, cualquiera que llegue al agente receptor podría dar de alta
uno convenciéndolo — y taparlo con autenticación es defender un agujero que no
hacía falta abrir.

**Dar de alta un negocio es una operación de la fábrica, no de una
conversación.** Va por el camino de escritura de `repositorio.py`, llamado por
la API de la fábrica detrás de login de administrador. No es de esta fase.

El modo interno del dueño es **solo de lectura sobre lo suyo**. Eso también
cierra el otro riesgo: aunque a alguien se le filtre el acceso al modo interno,
lo peor que puede hacer es leer, no crear.

**Actualizar el §6 del spec** para que refleje esto.

**Lo que esta fase NO hace:**

- **No crea nada.** Ni negocios, ni agentes, ni servicios. Ninguna tool
  escribe, salvo `capture_lead`, que agrega un interesado y nada más.
- **No agrega autenticación.** El modo interno se resuelve por perfil, y quién
  tiene derecho a pedirlo se resuelve antes del panel de control. Ver Riesgos.
- **No toca `usage_daily` ni el kill-switch.** Eso es Fase 10.

## Estado verificado del código (2026-08-11)

Antes de escribir este plan se leyeron los archivos, no la memoria:

- `brain/tenants/repositorio.py` — único punto que habla con Supabase, y hay un
  test con AST que lo hace cumplir. **Toda tool que lea datos pasa por acá.**
- `brain/tenants/modelos.py` — `Tenant` tiene `perfil: PerfilTenant`. El
  `perfil.slug` es lo que decide qué registry le toca (`receptor` vs el resto).
- `brain/contexto.py` — `construir_contexto(tenant, motor, canal)` arma el
  prompt. Las tools no van en el prompt: van en la sesión.
- `voice/agente.py` — `AgentSession(**motores.componentes(config), **extras)` y
  `Receptor(prompt)`. Las tools se enganchan en el `Agent`, no en la sesión.
- `tests/test_frontera.py` — `brain/` no puede importar `livekit`. **Las tools
  van en `brain/` y no pueden importar livekit**, así WhatsApp las reusa.

---

## FASE 9 — Capacidades del agente

### Task 1: Esquema de tools y leads

**Files:**
- Create: `supabase/migrations/0006_tools_y_leads.sql`

- [ ] **Step 1: Escribir la migración**

```sql
-- Que puede HACER un agente, no solo que sabe.
--
-- Tres tablas y no una porque hay tres niveles de decision:
--   tools          que capacidades existen en el motor
--   profile_tools  que puede un vertical (todas las barberias)
--   tenant_tools   que puede este negocio en particular
--
-- El orden importa: tenant_tools gana sobre profile_tools. Asi se le puede
-- dar o quitar una capacidad a un cliente sin tocar a los demas de su rubro.
--
-- NINGUNA tool crea negocios ni agentes. Dar de alta un negocio es una
-- operacion de la fabrica detras de login, no algo que un agente haga porque
-- alguien se lo pida bien.

create table tools (
    nombre text primary key,
    descripcion text not null,
    -- 'publico' es el visitante; 'interno' es el dueño del negocio en su
    -- panel. El interno es un superconjunto: tambien atiende.
    registry text not null check (registry in ('publico', 'interno')),
    -- Ninguna tool de esta fase escribe, salvo capture_lead. Se deja
    -- declarado para que agregar una que escriba sea una decision visible.
    escribe boolean not null default false,
    created_at timestamptz not null default now()
);

create table profile_tools (
    perfil_slug text not null references agent_profiles(slug) on delete cascade,
    tool text not null references tools(nombre) on delete cascade,
    primary key (perfil_slug, tool)
);

create table tenant_tools (
    tenant_id uuid not null references tenants(id) on delete cascade,
    tool text not null references tools(nombre) on delete cascade,
    -- false quita una capacidad que el perfil si da. Es un override, no un
    -- borrado: si la fila no existe, manda el perfil.
    habilitada boolean not null default true,
    primary key (tenant_id, tool)
);

create table leads (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id) on delete cascade,
    nombre text not null default '',
    contacto text not null default '',
    interes text not null default '',
    -- De que sala salio. Sirve para reconstruir la conversacion cuando el
    -- lead no cierra y hay que entender por que.
    sala text not null default '',
    created_at timestamptz not null default now()
);
create index leads_tenant_id_idx on leads(tenant_id, created_at desc);

-- ── Catalogo ───────────────────────────────────────────────────────────

insert into tools (nombre, descripcion, registry, escribe) values
    ('get_services',      'Los servicios reales del negocio', 'publico', false),
    ('get_business_info', 'Horarios, direccion y datos del negocio', 'publico', false),
    ('capture_lead',      'Guarda a un interesado con su contacto', 'publico', true),
    ('transfer_to_human', 'Deja constancia de que pidieron hablar con una persona', 'publico', false),
    ('get_mis_leads',     'Los interesados que dejaron contacto en este negocio', 'interno', false),
    ('get_mis_metricas',  'Cuantas conversaciones hubo y como salieron', 'interno', false),
    ('get_mis_conversaciones', 'El historial de charlas de este negocio', 'interno', false);

-- Todos los verticales arrancan con las publicas.
insert into profile_tools (perfil_slug, tool)
    select p.slug, t.nombre from agent_profiles p, tools t where t.registry = 'publico';

-- Las internas las tiene cualquier vertical: son de lectura sobre lo propio.
-- Lo que decide si se alcanzan no es el vertical, es el MODO de la sesion.
insert into profile_tools (perfil_slug, tool)
    select p.slug, t.nombre from agent_profiles p, tools t where t.registry = 'interno';
```

- [ ] **Step 2: Aplicar**

Ver [`docs/procesos/aplicar-una-migracion-de-supabase.md`](../../procesos/aplicar-una-migracion-de-supabase.md).
El MCP no ve este proyecto; va con el CLI.

- [ ] **Step 3: Verificar el gate de datos**

```sql
select p.perfil_slug, count(*) from profile_tools p group by 1 order by 1;
```

Esperado: `receptor` con 7, cada otro vertical con 4.

- [ ] **Step 4: Commit**

---

### Task 2: El resolver de tools — y el test que bloquea

**Files:**
- Create: `src/motor_voz/brain/tools/__init__.py`
- Create: `src/motor_voz/brain/tools/registro.py`
- Create: `tests/test_registro_de_tools.py`

Esta es la task crítica de la fase. **El spec es explícito: la verificación va
en el resolver, no en el prompt.** Un modelo puede inventar el nombre de una
tool, y alguien puede intentar inyectarla por prompt. Lo único que lo detiene
es que el resolver no la devuelva.

- [ ] **Step 1: Escribir los tests que fallan**

`tests/test_registro_de_tools.py`:

```python
"""El test que bloquea el merge de la Fase 9.

Quien habla desde una landing publica no puede alcanzar una tool interna,
aunque el modelo la invente o alguien la inyecte por prompt. La defensa es
que el resolver no la devuelva: no hay ninguna otra.
"""

from __future__ import annotations

import pytest

from motor_voz.brain.tools.registro import (
    MODO_POR_DEFECTO,
    RegistryDesconocido,
    ToolNoPermitida,
    registry_de,
    resolver_tool,
    tools_de,
)

PUBLICAS = {"get_services", "get_business_info", "capture_lead", "transfer_to_human"}
INTERNAS = {"get_mis_leads", "get_mis_metricas", "get_mis_conversaciones"}


class TestQueRegistryLeToca:
    def test_el_modo_interno_alcanza_el_registry_interno(self):
        assert registry_de("interno") == "interno"

    @pytest.mark.parametrize("modo", ["publico", "", "  ", "INTERNO", "admin", "inventado"])
    def test_cualquier_otra_cosa_es_publica(self, modo):
        """Falla cerrado: un modo vacio, mal escrito o inventado es publico.

        Es lo que decide si alguien ve los leads de un negocio. Un typo no
        puede abrirlo.
        """
        assert registry_de(modo) == "publico"

    def test_el_default_es_publico(self):
        assert MODO_POR_DEFECTO == "publico"


class TestDesdeLaLandingNoSeAlcanzaLoInterno:
    @pytest.mark.parametrize("nombre", sorted(INTERNAS))
    def test_no_resuelve_las_internas(self, nombre):
        with pytest.raises(ToolNoPermitida):
            resolver_tool("publico", nombre)

    @pytest.mark.parametrize("nombre", sorted(PUBLICAS))
    def test_si_resuelve_las_publicas(self, nombre):
        assert resolver_tool("publico", nombre) is not None

    def test_el_modo_interno_alcanza_las_dos(self):
        for nombre in PUBLICAS | INTERNAS:
            assert resolver_tool("interno", nombre) is not None

    def test_una_tool_inventada_no_se_resuelve(self):
        """El modelo alucina nombres de tools. No puede alcanzar nada."""
        with pytest.raises(ToolNoPermitida):
            resolver_tool("interno", "borrar_todo")


class TestNadieCreaNegociosHablando:
    """La regla de Sergio, 2026-08-11: ni el visitante ni el dueño crean nada.

    Dar de alta un negocio es una operacion de la fabrica detras de login. Si
    alguna vez aparece como tool, este test se rompe y hay que discutirlo.
    """

    @pytest.mark.parametrize(
        "nombre", ["crear_negocio", "crear_agente", "crear_tenant", "disparar_web_factory"]
    )
    @pytest.mark.parametrize("modo", ["publico", "interno"])
    def test_ningun_modo_alcanza_una_tool_que_cree(self, modo, nombre):
        with pytest.raises(ToolNoPermitida):
            resolver_tool(modo, nombre)


class TestElCatalogo:
    def test_lo_interno_incluye_lo_publico(self):
        """El dueño tambien atiende: es un superconjunto, no otro juego."""
        assert PUBLICAS < tools_de("interno")

    def test_ningun_registry_esta_vacio(self):
        """Sin esta guarda, un resolver roto pasaria los tests de arriba."""
        assert tools_de("publico")
        assert tools_de("interno")

    def test_un_registry_que_no_existe_falla(self):
        with pytest.raises(RegistryDesconocido):
            tools_de("inventado")
```

- [ ] **Step 2: Correr para verificar que falla**

```bash
uv run pytest tests/test_registro_de_tools.py -v
```

Esperado: `ModuleNotFoundError: No module named 'motor_voz.brain.tools'`.

- [ ] **Step 3: Implementar `registro.py`**

La forma importa. **El registry se declara como un mapa de nombre a función, y
`resolver_tool` es la única puerta.** Nada de `getattr` sobre un módulo: con
eso, cualquier función que exista pasa a ser alcanzable.

```python
"""Que puede hacer un agente, y quien puede hacer que.

Dos registries, y lo que decide cual toca es el MODO de la sesion, no el
vertical del negocio:

    publico   el visitante que llega a la landing
    interno   el dueño del negocio, en su panel de control

El interno es un SUPERCONJUNTO del publico: el dueño tambien atiende.

NINGUN registry crea negocios ni agentes. Dar de alta es una operacion de la
fabrica detras de login, no algo que un agente haga porque se lo pidan bien.
Hay un test que lo fija (TestNadieCreaNegociosHablando): si alguna vez
aparece una tool que cree, se rompe y hay que discutirlo.

Este modulo no importa livekit ni Supabase. Las tools reciben lo que
necesitan como argumento, asi las reusa el canal asincrono (WhatsApp) sin
tocar nada. Lo hace cumplir tests/test_frontera.py.
"""

from __future__ import annotations

from collections.abc import Callable

from motor_voz.brain.tools import internas, publicas

MODO_POR_DEFECTO = "publico"
"""Lo que se usa cuando nadie dijo nada, y cuando lo que dijeron no se entiende.

Esto decide si alguien ve los leads de un negocio. Un modo vacio, mal escrito
o inventado tiene que caer del lado seguro.
"""


class ToolNoPermitida(PermissionError):
    """La tool no existe, o existe y este registry no la alcanza.

    Un solo error para los dos casos a proposito: distinguirlos le diria al
    que esta probando cuales existen.
    """


class RegistryDesconocido(ValueError):
    """No hay un registry con ese nombre."""


# El mapa es la frontera. Una funcion que no este aca no es alcanzable,
# aunque exista en el modulo y aunque el modelo invente su nombre. Por eso es
# un mapa explicito y no un getattr sobre el modulo.
_PUBLICAS: dict[str, Callable] = {
    "get_services": publicas.get_services,
    "get_business_info": publicas.get_business_info,
    "capture_lead": publicas.capture_lead,
    "transfer_to_human": publicas.transfer_to_human,
}

_INTERNAS: dict[str, Callable] = {
    "get_mis_leads": internas.get_mis_leads,
    "get_mis_metricas": internas.get_mis_metricas,
    "get_mis_conversaciones": internas.get_mis_conversaciones,
}

_REGISTRIES: dict[str, dict[str, Callable]] = {
    "publico": _PUBLICAS,
    "interno": _PUBLICAS | _INTERNAS,
}


def registry_de(modo: str) -> str:
    """Que registry le toca a un modo de sesion.

    Falla cerrado: SOLO el string exacto `interno` abre lo interno. Vacio,
    con mayusculas, con espacios o inventado cae en publico.

    Se lista lo que ABRE, no lo que cierra. Comparar contra lo que cierra
    —`if modo != "publico"`— dejaria pasar cualquier valor raro.
    """
    return "interno" if modo == "interno" else MODO_POR_DEFECTO


def tools_de(registry: str) -> set[str]:
    """Los nombres que alcanza un registry."""
    if registry not in _REGISTRIES:
        raise RegistryDesconocido(f"No existe el registry '{registry}'.")
    return set(_REGISTRIES[registry])


def resolver_tool(registry: str, nombre: str) -> Callable:
    """La unica puerta. Si no pasa por aca, no se ejecuta."""
    if registry not in _REGISTRIES:
        raise RegistryDesconocido(f"No existe el registry '{registry}'.")
    funcion = _REGISTRIES[registry].get(nombre)
    if funcion is None:
        raise ToolNoPermitida(f"El registry '{registry}' no alcanza la tool '{nombre}'.")
    return funcion
```

**De dónde sale el `modo`.** Del token, firmado, igual que el tenant y el
motor — nunca de algo que mande el navegador. Y `POST /api/token` solo puede
conceder `interno` cuando sepa quién pide, o sea **cuando exista login**. Hasta
entonces la API siempre emite `publico`, y el modo interno solo se alcanza en
desarrollo. Eso es de la fase de autenticación, no de esta.

- [ ] **Step 4: Correr — y correr la frontera**

```bash
uv run pytest tests/test_registro_de_tools.py tests/test_frontera.py -v
```

**Gate de la Task 2:** los tres tests de
`TestUnTenantPublicoNoAlcanzaLasDelReceptor` en verde, y `test_frontera` sigue
pasando ahora que cubre `brain/tools/`.

- [ ] **Step 5: Commit**

---

### Task 3: Las tools públicas

**Files:**
- Create: `src/motor_voz/brain/tools/publicas.py`
- Create: `tests/test_tools_publicas.py`
- Modify: `src/motor_voz/brain/tenants/repositorio.py` (agregar `guardar_lead`)

- [ ] **Step 1: Escribir los tests primero**

Cuatro cosas que tienen que quedar fijadas:

1. `get_services` devuelve **solo** los del tenant que se le pasa.
2. `capture_lead` guarda con el `tenant_id` del tenant resuelto, **nunca** con
   uno que venga por argumento.
3. `get_business_info` no filtra datos que el tenant no declaró.
4. `transfer_to_human` no promete nada que no exista: hoy deja constancia y
   avisa, no transfiere.

- [ ] **Step 2: Implementar**

Cada tool recibe el `Tenant` ya resuelto como primer argumento. **Ninguna
acepta un `tenant_id`**: si lo aceptara, el modelo podría pasarle el de otro
negocio.

```python
async def capture_lead(tenant: Tenant, config: Config, *, nombre: str = "",
                       contacto: str = "", interes: str = "", sala: str = "") -> str:
    """Guarda un interesado. El tenant sale del argumento, no del modelo."""
```

- [ ] **Step 3: Agregar `guardar_lead` al repositorio**

Va en `repositorio.py` porque **es el único punto que habla con Supabase**, y
hay un test con AST que lo hace cumplir. No lo esquives.

- [ ] **Step 4: Correr todo**

---

### Task 4: Las tools internas

**Files:**
- Create: `src/motor_voz/brain/tools/internas.py`
- Create: `tests/test_tools_internas.py`
- Modify: `src/motor_voz/brain/tenants/repositorio.py` (`leads_de`, `metricas_de`)

Las tres son **de lectura sobre lo propio**. Ninguna escribe. Es lo que el
dueño ve cuando le pregunta a su agente en el panel: *"¿cuántos contactos me
dejaron esta semana?"*, *"¿cómo vengo?"*.

- [ ] **Step 1: Los tests que importan**

1. `get_mis_leads` devuelve **solo** los del tenant resuelto. Con dos tenants
   sembrados, los conjuntos son disjuntos.
2. **Ninguna acepta un `tenant_id` por argumento.** Si lo aceptara, el modelo
   podría pasarle el de otro negocio, y el modelo obedece a quien le habla.
3. `get_mis_metricas` con un tenant sin conversaciones devuelve ceros, no
   rompe. Un negocio recién dado de alta es el caso normal, no el raro.
4. Los leads salen ordenados por fecha, del más nuevo al más viejo: nadie
   pregunta por el contacto de hace tres meses primero.

- [ ] **Step 2: Implementar**

Firma de las tres, sin excepción:

```python
async def get_mis_leads(tenant: Tenant, config: Config, *, desde_dias: int = 30) -> str:
    """El tenant sale del argumento, nunca del modelo."""
```

`get_mis_conversaciones` depende de que existan `sessions` y
`conversation_turns`, **que son de la Fase 10**. Devolvé un mensaje honesto en
vez de fallar callado, igual que se hace con lo que todavía no existe:

```python
async def get_mis_conversaciones(tenant: Tenant, config: Config, **_) -> str:
    """Todavia no se guardan las conversaciones: es de la Fase 10."""
    return "Todavia no estoy guardando el historial de charlas."
```

- [ ] **Step 3: Agregar las lecturas al repositorio**

`leads_de(config, tenant_id)` y `metricas_de(config, tenant_id)` van en
`repositorio.py`, con su `.eq("tenant_id", ...)`. Es el único punto que habla
con Supabase y hay un test con AST que lo hace cumplir.

- [ ] **Step 4: Correr**

---

### Task 5: Cablear las tools en el agente

**Files:**
- Modify: `src/motor_voz/voice/agente.py`
- Modify: `tests/test_api.py` o `tests/test_motores.py` según dónde caiga

**Abrí `agente.py` antes de tocarlo.** Tiene la configuración de interrupción
y la de memoria del worker, que no se toca.

- [ ] **Step 1: Enganchar las tools al `Agent`**

Las tools van en el `Agent`, no en la `AgentSession`. El registry sale de
`registry_de(modo)`, y **el modo sale de la metadata firmada del token**, igual
que el motor y el tenant. Nunca de algo que mande el navegador.

Cada tool se envuelve para que reciba el `tenant` y el `config` ya resueltos —
así el modelo nunca elige a quién le aplica.

- [ ] **Step 1b: Que el modo llegue firmado**

`api/servidor.py` mete `modo` en la metadata del token. **En producción siempre
`publico`**, porque conceder `interno` requiere saber quién pide y eso todavía
no existe. Un test que lo fije:

```python
async def test_en_produccion_el_token_nunca_concede_modo_interno(self, cliente):
    """Conceder interno sin login seria regalar los leads de un negocio."""
```

- [ ] **Step 2: Verificar que la frontera sigue en pie**

`voice/agente.py` **sí** puede importar `brain/tools`. Al revés no.

- [ ] **Step 3: Correr toda la suite**

---

### Task 6: Verificación y gate de la Fase 9

- [ ] **Step 1: Suite completa, incluida integración**

- [ ] **Step 2: Probar a oído con los dos tenants**

Con el nivel 1 en local (ver
[`docs/procesos/probar-un-tenant-a-oido.md`](../../procesos/probar-un-tenant-a-oido.md)):

- [ ] Preguntarle a la barbería por sus servicios → los suyos, no los de
      QuantumHive
- [ ] Dejarle un contacto → aparece en `leads` con el `tenant_id` correcto
- [ ] Pedirle que **cree un negocio** → no puede, y lo dice sin inventar que lo
      hizo
- [ ] Pedirle **los leads** desde la landing pública → no puede. Es el que más
      importa: ahí es donde se filtrarían los datos de un cliente

- [ ] **Step 3: Documentar en `docs/resultados/fase9-tools.md`**

**Gate de la Fase 9 — no se avanza a la Fase 10 sin esto:**

1. Desde el modo público no se resuelve ninguna tool interna, probado por test.
2. Una tool inventada por el modelo no resuelve nada.
3. **Ningún modo alcanza una tool que cree negocios o agentes.** Es la regla
   de Sergio y hay un test que se rompe si alguien la agrega.
4. `capture_lead` guarda siempre con el tenant resuelto; no hay camino para
   pasarle otro.
5. En producción el token nunca concede modo interno.
6. `brain/tools/` no importa `livekit` (`test_frontera.py` en verde).
7. A oído: cada tenant responde con sus datos, y desde la landing no se
   alcanzan ni los leads ni la creación.

---

## Riesgos de este plan

| Riesgo | Señal temprana | Qué hacer |
|---|---|---|
| **El modo interno no tiene autenticación detrás** | Alguien alcanza los leads de un negocio sin ser su dueño | El resolver verifica el *modo*, no *quién habla*. Por eso en producción la API **nunca** concede `interno`: hasta que exista login, el modo interno solo se alcanza en desarrollo. Es la fase siguiente y va **antes del panel de control** |
| Las tools se declaran en la base y en el código, y pueden desincronizarse | El catálogo tiene una tool que el resolver no conoce, o al revés | Un test que cruce `tools` de Supabase contra `_REGISTRIES`. Va en la Task 2 si es barato, o en la 6 |
| Alguien agrega una tool que crea negocios | Vuelve el agujero que esta fase evitó | `TestNadieCreaNegociosHablando` se rompe. Si se rompe, no se arregla el test: se discute la decisión |
| El modelo inventa argumentos, no solo nombres de tools | Una tool recibe `tenant_id` o `precio` que el visitante nunca dijo | Ninguna tool acepta identificadores por argumento. Lo que decide *a quién* se aplica sale del tenant resuelto, siempre |
| `get_mis_conversaciones` promete algo que no existe | El agente dice que va a mostrar el historial y no muestra nada | Devuelve un mensaje honesto. Las tablas son de la Fase 10 |
| Aplicar los snippets de este plan sin leer el archivo | Se borra código que funciona, como pasó en las Fases 5-8 | Está escrito arriba y en `docs/procesos/README.md`. Leé el archivo primero |
