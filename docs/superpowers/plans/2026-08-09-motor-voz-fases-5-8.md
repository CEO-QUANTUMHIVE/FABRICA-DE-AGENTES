# Motor de Voz — Multi-tenant, Fases 5 a 8 — Plan de Implementación

> **Para agentes ejecutores:** SUB-SKILL REQUERIDA: usar `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para ejecutar tarea por tarea. Los pasos usan checkbox (`- [ ]`) para seguimiento.

**Goal:** Que el runtime que ya habla (Fases 0-4, en producción) atienda a más de un tenant sobre el mismo código, con datos y voz propios por tenant, y con el aislamiento entre tenants probado por test — no por promesa.

**Architecture:** El tenant se resuelve a partir del nombre de sala, que viaja firmado dentro del token de LiveKit (el navegador no lo puede falsear: `VideoGrants(room=...)` restringe a qué sala se puede entrar). Toda esa resolución vive en `brain/`, que sigue sin importar `livekit`. Un único módulo (`brain/tenants/repositorio.py`) habla con Supabase; nadie más instancia el cliente. El aislamiento depende de que cada query de ese módulo filtre por `tenant_id` — Supabase usa `SERVICE_ROLE_KEY`, que saltea RLS, así que RLS no es la defensa real.

**Tech Stack:** `supabase-py` (cliente async, `acreate_client`) · Supabase Postgres · lo ya instalado (`livekit-agents`, `pytest`, `pytest-asyncio`)

---

## Alcance de este plan

Cubre las **Fases 5 a 8** del spec `docs/superpowers/specs/2026-08-08-motor-voz-design.md`: Supabase, tenants, perfiles, servicios, resolver, capa única de repositorios, context builder dinámico y voz por tenant.

**Fuera de este plan** (van en planes propios, después de que este cierre):
- Fase 9 — tools y registries (`registry_publico` / `registry_receptor`)
- Fase 10 — límites de gasto, kill-switch, degradación, eventos a Quantum Core
- Fase 11 — modo asíncrono (WhatsApp, Telegram, guiones cacheados)

Estas tres dependen de que el tenant ya se resuelva (este plan), así que no pueden arrancar antes.

## Estado verificado del código (2026-08-09)

Leído el código real, no el plan viejo:

- `voice/agente.py` arma la sesión llamando a `motores.componentes(config)` y construye `Receptor(config.motor)`, que llama a `brain/prompt.construir(motor=motor, canal="web")` con una identidad fija (`IDENTIDAD`, constante).
- **El nombre de sala cambió después de escribir este plan** (commit `c0acfa8`, selector de voces de Gemini). Hoy es `demo-{motor}-{voz}-{aleatorio}` — ej. `demo-gemini-Leda-a1b2c3` — con dos parsers en `agente.py`: `motor_de_la_sala` (lee `partes[1]`) y `voz_de_la_sala` (lee `partes[2]`).

  **Este plan lo extiende a `demo-{tenant}-{motor}-{voz}-{aleatorio}`**, o sea:

  ```text
  demo - quantumhive -  gemini  -  Leda  -  a1b2c3
   [0]      [1]           [2]       [3]      [4]
          tenant         motor      voz    aleatorio
  ```

  Los slugs de tenant no llevan guiones (`quantumhive`, `demo_capilar` usan guión bajo), así que partir por `-` sigue siendo seguro. Consecuencias, todas cubiertas en la Task 9:
  - `motor_de_la_sala` pasa de `partes[1]` a `partes[2]`.
  - `voz_de_la_sala` pasa de `partes[2]` a `partes[3]`.
  - `tenant_de_la_sala` (Task 5) lee `partes[1]` — ya está escrito así, no cambia.
  - `tests/test_api.py::test_el_motor_va_en_el_nombre_de_la_sala` afirma el formato viejo y hay que actualizarlo.
- `api/servidor.py` no sabe nada de tenants: emite token con `nivel` únicamente.
- `config.py` no tiene campos de Supabase, aunque `.env.example` los menciona vacíos.
- No existe ningún cliente de Supabase en el repo. No existe proyecto de Supabase para este repo (los secrets de Secret Manager `motor-voz-*` no incluyen Supabase; el que existe, `hermes-supabase-service-role`, es de otro proyecto).
- `brain/` tiene hoy `prompt.py` y `normalizar.py`. Sigue sin importar `livekit`, cubierto por `tests/test_frontera.py` (recorre `brain/` entero con `rglob`, así que los módulos nuevos de este plan quedan cubiertos automáticamente sin tocar ese test).

## Dependencia externa de este plan

**Antes de la Task 2** tiene que existir un proyecto de Supabase para este repo, con su URL y su `service_role` key. La `service_role` key no se puede obtener por MCP (adrede: expone un bypass de RLS) — la trae Sergio del dashboard de Supabase y la sube como hizo con las demás claves:

```bash
echo -n "https://xxxxx.supabase.co" | gcloud secrets create motor-voz-supabase-url --data-file=-
echo -n "eyJ..." | gcloud secrets create motor-voz-supabase-service-role --data-file=-
```

El proyecto en sí (crear la instancia) sí se puede hacer con `mcp__supabase__create_project` si no existe uno. La Task 2 asume que ya está creado y da por sentado `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` en el `.env` local para poder aplicar la migración y correr los tests de integración.

---

## FASE 5 — Supabase, tenants, perfiles, servicios

### Task 1: `Config` gana los campos de Supabase, y el proyecto suma la dependencia

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/motor_voz/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Agregar `supabase` a las dependencias y el marker `integracion`**

En `pyproject.toml`, agregar `"supabase>=2.9,<3"` a `dependencies` (junto a `python-dotenv`), y agregar el marker nuevo:

```toml
markers = [
    "smoke: llama APIs reales y consume creditos. No corre por defecto.",
    "integracion: requiere Supabase real (sin costo, pero si red). No corre por defecto.",
]
addopts = "-m 'not smoke and not integracion'"
```

- [ ] **Step 2: Instalar**

```bash
uv sync
```

Esperado: agrega `supabase` y sus dependencias (`postgrest`, `gotrue`, etc.) a `.venv/`.

- [ ] **Step 3: Escribir los tests que fallan**

Agregar al final de `tests/test_config.py`:

```python
def test_carga_los_campos_de_supabase():
    entorno = ENTORNO_COMPLETO | {
        "SUPABASE_URL": "https://xyz.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "clave-falsa",
    }
    config = cargar(entorno)
    assert config.supabase_url == "https://xyz.supabase.co"
    assert config.supabase_service_role_key == "clave-falsa"


def test_supabase_es_opcional_y_default_vacio():
    """Las fases 0-4 no necesitan Supabase: no puede romper lo que ya anda."""
    config = cargar(ENTORNO_COMPLETO)
    assert config.supabase_url == ""
    assert config.supabase_service_role_key == ""
```

- [ ] **Step 4: Correr para verificar que fallan**

```bash
uv run pytest tests/test_config.py -v
```

Esperado: FALLA con `AttributeError: 'Config' object has no attribute 'supabase_url'`.

- [ ] **Step 5: Implementar**

En `src/motor_voz/config.py`, agregar dos campos al `dataclass Config` (después de `azure_api_key: str`):

```python
    supabase_url: str
    supabase_service_role_key: str
