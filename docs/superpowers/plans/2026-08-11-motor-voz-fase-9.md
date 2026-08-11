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
registry_publico    get_services, get_business_info,
                    capture_lead, transfer_to_human

registry_receptor   registry_publico
                    + crear_negocio, guardar_expediente,
                      disparar_web_factory
```

**Lo que esta fase NO hace:**

- **No implementa `disparar_web_factory`.** La fábrica de webs es otro sistema
  y su contrato no está definido. Se registra la tool y se deja fallando con un
  mensaje claro.
- **No agrega autenticación.** El registry del receptor solo lo puede pedir un
  tenant con perfil de receptor, y eso se verifica en código. Pero *quién*
  tiene derecho a hablar con el agente receptor sigue sin resolverse: ver
  Riesgos.
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

create table tools (
    nombre text primary key,
    descripcion text not null,
    -- 'publico' o 'receptor'. El del receptor es un superconjunto: incluye
    -- todas las publicas mas las suyas.
    registry text not null check (registry in ('publico', 'receptor')),
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

insert into tools (nombre, descripcion, registry) values
    ('get_services',      'Los servicios reales del negocio', 'publico'),
    ('get_business_info', 'Horarios, direccion y datos del negocio', 'publico'),
    ('capture_lead',      'Guarda a un interesado con su contacto', 'publico'),
    ('transfer_to_human', 'Deja constancia de que pidieron hablar con una persona', 'publico'),
    ('crear_negocio',     'Da de alta un negocio nuevo', 'receptor'),
    ('guardar_expediente','Guarda lo que se averiguo del negocio', 'receptor'),
    ('disparar_web_factory', 'Le pide a la fabrica de webs que arme el sitio', 'receptor');

-- Todos los verticales arrancan con las publicas.
insert into profile_tools (perfil_slug, tool)
    select p.slug, t.nombre from agent_profiles p, tools t where t.registry = 'publico';

-- Y el receptor ademas con las suyas.
insert into profile_tools (perfil_slug, tool)
    select 'receptor', nombre from tools where registry = 'receptor';
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
"""El test que bloquea el merge de la Fase 9 (spec S6).

Un tenant publico no puede alcanzar una tool del receptor, aunque el modelo
la invente o alguien la inyecte por prompt. La defensa es que el resolver no
la devuelva: no hay ninguna otra.
"""

from __future__ import annotations

import pytest

from motor_voz.brain.tools.registro import (
    RegistryDesconocido,
    ToolNoPermitida,
    registry_de,
    resolver_tool,
    tools_de,
)

PUBLICAS = {"get_services", "get_business_info", "capture_lead", "transfer_to_human"}
DEL_RECEPTOR = {"crear_negocio", "guardar_expediente", "disparar_web_factory"}


class TestQueRegistryLeToca:
    def test_el_perfil_receptor_usa_el_registry_del_receptor(self):
        assert registry_de("receptor") == "receptor"

    @pytest.mark.parametrize("perfil", ["capilar", "gastronomia", "cualquier-vertical-nuevo"])
    def test_cualquier_otro_perfil_es_publico(self, perfil):
        """Falla cerrado: un vertical nuevo no hereda las del receptor."""
        assert registry_de(perfil) == "publico"


class TestUnTenantPublicoNoAlcanzaLasDelReceptor:
    @pytest.mark.parametrize("nombre", sorted(DEL_RECEPTOR))
    def test_no_las_resuelve(self, nombre):
        with pytest.raises(ToolNoPermitida):
            resolver_tool("publico", nombre)

    @pytest.mark.parametrize("nombre", sorted(PUBLICAS))
    def test_si_resuelve_las_publicas(self, nombre):
        assert resolver_tool("publico", nombre) is not None

    def test_el_receptor_alcanza_las_dos(self):
        for nombre in PUBLICAS | DEL_RECEPTOR:
            assert resolver_tool("receptor", nombre) is not None

    def test_una_tool_inventada_no_se_resuelve(self):
        """El modelo alucina nombres de tools. No puede alcanzar nada."""
        with pytest.raises(ToolNoPermitida):
            resolver_tool("receptor", "borrar_todo")


class TestElCatalogo:
    def test_las_del_receptor_incluyen_las_publicas(self):
        """El registry del receptor es un superconjunto, no otro juego."""
        assert PUBLICAS < tools_de("receptor")

    def test_ningun_registry_esta_vacio(self):
        """Sin esta guarda, un resolver roto pasaria los tests de arriba."""
        assert tools_de("publico")
        assert tools_de("receptor")

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

Dos registries (spec S6): el publico, que usan los agentes que atienden
visitantes, y el del receptor, que ademas puede dar de alta negocios.

El del receptor es un SUPERCONJUNTO del publico, no otro juego.

Este modulo no importa livekit ni Supabase. Las tools reciben lo que
necesitan como argumento, asi las reusa el canal asincrono (WhatsApp) sin
tocar nada. Lo hace cumplir tests/test_frontera.py.
"""

from __future__ import annotations

from collections.abc import Callable

from motor_voz.brain.tools import publicas, receptor


class ToolNoPermitida(PermissionError):
    """La tool no existe, o existe y este registry no la alcanza.

    Un solo error para los dos casos a proposito: distinguirlos le diria al
    que esta probando cuales existen.
    """


class RegistryDesconocido(ValueError):
    """No hay un registry con ese nombre."""


# El mapa es la frontera. Una funcion que no este aca no es alcanzable,
# aunque exista en el modulo y aunque el modelo invente su nombre.
_PUBLICAS: dict[str, Callable] = {
    "get_services": publicas.get_services,
    "get_business_info": publicas.get_business_info,
    "capture_lead": publicas.capture_lead,
    "transfer_to_human": publicas.transfer_to_human,
}

_DEL_RECEPTOR: dict[str, Callable] = {
    "crear_negocio": receptor.crear_negocio,
    "guardar_expediente": receptor.guardar_expediente,
    "disparar_web_factory": receptor.disparar_web_factory,
}

_REGISTRIES: dict[str, dict[str, Callable]] = {
    "publico": _PUBLICAS,
    # El del receptor incluye las publicas: un receptor tambien atiende.
    "receptor": _PUBLICAS | _DEL_RECEPTOR,
}


def registry_de(perfil_slug: str) -> str:
    """Que registry le toca a un perfil.

    Falla cerrado: solo el perfil `receptor` alcanza el suyo. Un vertical
    nuevo es publico sin que nadie tenga que acordarse de declararlo.
    """
    return "receptor" if perfil_slug == "receptor" else "publico"


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

### Task 4: Las tools del receptor

**Files:**
- Create: `src/motor_voz/brain/tools/receptor.py`
- Create: `tests/test_tools_receptor.py`
- Modify: `src/motor_voz/brain/tenants/repositorio.py` (`crear_tenant`, `guardar_expediente`)

**Acá aparece el camino de escritura que hoy no existe.** `crear_negocio` es la
primera función que da de alta un tenant desde código en vez de una migración
SQL escrita a mano.

- [ ] **Step 1: Los tests que importan**

1. `crear_negocio` con un slug que ya existe **no** pisa el que está.
2. Un slug se normaliza antes de guardarse: minúsculas, sin espacios, sin
   guiones (los slugs usan guion bajo porque el nombre de sala se parte por
   guion — ver `brain/tenants/resolver.py`).
3. `disparar_web_factory` **falla con un mensaje claro**, no en silencio: la
   fábrica de webs es otro sistema y su contrato no existe todavía.

- [ ] **Step 2: Implementar**

`disparar_web_factory` así, a propósito:

```python
async def disparar_web_factory(tenant: Tenant, config: Config, **_) -> str:
    """Todavia no hay a quien pedirselo.

    Devuelve un mensaje en vez de fallar callado: el agente se lo dice al
    visitante y no queda prometiendo algo que no va a pasar.
    """
    return (
        "Todavia no puedo armar el sitio solo. Lo anoto y lo hace una persona."
    )