```

Y en `cargar()`, agregar antes del `)` de cierre:

```python
        supabase_url=e.get("SUPABASE_URL", "").strip(),
        supabase_service_role_key=e.get("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
```

No van en `OBLIGATORIAS`: las Fases 0-4 (motor sin tenants) siguen funcionando sin Supabase configurado. Se validan recién cuando algo intenta usarlas, en el repositorio de la Task 4.

- [ ] **Step 6: Correr para verificar que pasan**

```bash
uv run pytest tests/test_config.py -v
```

Esperado: `8 passed`.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src/motor_voz/config.py tests/test_config.py
git commit -m "feat(fase5): Config admite credenciales de Supabase, opcionales"
```

---

### Task 2: Esquema de Supabase y los dos tenants del MVP

**Files:**
- Create: `supabase/migrations/0001_tenants_perfiles_servicios_voces.sql`

- [ ] **Step 1: Escribir la migración**

`supabase/migrations/0001_tenants_perfiles_servicios_voces.sql`:

```sql
-- Esquema minimo para las Fases 5-8: tenants, perfiles de vertical,
-- servicios y voces. Las tablas de tools, sesiones, leads y uso diario
-- (Fases 9-10) se agregan en sus propias migraciones cuando toque.

create extension if not exists "pgcrypto";

-- Perfil de vertical: la identidad base que comparten todos los tenants
-- de ese rubro. "receptor" es QuantumHive; "capilar" es la barberia de
-- prueba que existe solo para validar aislamiento (spec S5).
create table agent_profiles (
    slug text primary key,
    nombre text not null,
    prompt_base text not null,
    created_at timestamptz not null default now()
);

create table tenants (
    id uuid primary key default gen_random_uuid(),
    slug text unique not null,
    nombre text not null,
    perfil_slug text not null references agent_profiles(slug),
    idioma text not null default 'es',
    estado text not null default 'activo' check (estado in ('activo', 'pausado')),
    created_at timestamptz not null default now()
);

create table tenant_configs (
    tenant_id uuid primary key references tenants(id) on delete cascade,
    prompt_propio text not null default '',
    zona_horaria text not null default 'America/Argentina/Buenos_Aires',
    ajustes jsonb not null default '{}'::jsonb
);

create table services (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id) on delete cascade,
    nombre text not null,
    descripcion text not null default '',
    activo boolean not null default true,
    created_at timestamptz not null default now()
);
create index services_tenant_id_idx on services(tenant_id);

-- consentimiento_aprobado es obligatorio antes de usar una voz clonada:
-- spec S19 y S11. Sin fila en estado 'aprobado', el tenant no tiene voz
-- propia y el motor cae a la voz por defecto de Fish.
create table voice_profiles (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id) on delete cascade,
    proveedor text not null default 'fishaudio',
    voice_id text not null,
    consentimiento_aprobado boolean not null default false,
    consentimiento_registrado_en timestamptz,
    estado text not null default 'pendiente' check (estado in ('pendiente', 'aprobado', 'rechazado')),
    created_at timestamptz not null default now()
);
create index voice_profiles_tenant_id_idx on voice_profiles(tenant_id);

-- ── Datos semilla: los dos tenants del MVP (spec S5) ──────────────

insert into agent_profiles (slug, nombre, prompt_base) values
    ('receptor', 'Receptor QuantumHive',
     'Sos el asistente virtual de QuantumHive, una empresa argentina que le da vida digital a los negocios: les hace la web, les arma un empleado virtual que atiende clientes, les da voz, avatar y un catalogo que vende. Hablas espanol rioplatense, de vos.'),
    ('capilar', 'Barberia (demo)',
     'Sos el asistente de una barberia. Atendes consultas de turnos, precios de cortes y horarios. Sos calido, directo y hablas espanol rioplatense, de vos. Esta barberia es una demo: existe para probar que el motor aisla bien los datos entre negocios distintos.');

insert into tenants (slug, nombre, perfil_slug, idioma) values
    ('quantumhive', 'QuantumHive', 'receptor', 'es'),
    ('demo_capilar', 'Barberia Demo', 'capilar', 'es');

insert into tenant_configs (tenant_id, prompt_propio)
    select id, '' from tenants where slug = 'quantumhive';
insert into tenant_configs (tenant_id, prompt_propio)
    select id, 'Atendes en la barberia demo de QuantumHive, usada solo para probar aislamiento entre tenants. No es un negocio real.'
    from tenants where slug = 'demo_capilar';

insert into services (tenant_id, nombre, descripcion)
    select id, 'Web inteligente', 'Pagina que conversa con el visitante y responde por si sola' from tenants where slug = 'quantumhive';
insert into services (tenant_id, nombre, descripcion)
    select id, 'Empleado virtual', 'Agente que atiende clientes por voz, WhatsApp y Telegram' from tenants where slug = 'quantumhive';

insert into services (tenant_id, nombre, descripcion)
    select id, 'Corte clasico', 'Corte de cabello tradicional' from tenants where slug = 'demo_capilar';
insert into services (tenant_id, nombre, descripcion)
    select id, 'Afeitado a navaja', 'Afeitado tradicional con toalla caliente' from tenants where slug = 'demo_capilar';

-- Voz de QuantumHive: la clonada VOZ-003 que ya esta en produccion
-- (ver docs/CONTINUAR-ACA.md). demo_capilar usa un voice_id de catalogo
-- de Fish, sin clonar — no existe una persona real detras, asi que no
-- hay consentimiento que registrar. AJUSTAR el voice_id de demo_capilar
-- por uno real del catalogo de Fish antes del gate de oido de la Fase 8.
insert into voice_profiles (tenant_id, proveedor, voice_id, consentimiento_aprobado, consentimiento_registrado_en, estado)
    select id, 'fishaudio', '63f9f124b9401b8d8d9846c4b0d75f1a', true, now(), 'aprobado'
    from tenants where slug = 'quantumhive';
insert into voice_profiles (tenant_id, proveedor, voice_id, consentimiento_aprobado, consentimiento_registrado_en, estado)
    select id, 'fishaudio', 'e7e1049270f649f7bd48b7b48adb8898', true, now(), 'aprobado'
    from tenants where slug = 'demo_capilar';
```

- [ ] **Step 2: Aplicar la migración**

Con el proyecto de Supabase ya creado (ver "Dependencia externa" arriba), aplicarla con la herramienta MCP:

```
mcp__supabase__apply_migration
  project_id: <el del proyecto de Supabase de este repo>
  name: tenants_perfiles_servicios_voces
  query: <el contenido del archivo de arriba>
```

O, si se prefiere `supabase` CLI en vez de MCP:

```bash
supabase db push
```

- [ ] **Step 3: Verificar que cargó**

```
mcp__supabase__execute_sql
  project_id: <el mismo>
  query: select slug, nombre, perfil_slug from tenants order by slug;
```

Esperado: dos filas, `demo_capilar` y `quantumhive`.

**Gate de la Fase 5:** `select count(*) from tenants` devuelve 2, cada uno con al menos un servicio y una voz aprobada.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/0001_tenants_perfiles_servicios_voces.sql
git commit -m "feat(fase5): esquema de tenants y datos semilla de los dos tenants del MVP"
```

---

## FASE 6 — Tenant resolver y capa única de repositorios

### Task 3: Modelos del tenant

**Files:**
- Create: `src/motor_voz/brain/tenants/__init__.py`
- Create: `src/motor_voz/brain/tenants/modelos.py`
- Create: `tests/test_tenants_modelos.py`

- [ ] **Step 1: Escribir el test que falla**

`tests/test_tenants_modelos.py`:

```python
import pytest

from motor_voz.brain.tenants.modelos import PerfilTenant, Servicio, Tenant, VozTenant


def _tenant_de_prueba() -> Tenant:
    return Tenant(
        id="1",
        slug="quantumhive",
        nombre="QuantumHive",
        idioma="es",
        perfil=PerfilTenant(slug="receptor", nombre="Receptor", prompt_base="Identidad."),
        prompt_propio="",
        servicios=(Servicio(nombre="Web inteligente", descripcion="Pagina que conversa"),),
        voz=VozTenant(proveedor="fishaudio", voice_id="abc123", consentimiento_aprobado=True),
    )


def test_expone_los_campos():
    t = _tenant_de_prueba()
    assert t.slug == "quantumhive"
    assert t.perfil.slug == "receptor"
    assert t.servicios[0].nombre == "Web inteligente"
    assert t.voz.voice_id == "abc123"


def test_es_inmutable():
    t = _tenant_de_prueba()
    with pytest.raises(Exception):
        t.slug = "otro"  # type: ignore[misc]


def test_puede_no_tener_voz_propia():
    t = Tenant(
        id="2", slug="sin-voz", nombre="Sin Voz", idioma="es",
        perfil=PerfilTenant(slug="receptor", nombre="Receptor", prompt_base="Identidad."),
        prompt_propio="", servicios=(), voz=None,
    )
    assert t.voz is None
```

- [ ] **Step 2: Correr para verificar que falla**

```bash
uv run pytest tests/test_tenants_modelos.py -v
```

Esperado: FALLA con `ModuleNotFoundError: No module named 'motor_voz.brain.tenants'`.

- [ ] **Step 3: Implementar**

`src/motor_voz/brain/tenants/__init__.py`:

```python
"""Todo lo relativo a la resolucion de tenants: modelos, repositorio, resolver.

Sigue bajo brain/: no importa livekit. Lo hace cumplir tests/test_frontera.py.
"""
```

`src/motor_voz/brain/tenants/modelos.py`:

```python
"""Modelos de datos del tenant: lo que devuelve el repositorio.

Estos dataclasses no saben que existe Supabase ni livekit. Son el
contrato que usan el resolver, el context builder y la seleccion de voz.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Servicio:
    nombre: str
    descripcion: str


@dataclass(frozen=True)
class PerfilTenant:
    slug: str
    nombre: str
    prompt_base: str


@dataclass(frozen=True)
class VozTenant:
    proveedor: str
    voice_id: str
    consentimiento_aprobado: bool


@dataclass(frozen=True)
class Tenant:
    id: str
    slug: str
    nombre: str
    idioma: str
    perfil: PerfilTenant
    prompt_propio: str
    servicios: tuple[Servicio, ...]
    voz: VozTenant | None
```

- [ ] **Step 4: Correr para verificar que pasa**

```bash
uv run pytest tests/test_tenants_modelos.py -v
```

Esperado: `3 passed`.

- [ ] **Step 5: Verificar que la frontera sigue en pie**

```bash
uv run pytest tests/test_frontera.py -v
```

Esperado: pasa y ahora cubre también `brain/tenants/modelos.py` (el test usa `rglob`, no hace falta tocarlo).

- [ ] **Step 6: Commit**

```bash
git add src/motor_voz/brain/tenants/__init__.py src/motor_voz/brain/tenants/modelos.py tests/test_tenants_modelos.py
git commit -m "feat(fase6): modelos de datos del tenant"
```

---

### Task 4: El repositorio único — y el test que bloquea el merge

**Files:**
- Create: `src/motor_voz/brain/tenants/repositorio.py`
- Create: `tests/test_un_solo_cliente_supabase.py`
- Create: `tests/smoke/test_aislamiento_multitenant.py`

- [ ] **Step 1: Escribir el test de aislamiento — el que bloquea (falla primero porque el módulo no existe)**

`tests/smoke/test_aislamiento_multitenant.py`:

```python
"""El test que bloquea el merge de las Fases 5-8 (spec S7).

Pide los dos tenants sembrados por la migracion (quantumhive y
demo_capilar) y verifica que los servicios de uno nunca aparecen en el
otro. Corre contra Supabase real: probar aislamiento contra un mock solo
prueba el mock, no el codigo.

Correr con:
    uv run pytest -m integracion tests/smoke/test_aislamiento_multitenant.py -v
"""

from __future__ import annotations

import pytest

from motor_voz.brain.tenants import repositorio
from motor_voz.config import cargar


@pytest.mark.integracion
@pytest.mark.asyncio
async def test_un_tenant_no_ve_servicios_del_otro():
    config = cargar()

    quantumhive = await repositorio.obtener_tenant(config, "quantumhive")
    demo_capilar = await repositorio.obtener_tenant(config, "demo_capilar")

    nombres_quantumhive = {s.nombre for s in quantumhive.servicios}
    nombres_capilar = {s.nombre for s in demo_capilar.servicios}

    assert nombres_quantumhive, "quantumhive deberia tener servicios sembrados"
    assert nombres_capilar, "demo_capilar deberia tener servicios sembrados"
    assert nombres_quantumhive.isdisjoint(nombres_capilar), (
        "Un tenant esta viendo servicios del otro: aislamiento roto"
    )
    assert quantumhive.perfil.slug == "receptor"
    assert demo_capilar.perfil.slug == "capilar"
    assert quantumhive.perfil.prompt_base != demo_capilar.perfil.prompt_base


@pytest.mark.integracion
@pytest.mark.asyncio
async def test_tenant_inexistente_o_pausado_no_se_resuelve():
    config = cargar()
    with pytest.raises(repositorio.TenantNoEncontrado):
        await repositorio.obtener_tenant(config, "no-existe-este-slug")
```

- [ ] **Step 2: Correr para verificar que falla**

```bash
uv run pytest -m integracion tests/smoke/test_aislamiento_multitenant.py -v
```

Esperado: FALLA con `ModuleNotFoundError: No module named 'motor_voz.brain.tenants.repositorio'`.

- [ ] **Step 3: Escribir el test que hace cumplir el punto único de acceso**

`tests/test_un_solo_cliente_supabase.py`:

```python
"""Nadie fuera de repositorio.py instancia el cliente de Supabase.

Supabase se usa con SERVICE_ROLE_KEY, que saltea RLS (spec S7). El
aislamiento entre tenants depende de que TODA query pase por
brain/tenants/repositorio.py y filtre por tenant_id ahi. Si otro modulo
pudiera instanciar el cliente, esa garantia desaparece.
"""

from __future__ import annotations

import ast
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SRC = RAIZ / "src" / "motor_voz"
PERMITIDO = SRC / "brain" / "tenants" / "repositorio.py"
PROHIBIDOS = ("create_client", "acreate_client")


def modulos_del_src() -> list[pathlib.Path]:
    return sorted(p for p in SRC.rglob("*.py") if p != PERMITIDO)


def nombres_llamados(ruta: pathlib.Path) -> list[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    nombres: list[str] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        objetivo = nodo.func
        if isinstance(objetivo, ast.Name):
            nombres.append(objetivo.id)
        elif isinstance(objetivo, ast.Attribute):
            nombres.append(objetivo.attr)
    return nombres


def test_repositorio_existe():
    """Sin esta guarda, el test de abajo pasaria sin revisar nada."""
    assert PERMITIDO.exists(), f"No existe {PERMITIDO}"


def test_ningun_otro_modulo_crea_el_cliente_de_supabase():
    infractores = [
        str(ruta.relative_to(RAIZ))
        for ruta in modulos_del_src()
        if any(llamado in PROHIBIDOS for llamado in nombres_llamados(ruta))
    ]
    assert not infractores, (
        "Estos modulos instancian el cliente de Supabase fuera de "
        f"repositorio.py: {infractores}. Todo acceso a Supabase pasa por "
        "brain/tenants/repositorio.py."
    )
```

- [ ] **Step 4: Correr para verificar que falla**

```bash
uv run pytest tests/test_un_solo_cliente_supabase.py -v
```

Esperado: FALLA en `test_repositorio_existe` con "No existe ... repositorio.py".

- [ ] **Step 5: Implementar el repositorio**

`src/motor_voz/brain/tenants/repositorio.py`:

```python
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

from motor_voz.brain.tenants.modelos import PerfilTenant, Servicio, Tenant, VozTenant
from motor_voz.config import Config


class TenantNoEncontrado(RuntimeError):
    """No existe un tenant activo con ese slug."""


async def _cliente(config: Config) -> AsyncClient:
    return await acreate_client(config.supabase_url, config.supabase_service_role_key)


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

    return Tenant(
        id=tenant_id,
        slug=datos_tenant["slug"],
        nombre=datos_tenant["nombre"],
        idioma=datos_tenant["idioma"],
        perfil=perfil,
        prompt_propio=prompt_propio,
        servicios=servicios,
        voz=voz,
    )
```

- [ ] **Step 6: Correr el test del punto único de acceso**

```bash
uv run pytest tests/test_un_solo_cliente_supabase.py -v
```

Esperado: `2 passed`.

- [ ] **Step 7: Correr el test de aislamiento (necesita `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` reales en el `.env`, y la Task 2 ya aplicada)**

```bash
uv run pytest -m integracion tests/smoke/test_aislamiento_multitenant.py -v -s
```

Esperado: `2 passed`. **Este es el gate bloqueante de la Fase 6 — no se avanza a la Fase 7 si esto está roto.**

- [ ] **Step 8: Verificar que la frontera sigue en pie**

```bash
uv run pytest tests/test_frontera.py -v
```

Esperado: pasa — `repositorio.py` importa `supabase`, no `livekit`, así que no viola nada.

- [ ] **Step 9: Commit**

```bash
git add src/motor_voz/brain/tenants/repositorio.py tests/test_un_solo_cliente_supabase.py tests/smoke/test_aislamiento_multitenant.py
git commit -m "feat(fase6): repositorio unico de Supabase con test de aislamiento bloqueante"
```

---

### Task 5: Resolver — de qué sala sale qué tenant

**Files:**
- Create: `src/motor_voz/brain/tenants/resolver.py`
- Create: `tests/test_resolver.py`

- [ ] **Step 1: Escribir los tests que fallan**

`tests/test_resolver.py`:

```python
from motor_voz.brain.tenants.resolver import TENANT_POR_DEFECTO, tenant_de_la_sala


def test_extrae_el_tenant_del_nombre_de_sala():
    assert tenant_de_la_sala("demo-quantumhive-pipeline-a1b2c3") == "quantumhive"
    assert tenant_de_la_sala("demo-demo_capilar-gemini-f9e8d7") == "demo_capilar"


def test_nombre_sin_formato_cae_al_default():
    assert tenant_de_la_sala("sala-armada-a-mano") == TENANT_POR_DEFECTO


def test_nombre_vacio_cae_al_default():
    assert tenant_de_la_sala("") == TENANT_POR_DEFECTO
```

- [ ] **Step 2: Correr para verificar que falla**

```bash
uv run pytest tests/test_resolver.py -v
```

Esperado: FALLA con `ModuleNotFoundError: No module named 'motor_voz.brain.tenants.resolver'`.

- [ ] **Step 3: Implementar**

`src/motor_voz/brain/tenants/resolver.py`:

```python
"""Resuelve que tenant atiende una sala.

El slug del tenant viaja en el nombre de sala, exactamente como el motor
(ver voice/agente.py:motor_de_la_sala). El nombre de sala queda fijado en
el token via VideoGrants(room=...) al emitirlo, asi que el navegador no
lo puede falsear: solo se puede unir a la sala que el backend eligio.

Formato: demo-<tenant>-<motor>-<aleatorio>

Esta funcion no sabe que existe livekit: recibe un string y devuelve
otro. La frontera la cumple tests/test_frontera.py.
"""

from __future__ import annotations

TENANT_POR_DEFECTO = "quantumhive"


def tenant_de_la_sala(nombre_sala: str) -> str:
    """Extrae el tenant del nombre `demo-<tenant>-<motor>-<aleatorio>`.

    Si el nombre no sigue ese formato — una sala creada a mano, por
    ejemplo — se usa el tenant por defecto.
    """
    partes = nombre_sala.split("-")
    if len(partes) >= 4 and partes[0] == "demo":
        return partes[1]
    return TENANT_POR_DEFECTO
```

- [ ] **Step 4: Correr para verificar que pasa**

```bash
uv run pytest tests/test_resolver.py -v
```

Esperado: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/motor_voz/brain/tenants/resolver.py tests/test_resolver.py
git commit -m "feat(fase6): resolver de tenant a partir del nombre de sala"
```

**Gate de la Fase 6:** el test de aislamiento de la Task 4 pasa contra Supabase real, y el resolver nunca deja que un nombre de sala sin tenant caiga en un tenant equivocado (siempre cae al default, nunca a lo que venga en la cadena).

---

## FASE 7 — Context builder dinámico

### Task 6: `brain/contexto.py` — el prompt final, por tenant

**Files:**
- Modify: `src/motor_voz/brain/prompt.py`
- Create: `src/motor_voz/brain/contexto.py`
- Create: `tests/test_contexto.py`

- [ ] **Step 1: Modificar `construir()` para aceptar una identidad propia**

En `src/motor_voz/brain/prompt.py`, cambiar la firma de `construir` (agrega un parámetro con default, no rompe ningún llamador existente):

```python
def construir(
    motor: str = "pipeline",
    canal: str = "web",
    contexto_extra: str = "",
    identidad: str = IDENTIDAD,
) -> str:
    """Compone el system prompt final para un motor y un canal.

    Args:
        motor: pipeline, gemini u openai. Define como se entrega el habla.
        canal: web, whatsapp o telegram. Define el formato.
        contexto_extra: datos de la sesion. Vacio por defecto.
        identidad: capa 1 del prompt. Default: la identidad de QuantumHive.
            Un tenant con perfil propio (spec S5) pasa la suya.
    """
    partes = [
        identidad,
        ENTREGAS.get(motor, ENTREGA_PIPELINE),
        CANALES.get(canal, CANAL_WEB),
        EJEMPLOS,
    ]
    if contexto_extra.strip():
        partes.append(f"Contexto de esta conversacion:\n{contexto_extra.strip()}")
    return "\n\n".join(partes)
```

- [ ] **Step 2: Correr los tests existentes de prompt — no se pueden romper**

```bash
uv run pytest tests/test_prompt.py -v
```

Esperado: sigue en verde. Todos los tests llaman a `construir()` sin `identidad`, así que usan el default `IDENTIDAD` y no cambian de comportamiento.

- [ ] **Step 3: Escribir los tests que fallan para `contexto.py`**

`tests/test_contexto.py`:

```python
from motor_voz.brain.contexto import construir_contexto
from motor_voz.brain.prompt import ENTREGA_LIVE
from motor_voz.brain.tenants.modelos import PerfilTenant, Servicio, Tenant

QUANTUMHIVE = Tenant(
    id="1", slug="quantumhive", nombre="QuantumHive", idioma="es",
    perfil=PerfilTenant(slug="receptor", nombre="Receptor", prompt_base="Identidad de QuantumHive."),
    prompt_propio="",
    servicios=(Servicio(nombre="Web inteligente", descripcion="Pagina que conversa"),),
    voz=None,
)

DEMO_CAPILAR = Tenant(
    id="2", slug="demo_capilar", nombre="Barberia Demo", idioma="es",
    perfil=PerfilTenant(slug="capilar", nombre="Barberia", prompt_base="Identidad de barberia."),
    prompt_propio="Atendes en la barberia demo.",
    servicios=(Servicio(nombre="Corte clasico", descripcion="Corte tradicional"),),
    voz=None,
)


def test_usa_la_identidad_propia_del_tenant():
    p = construir_contexto(QUANTUMHIVE)
    assert "Identidad de QuantumHive." in p


def test_no_mezcla_identidades_entre_tenants():
    p_a = construir_contexto(QUANTUMHIVE)
    p_b = construir_contexto(DEMO_CAPILAR)
    assert "Identidad de barberia." not in p_a
    assert "Identidad de QuantumHive." not in p_b


def test_lista_solo_los_servicios_propios():
    p_a = construir_contexto(QUANTUMHIVE)
    p_b = construir_contexto(DEMO_CAPILAR)
    assert "Web inteligente" in p_a
    assert "Corte clasico" not in p_a
    assert "Corte clasico" in p_b
    assert "Web inteligente" not in p_b


def test_incluye_el_prompt_propio_del_tenant():
    assert "Atendes en la barberia demo." in construir_contexto(DEMO_CAPILAR)


def test_respeta_motor_y_canal():
    p = construir_contexto(QUANTUMHIVE, motor="gemini", canal="web")
    assert ENTREGA_LIVE in p


def test_un_tenant_sin_servicios_no_rompe():
    sin_servicios = Tenant(
        id="3", slug="nuevo", nombre="Nuevo", idioma="es",
        perfil=PerfilTenant(slug="receptor", nombre="Receptor", prompt_base="Identidad."),
        prompt_propio="Prompt propio sin servicios todavia.",
        servicios=(), voz=None,
    )
    p = construir_contexto(sin_servicios)
    assert "Prompt propio sin servicios todavia." in p
```

- [ ] **Step 4: Correr para verificar que falla**

```bash
uv run pytest tests/test_contexto.py -v
```

Esperado: FALLA con `ModuleNotFoundError: No module named 'motor_voz.brain.contexto'`.

- [ ] **Step 5: Implementar**

`src/motor_voz/brain/contexto.py`:

```python
"""Arma el prompt final de una sesion a partir del tenant ya resuelto.

Combina la identidad propia del tenant (su perfil de vertical) con las
capas de entrega y canal de brain/prompt.py, y agrega sus servicios como
contexto de sesion. No sabe que existe livekit ni Supabase: recibe un
Tenant ya resuelto por brain/tenants/repositorio.py.
"""

from __future__ import annotations

from motor_voz.brain.prompt import construir
from motor_voz.brain.tenants.modelos import Tenant


def _contexto_de_servicios(tenant: Tenant) -> str:
    if not tenant.servicios:
        return tenant.prompt_propio
    lista = "\n".join(f"- {s.nombre}: {s.descripcion}" for s in tenant.servicios)
    servicios_texto = (
        f"Estos son los servicios reales de {tenant.nombre}, no inventes otros:\n{lista}"
    )
    if tenant.prompt_propio.strip():
        return f"{tenant.prompt_propio.strip()}\n\n{servicios_texto}"
    return servicios_texto


def construir_contexto(tenant: Tenant, motor: str = "pipeline", canal: str = "web") -> str:
    """Prompt final para este tenant, en este motor y este canal."""
    return construir(
        motor=motor,
        canal=canal,
        identidad=tenant.perfil.prompt_base,
        contexto_extra=_contexto_de_servicios(tenant),
    )
```

- [ ] **Step 6: Correr para verificar que pasa**

```bash
uv run pytest tests/test_contexto.py -v
```

Esperado: `6 passed`.

- [ ] **Step 7: Verificar que la frontera sigue en pie**

```bash
uv run pytest tests/test_frontera.py -v
```

Esperado: pasa, ahora también cubre `brain/contexto.py`.

- [ ] **Step 8: Commit**

```bash
git add src/motor_voz/brain/prompt.py src/motor_voz/brain/contexto.py tests/test_contexto.py
git commit -m "feat(fase7): context builder dinamico por tenant"
```

**Gate de la Fase 7:** `test_lista_solo_los_servicios_propios` y `test_no_mezcla_identidades_entre_tenants` en verde — cada tenant responde solo con sus propios datos.

---

## FASE 8 — Voz por tenant y cableado final

### Task 7: El proveedor de TTS acepta una voz que no viene de `Config`

**Files:**
- Modify: `src/motor_voz/voice/providers/tts.py`
- Modify: `tests/test_providers.py`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/test_providers.py`:

```python
def test_opciones_tts_el_override_pisa_al_voice_id_de_config():
    opciones_resultado = tts.opciones(
        cargar(ENTORNO | {"FISH_VOICE_ID": "voz-de-config"}),
        voice_id_override="voz-del-tenant",
    )
    assert opciones_resultado["voice_id"] == "voz-del-tenant"


def test_opciones_tts_sin_override_usa_el_de_config():
    opciones_resultado = tts.opciones(cargar(ENTORNO | {"FISH_VOICE_ID": "voz-de-config"}))
    assert opciones_resultado["voice_id"] == "voz-de-config"


def test_opciones_tts_override_vacio_no_pisa_nada():
    opciones_resultado = tts.opciones(
        cargar(ENTORNO | {"FISH_VOICE_ID": "voz-de-config"}), voice_id_override=""
    )
    assert opciones_resultado["voice_id"] == "voz-de-config"
```

- [ ] **Step 2: Correr para verificar que falla**

```bash
uv run pytest tests/test_providers.py -v -k override
```

Esperado: FALLA con `TypeError: opciones() got an unexpected keyword argument 'voice_id_override'`.

- [ ] **Step 3: Implementar**

Reemplazar `src/motor_voz/voice/providers/tts.py` completo:

```python
"""Sintesis de voz con Fish Audio.

Este modulo es el unico punto que conoce a Fish. Cuando se agregue el pool
de proveedores del spec, el router vive aca y el resto del motor no se entera.
"""

from __future__ import annotations

from typing import Any

from livekit.plugins import fishaudio

from motor_voz.config import Config


def opciones(config: Config, voice_id_override: str = "") -> dict[str, Any]:
    """El default de latency_mode es 'balanced'; para Live queremos 'low'.

    `speed` y `temperature` salen de configuracion porque son de oido, no
    de calculo: se ajustan escuchando. `voice_id_override` es la voz del
    tenant resuelto (spec S8, "cada tenant habla con su propia voz");
    gana sobre `FISH_VOICE_ID` de Config, que queda como fallback para
    cuando no hay tenant (fases 0-4, desarrollo local).
    """
    opts: dict[str, Any] = {
        "model": config.fish_model,
        "latency_mode": config.fish_latency_mode,
        "speed": config.fish_speed,
        "temperature": config.fish_temperature,
        "api_key": config.fish_api_key,
    }
    voice_id = voice_id_override.strip() or config.fish_voice_id.strip()
    if voice_id:
        opts["voice_id"] = voice_id
    return opts


def crear(config: Config, voice_id_override: str = "") -> fishaudio.TTS:
    return fishaudio.TTS(**opciones(config, voice_id_override))
```

- [ ] **Step 4: Correr para verificar que pasa**

```bash
uv run pytest tests/test_providers.py -v
```

Esperado: todos en verde, incluidos los tres nuevos.

- [ ] **Step 5: Commit**

```bash
git add src/motor_voz/voice/providers/tts.py tests/test_providers.py
git commit -m "feat(fase8): tts acepta una voz que no viene de Config"
```

---

### Task 8: `motores.componentes` propaga la voz del tenant

**Files:**
- Modify: `src/motor_voz/voice/motores.py`
- Modify: `tests/test_motores.py`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_motores.py` (revisar el `ENTORNO`/fixture que ya usa ese archivo y reutilizarlo):

```python
def test_componentes_pipeline_propaga_la_voz_del_tenant():
    config = cargar(ENTORNO | {"MOTOR": "pipeline"})
    comps = motores.componentes(config, voice_id_override="voz-del-tenant")
    assert comps["tts"].voice_id == "voz-del-tenant"


def test_componentes_sin_override_usa_la_voz_de_config():
    config = cargar(ENTORNO | {"MOTOR": "pipeline", "FISH_VOICE_ID": "voz-de-config"})
    comps = motores.componentes(config)
    assert comps["tts"].voice_id == "voz-de-config"
```

`fishaudio.TTS` expone `voice_id` como atributo público (verificado el 2026-08-09 instanciando el objeto real, no de memoria) — no hace falta tocar el privado `_opts`.

- [ ] **Step 2: Correr para verificar que falla**

```bash
uv run pytest tests/test_motores.py -v -k voz
```

Esperado: FALLA con `TypeError: componentes() got an unexpected keyword argument 'voice_id_override'`.

- [ ] **Step 3: Implementar**

En `src/motor_voz/voice/motores.py`, modificar `_pipeline`, `_gemini`, `_openai` y `componentes` para que todos acepten (aunque solo `_pipeline` lo use) el mismo parámetro — mantiene el despacho por diccionario uniforme:

```python
def componentes(config: Config, voice_id_override: str = "") -> dict[str, Any]:
    """Devuelve los kwargs de AgentSession del motor configurado.

    `voice_id_override` es la voz del tenant ya resuelto (spec S8). Solo
    el pipeline la usa hoy: Gemini y OpenAI hablan con una voz de catalogo
    fija (`gemini_voice`/`openai_voice`), no con una voz clonada.
    """
    if config.motor not in MOTORES:
        raise MotorNoDisponible(
            f"Motor '{config.motor}' desconocido. Validos: {', '.join(MOTORES)}."
        )
    return _CONSTRUCTORES[config.motor](config, voice_id_override)


def _pipeline(config: Config, voice_id_override: str = "") -> dict[str, Any]:
    return {
        "stt": proveedor_stt.crear(config),
        "llm": proveedor_llm.crear(config),
        "tts": proveedor_tts.crear(config, voice_id_override),
        # Groq Whisper no hace endpointing: sin VAD no hay deteccion de turno
        # ni interrupcion.
        "vad": silero.VAD.load(),
    }
```

Y agregar `voice_id_override: str = ""` como parámetro (sin usarlo) a `_gemini` y `_openai`.

> **No mover los imports adentro de las funciones.** El commit `25603f3`
> los subió a nivel de módulo justamente porque livekit-agents exige que
> los plugins se registren en el hilo principal: con el import adentro,
> la primera sesión de Gemini revienta con `RuntimeError: Plugins must be
> registered on the main thread`. Ya pasó en producción. `google` y
> `openai_realtime` **ya están importados arriba** en el archivo — usarlos
> desde ahí.

```python
def _gemini(config: Config, voice_id_override: str = "") -> dict[str, Any]:
    return {"llm": google.beta.realtime.RealtimeModel(**opciones_gemini(config))}
```

```python
def _openai(config: Config, voice_id_override: str = "") -> dict[str, Any]:
    opts = opciones_openai(config)
    if opts.pop("_azure", False):
        return {"llm": openai_realtime.RealtimeModel.with_azure(**opts)}
    return {"llm": openai_realtime.RealtimeModel(**opts)}
```

- [ ] **Step 4: Correr para verificar que pasa**

```bash
uv run pytest tests/test_motores.py -v
```

Esperado: todos en verde.

- [ ] **Step 5: Commit**

```bash
git add src/motor_voz/voice/motores.py tests/test_motores.py
git commit -m "feat(fase8): componentes del motor propagan la voz del tenant"
```

---

### Task 9: Cablear todo — `api/servidor.py` y `voice/agente.py`

**Files:**
- Modify: `src/motor_voz/api/servidor.py`
- Modify: `src/motor_voz/voice/agente.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Actualizar el fixture de `test_api.py` con un tenant falso — así los tests siguen sin red**

En `tests/test_api.py`, agregar los imports y el tenant/función falsa, y cambiar el fixture `cliente`:

```python
from motor_voz.brain.tenants.modelos import PerfilTenant, Tenant
from motor_voz.brain.tenants.repositorio import TenantNoEncontrado

TENANT_DE_PRUEBA = Tenant(
    id="tenant-1", slug="quantumhive", nombre="QuantumHive", idioma="es",
    perfil=PerfilTenant(slug="receptor", nombre="Receptor", prompt_base="Identidad de prueba."),
    prompt_propio="", servicios=(), voz=None,
)


async def _tenant_falso(config, slug):
    if slug != TENANT_DE_PRUEBA.slug:
        raise TenantNoEncontrado(f"no existe el tenant '{slug}'")
    return TENANT_DE_PRUEBA


@pytest.fixture
def cliente(aiohttp_client):
    async def _crear(**extra):
        obtener_tenant = extra.pop("obtener_tenant", _tenant_falso)
        return await aiohttp_client(
            crear_app(cargar(ENTORNO | extra), obtener_tenant=obtener_tenant)
        )
    return _crear
```

- [ ] **Step 2: Actualizar el test que ya existe para el nuevo formato de sala**

Cambiar `test_el_motor_va_en_el_nombre_de_la_sala`:

```python
    async def test_el_motor_va_en_el_nombre_de_la_sala(self, cliente):
        """Asi lo lee el agente, y el token restringe a que sala se entra."""
        c = await cliente()
        for nivel, motor in [(1, "pipeline"), (2, "gemini"), (3, "openai")]:
            d = await (await c.post("/api/token", json={"nivel": nivel})).json()
            # demo-<tenant>-<motor>-<voz>-<aleatorio>
            assert d["sala"].startswith(f"demo-quantumhive-{motor}-")
            assert d["sala"].split("-")[3] == d["voz"]
```

- [ ] **Step 3: Escribir los tests nuevos que fallan, para el flujo de tenant**

Agregar una clase nueva en `tests/test_api.py`:

```python
class TestTenant:
    async def test_por_defecto_usa_quantumhive(self, cliente):
        c = await cliente()
        d = await (await c.post("/api/token", json={"nivel": 1})).json()
        assert d["tenant"] == "quantumhive"

    async def test_tenant_inexistente_da_404(self, cliente):
        c = await cliente()
        r = await c.post("/api/token", json={"nivel": 1, "tenant": "no-existe"})
        assert r.status == 404

    async def test_supabase_caido_da_503_no_500(self, cliente):
        async def _falla(config, slug):
            raise RuntimeError("timeout de red")

        c = await cliente(obtener_tenant=_falla)
        r = await c.post("/api/token", json={"nivel": 1})
        assert r.status == 503

    async def test_el_tenant_va_en_la_metadata_firmada(self, cliente):
        import base64
        import json as jsonlib

        c = await cliente()
        d = await (await c.post("/api/token", json={"nivel": 1})).json()
        payload = d["token"].split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = jsonlib.loads(base64.urlsafe_b64decode(payload))
        metadata = jsonlib.loads(claims["metadata"])
        assert metadata["tenant"] == "quantumhive"
```

- [ ] **Step 4: Correr para verificar que fallan**

```bash
uv run pytest tests/test_api.py -v
```

Esperado: FALLA — `crear_app()` todavía no acepta `obtener_tenant`, y la respuesta no trae `"tenant"`.

- [ ] **Step 5: Implementar en `api/servidor.py`**

Agregar los imports (después de los que ya existen):

```python
from motor_voz.brain.tenants import repositorio
from motor_voz.brain.tenants.modelos import Tenant
from motor_voz.brain.tenants.resolver import TENANT_POR_DEFECTO
```

Agregar el tipo del callback arriba de `emitir_token` (junto con los demás imports de typing si hace falta `Awaitable`/`Callable`):

```python
from typing import Awaitable, Callable

ObtenerTenant = Callable[[Config, str], Awaitable[Tenant]]
```

Modificar `emitir_token` completo:

```python
async def emitir_token(peticion: web.Request) -> web.Response:
    config: Config = peticion.app["config"]
    limitador: Limitador = peticion.app["limitador"]
    obtener_tenant: ObtenerTenant = peticion.app["obtener_tenant"]

    try:
        cuerpo = await peticion.json()
    except json.JSONDecodeError:
        cuerpo = {}

    try:
        nivel = catalogo_niveles.resolver(cuerpo.get("nivel", 1))
    except catalogo_niveles.NivelInvalido as e:
        return _cors(web.json_response({"error": str(e)}, status=400))

    tenant_slug = (cuerpo.get("tenant") or TENANT_POR_DEFECTO).strip() or TENANT_POR_DEFECTO
    try:
        tenant = await obtener_tenant(config, tenant_slug)
    except repositorio.TenantNoEncontrado as e:
        return _cors(web.json_response({"error": str(e)}, status=404))
    except Exception:
        logger.exception("no se pudo resolver el tenant '%s'", tenant_slug)
        return _cors(
            web.json_response(
                {"error": "No se pudo validar el negocio. Reintenta en un momento."},
                status=503,
            )
        )

    ip = _ip_de(peticion)
    try:
        limitador.registrar(ip)
    except LimiteAlcanzado as e:
        logger.info("limite alcanzado para %s", ip)
        return _cors(web.json_response({"error": str(e)}, status=429))

    sala = f"demo-{tenant.slug}-{nivel.motor}-{voz}-{secrets.token_hex(6)}"
    identidad = f"visitante-{secrets.token_hex(4)}"

    token = (
        api.AccessToken(config.livekit_api_key, config.livekit_api_secret)
        .with_identity(identidad)
        .with_name("Visitante")
        # El motor y el tenant van firmados: el agente lee de aca, no del
        # navegador. Ademas el tenant queda fijado en el nombre de sala
        # (ver brain/tenants/resolver.py), que VideoGrants restringe.
        .with_metadata(
            json.dumps(
                {
                    "motor": nivel.motor,
                    "nivel": nivel.numero,
                    "voz": voz,
                    "tenant": tenant.slug,
                }
            )
        )
        .with_grants(
            api.VideoGrants(
                room_join=True, room=sala, can_publish=True, can_subscribe=True
            )
        )
        .to_jwt()
    )

    logger.info(
        "token emitido | nivel=%s motor=%s tenant=%s sala=%s",
        nivel.numero, nivel.motor, tenant.slug, sala,
    )
    return _cors(
        web.json_response(
            {
                "token": token,
                "url": config.livekit_url,
                "sala": sala,
                "nivel": nivel.numero,
                "plan": nivel.plan,
                "tenant": tenant.slug,
                "duracion_maxima_seg": config.max_session_seconds,
            }
        )
    )
```

Modificar `crear_app`:

```python
def crear_app(config: Config | None = None, obtener_tenant: ObtenerTenant | None = None) -> web.Application:
    cfg = config or cargar()
    app = web.Application()
    app["config"] = cfg
    app["obtener_tenant"] = obtener_tenant or repositorio.obtener_tenant
    app["limitador"] = Limitador(
        por_ip_hora=cfg.max_sesiones_por_ip_hora,
        por_dia=cfg.max_sesiones_por_dia,
    )
    app.add_routes(
        [
            web.get("/api/salud", salud),
            web.get("/api/niveles", listar_niveles),
            web.post("/api/token", emitir_token),
            web.options("/api/{resto:.*}", preflight),
        ]
    )
    return app
```

- [ ] **Step 6: Correr para verificar que pasa**

```bash
uv run pytest tests/test_api.py -v
```

Esperado: todos en verde, incluidos los nuevos de `TestTenant`.

- [ ] **Step 7: Cablear el agente — `voice/agente.py`**

Reemplazar las partes relevantes de `src/motor_voz/voice/agente.py`. Agregar imports:

```python
from motor_voz.brain.contexto import construir_contexto
from motor_voz.brain.tenants import repositorio
from motor_voz.brain.tenants.resolver import tenant_de_la_sala
```

Quitar el import de `construir` de `brain.prompt` (ya no se usa directo acá, lo usa `contexto.py`).

Correr los dos parsers un lugar a la derecha, porque el tenant entra al
principio: el formato pasa de `demo-<motor>-<voz>-<aleatorio>` a
`demo-<tenant>-<motor>-<voz>-<aleatorio>`.

```python
def motor_de_la_sala(nombre: str, por_defecto: str) -> str:
    """Extrae el motor de `demo-<tenant>-<motor>-<voz>-<aleatorio>`.

    Si el nombre no sigue ese formato — una sala creada a mano, por ejemplo —
    se usa el motor de la configuracion.
    """
    partes = nombre.split("-")
    if len(partes) >= 5 and partes[0] == "demo" and partes[2] in motores.MOTORES:
        return partes[2]
    return por_defecto


def voz_de_la_sala(nombre: str, por_defecto: str) -> str:
    """Extrae la voz de Gemini de `demo-<tenant>-<motor>-<voz>-<aleatorio>`.

    Solo importa cuando el motor es gemini; en los demas el campo esta
    igual (servidor.py siempre lo manda) pero no se usa. Se valida contra
    el catalogo real: una sala armada a mano no puede pedirle a Vertex una
    voz que no existe.
    """
    partes = nombre.split("-")
    if len(partes) >= 5 and partes[0] == "demo" and partes[3] in motores.VOCES_GEMINI:
        return partes[3]
    return por_defecto
```

Cambiar `Receptor` para que reciba el prompt ya armado en vez de solo el motor:

```python
class Receptor(Agent):
    """Agente receptor de un tenant."""

    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions="Saluda al visitante en una sola oracion corta y "
            "pregunta en que lo podes ayudar."
        )
```

Y en `entrypoint`, después de resolver `config` y antes de armar la sesión, resolver el tenant y usarlo tanto para la voz como para el prompt:

```python
@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    base = cargar()
    config = dataclasses.replace(
        base,
        motor=motor_de_la_sala(ctx.room.name, base.motor),
        gemini_voice=voz_de_la_sala(ctx.room.name, base.gemini_voice),
    )
    tenant_slug = tenant_de_la_sala(ctx.room.name)
    tenant = await repositorio.obtener_tenant(config, tenant_slug)
    ctx.log_context_fields = {"room": ctx.room.name, "motor": config.motor, "tenant": tenant.slug}

    logger.info(
        "sesion nueva | tenant=%s plan=%s motor=%s | voz=%s speed=%s temp=%s | voz_gemini=%s",
        tenant.slug,
        motores.PLANES.get(config.motor, "?"),
        config.motor,
        (tenant.voz.voice_id if tenant.voz else config.fish_voice_id)[:12] or "(default)",
        config.fish_speed,
        config.fish_temperature,
        config.gemini_voice,
    )

    extras: dict = {}
    if config.motor == "pipeline":
        extras["tts_text_transforms"] = [
            "filter_markdown",
            "filter_emoji",
            normalizar_para_voz,
        ]

    voice_id_override = tenant.voz.voice_id if tenant.voz else ""
    session: AgentSession = AgentSession(
        **motores.componentes(config, voice_id_override), **extras
    )

    @session.on("metrics_collected")
    def _metricas(ev: MetricsCollectedEvent) -> None:
        metrics.log_metrics(ev.metrics)

    async def registrar_uso() -> None:
        logger.info(f"Uso de la sesion: {session.usage}")

    ctx.add_shutdown_callback(registrar_uso)

    prompt = construir_contexto(tenant, motor=config.motor, canal="web")
    await session.start(
        agent=Receptor(prompt),
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )
```

- [ ] **Step 8: Verificar que importa sin errores**

```bash
uv run python -c "import motor_voz.voice.agente; print('importa OK')"
```

Esperado: imprime `importa OK`.

- [ ] **Step 9: Correr toda la suite**

```bash
uv run pytest -v
```

Esperado: todo en verde (los de `integracion` y `smoke` siguen excluidos por default).

- [ ] **Step 10: Commit**

```bash
git add src/motor_voz/api/servidor.py src/motor_voz/voice/agente.py tests/test_api.py
git commit -m "feat(fase8): api y agente resuelven el tenant y hablan con su voz propia"
```

---

### Task 10: Verificación end-to-end y gate de las Fases 5-8

**Files:** ninguno — es verificación manual y de integración.

- [ ] **Step 1: Correr la suite completa, incluida integración**

```bash
uv run pytest -v
uv run pytest -m integracion -v
```

Esperado: todo pasa. Anotar el número total de tests (referencia: 122 antes de este plan).

- [ ] **Step 2: Probar los dos tenants de punta a punta, en local**

Con `livekit-server --dev` corriendo y `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` reales en el `.env`:

```bash
uv run python -m motor_voz.api.servidor &
curl -s -X POST http://localhost:8080/api/token -H "Content-Type: application/json" -d '{"nivel":1,"tenant":"quantumhive"}'
curl -s -X POST http://localhost:8080/api/token -H "Content-Type: application/json" -d '{"nivel":1,"tenant":"demo_capilar"}'
```

Verificar que las dos respuestas traen `"sala"` con tenants distintos (`demo-quantumhive-pipeline-...` y `demo-demo_capilar-pipeline-...`).

- [ ] **Step 3: Conectarse a cada sala y escuchar**

Con `uv run python -m motor_voz.voice.agente dev` corriendo, conectar el frontend demo a cada token por separado y verificar a oído:

- [ ] QuantumHive saluda como QuantumHive y ofrece web inteligente/empleado virtual — nunca mezcla con la barbería.
- [ ] La barbería demo saluda como barbería, ofrece corte clásico/afeitado — nunca menciona QuantumHive como negocio propio.
- [ ] Si `demo_capilar` tiene un `voice_id` de Fish distinto y real (ajustado en la Task 2, Step 1), **se escucha una voz distinta** a la de QuantumHive. Si suena igual, revisar que el `voice_id` sembrado sea de verdad otro del catálogo de Fish.

- [ ] **Step 4: Documentar el resultado**

Crear `docs/resultados/fases5-8-multitenant.md` con: qué se escuchó en cada tenant, si las voces sonaron distintas, y cualquier cosa que no haya salido como en este plan.

- [ ] **Step 5: Commit**

```bash
git add docs/resultados/fases5-8-multitenant.md
git commit -m "docs(fase8): resultados de la verificacion multi-tenant end-to-end"
```

**Gate de las Fases 5-8 — no se avanza a la Fase 9 sin esto:**
1. Dos tenants cargados en Supabase, cada uno con servicios y voz propios (Fase 5).
2. El test de aislamiento (`tests/smoke/test_aislamiento_multitenant.py`) pasa contra Supabase real (Fase 6).
3. Cada tenant responde solo con sus propios servicios — probado por `tests/test_contexto.py` (Fase 7).
4. Cada tenant habla con su propia voz, validado a oído, no solo por código (Fase 8).
5. `brain/` sigue sin importar `livekit` en ningún módulo nuevo (`tests/test_frontera.py` en verde).

---

## Qué sigue

Con las Fases 5-8 cerradas, el runtime es multi-tenant de verdad: dos negocios distintos, mismo código, aislados y probados. Lo que falta para el MVP completo del spec:

- **Fase 9** — tools y registries (`registry_publico` / `registry_receptor`), captura de leads.
- **Fase 10** — límites de gasto, kill-switch por presupuesto, degradación cuando Fish o Groq fallan, eventos `live.sesion_iniciada`/`live.sesion_finalizada`/`voz.perfil_creado` hacia Quantum Core.
- **Fase 11** — modo asíncrono: WhatsApp, Telegram, guiones cacheados. Reusa `brain/contexto.py` y `brain/tenants/` sin tocarlos — es exactamente lo que la frontera dura existe para permitir.

Cada una es un plan propio, escrito cuando este cierre y quede verificado en producción.

## Riesgos de este plan

| Riesgo | Señal temprana | Qué hacer |
|---|---|---|
| No existe todavía un proyecto de Supabase para este repo | La Task 2 no tiene a qué aplicar la migración | Crear el proyecto con `mcp__supabase__create_project` antes de arrancar, y que Sergio suba `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` a Secret Manager |
| El `voice_id` sembrado para `demo_capilar` es un placeholder inventado | El gate de oído de la Task 10 no puede confirmar que suena distinto | Sergio elige un `voice_id` real del catálogo de Fish antes de la Task 10 |
| El nombre de sala cambia de 3 a 4 partes | Cualquier código o doc que asuma `demo-{motor}-...` (afuera de este repo, ej. el frontend demo si lo tiene hardcodeado) se rompe | Buscar `demo-` en `frontend/demo/` y en cualquier landing que ya integre el widget antes de deployar |
| `acreate_client`/`.maybe_single()` cambian de nombre en una versión nueva de `supabase-py` | `uv sync` trae una versión distinta a `>=2.9,<3` y los imports fallan | Ya verificado contra el paquete real instalado el 2026-08-09 (no de memoria); si falla, `uv run python -c "from supabase import acreate_client"` y ajustar |
| Validar el tenant contra Supabase en cada `POST /api/token` agrega latencia y un punto de falla nuevo al endpoint más usado | `emitir_token` tarda notablemente más, o Supabase caído tira 503 en toda la demo | Aceptable para este plan (Fase 10 es la que resuelve degradación con cache/circuit breaker); si molesta antes, cachear `obtener_tenant` con TTL corto |