```

- [ ] **Step 3: Correr**

---

### Task 5: Cablear las tools en el agente

**Files:**
- Modify: `src/motor_voz/voice/agente.py`
- Modify: `tests/test_api.py` o `tests/test_motores.py` según dónde caiga

**Abrí `agente.py` antes de tocarlo.** Tiene la configuración de interrupción
y la de memoria del worker, que no se toca.

- [ ] **Step 1: Enganchar las tools al `Agent`**

Las tools van en el `Agent`, no en la `AgentSession`. El registry sale de
`registry_de(tenant.perfil.slug)`, y cada tool se envuelve para que reciba el
`tenant` y el `config` ya resueltos — así el modelo nunca elige a quién le
aplica.

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
- [ ] Pedirle a la barbería que **cree un negocio** → no puede, y lo dice sin
      inventar que lo hizo

- [ ] **Step 3: Documentar en `docs/resultados/fase9-tools.md`**

**Gate de la Fase 9 — no se avanza a la Fase 10 sin esto:**

1. Un tenant público no resuelve ninguna tool del receptor, probado por test.
2. Una tool inventada por el modelo no resuelve nada.
3. `capture_lead` guarda siempre con el tenant resuelto; no hay camino para
   pasarle otro.
4. `brain/tools/` no importa `livekit` (`test_frontera.py` en verde).
5. A oído: cada tenant responde con sus datos y el público no puede crear
   negocios.

---

## Riesgos de este plan

| Riesgo | Señal temprana | Qué hacer |
|---|---|---|
| **El registry del receptor no tiene autenticación detrás** | Cualquiera que llegue al agente receptor puede crear negocios | Es el agujero grande de la fase. El resolver verifica el *perfil*, no *quién habla*. Hoy alcanza porque al receptor solo se llega desde nuestra landing, pero **antes del panel de control hay que resolver login**. Está anotado en el brief |
| Las tools se declaran en la base y en el código, y pueden desincronizarse | El catálogo tiene una tool que el resolver no conoce, o al revés | Un test que cruce `tools` de Supabase contra `_REGISTRIES`. Va en la Task 2 si es barato, o en la 6 |
| `crear_negocio` es el primer camino de escritura y toca aislamiento | Un slug mal normalizado, o un tenant que pisa a otro | Los tests de la Task 4 son el gate. No lo apures |
| El modelo inventa argumentos, no solo nombres de tools | Una tool recibe `tenant_id` o `precio` que el visitante nunca dijo | Ninguna tool acepta identificadores por argumento. Lo que decide *a quién* se aplica sale del tenant resuelto, siempre |
| Aplicar los snippets de este plan sin leer el archivo | Se borra código que funciona, como pasó en las Fases 5-8 | Está escrito arriba y en `docs/procesos/README.md`. Leé el archivo primero |
