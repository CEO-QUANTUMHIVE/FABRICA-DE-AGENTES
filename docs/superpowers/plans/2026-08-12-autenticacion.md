# Autenticación — Plan de Implementación

**Escrito:** 2026-08-12
**Va antes de:** el panel de control y del camino de escritura de la fábrica
**Mapa:** [`docs/MAPA.md`](../../MAPA.md), punto 7

---

## Para qué es, y para qué NO

**Es solo para el panel de control.** El dueño de un negocio entra con usuario
y contraseña y habla con su agente en modo interno.

**No es para la fábrica.** Ahí el cliente entra sin login, lo entrevistan, y
lo que se crea es un **borrador** (migración `0008`, ya aplicada). El login se
le entrega **después de pagar**, junto con el panel.

**No es para la landing.** El visitante sigue siendo anónimo.

## Por qué va antes que todo lo demás

Hoy `MODO_DE_LA_SESION` en `voice/agente.py` está **fijo en `publico`**. Está
fijo porque el modo interno da acceso a `get_mis_leads` y `get_mis_metricas`, y
sin login no hay forma de saber quién está del otro lado.

**Si el panel sale antes que esto, sale con la puerta abierta.**

## Estado verificado del código (2026-08-12)

Leído, no recordado:

- `api/servidor.py` — `emitir_token` resuelve el tenant por `Origin` y firma
  metadata con `motor`, `nivel`, `voz`, `tenant`. **Ahí va a ir `modo`.**
- `voice/agente.py` — `MODO_DE_LA_SESION = "publico"`, constante de módulo.
- `brain/tools/registro.py` — `registry_de(modo)` ya existe y falla cerrado:
  solo el string exacto `interno` abre lo interno.
- `brain/tenants/repositorio.py` — único punto que habla con Supabase, con un
  test de AST que lo hace cumplir. **Toda consulta nueva va acá.**

O sea: **la mitad del trabajo ya está hecha.** Falta quién autentica y que el
modo viaje firmado.

---

## Task 1: Supabase Auth y el vínculo usuario↔negocio

**Files:** `supabase/migrations/0009_usuarios_de_tenant.sql`

Usamos **Supabase Auth**, que ya viene con el proyecto: maneja contraseñas,
recuperación por mail y sesiones. No escribimos autenticación a mano — es el
lugar más fácil de arruinar.

```sql
-- Quien puede entrar al panel de que negocio.
--
-- Un negocio puede tener varios usuarios (el dueño y un empleado). Un usuario
-- podria administrar varios negocios (una cadena). Por eso es tabla aparte y
-- no una columna.
create table tenant_usuarios (
    usuario_id uuid not null references auth.users(id) on delete cascade,
    tenant_id uuid not null references tenants(id) on delete cascade,
    rol text not null default 'dueño' check (rol in ('dueño', 'empleado')),
    created_at timestamptz not null default now(),
    primary key (usuario_id, tenant_id)
);
create index tenant_usuarios_tenant_idx on tenant_usuarios(tenant_id);
```

- [x] Aplicada con el pooler (`aws-1-us-west-2`) el 2026-08-13, con RLS habilitado.
- [ ] Crear a mano un usuario para `quantumhive` y probar el login.

---

## Task 2: El endpoint valida la sesión

**Files:** `api/servidor.py`, `brain/tenants/repositorio.py`, `tests/test_api.py`

- [x] **Test primero.** Los cuatro que importan:

```python
async def test_sin_sesion_el_modo_es_publico(...)
async def test_con_sesion_de_OTRO_negocio_el_modo_es_publico(...)   # el crítico
async def test_con_sesion_del_dueño_el_modo_es_interno(...)
async def test_un_token_de_sesion_invalido_no_rompe_da_publico(...)
```

El segundo es el que importa: **tener sesión no alcanza, tiene que ser sesión
de *ese* negocio.** Si no, cualquier cliente ve los leads de cualquier otro.

- [x] **En `repositorio.py`:** validación de JWT y rol filtrado por usuario + tenant.
      que devuelve el rol o `None`. Con su `.eq()` por los dos campos.

- [x] **En `emitir_token`:** leer `Authorization: Bearer <jwt de Supabase>`.

```python
# El modo NO sale de lo que pida el navegador. Sale de verificar la sesion
# contra el tenant que ya resolvio el dominio. Falla cerrado: cualquier
# problema —sin cabecera, JWT vencido, sesion de otro negocio— es publico.
modo = "publico"
if jwt:
    usuario = await verificar_jwt(config, jwt)      # Supabase valida la firma
    if usuario and await tenant_del_usuario(config, usuario.id, tenant.id):
        modo = "interno"
```

- [x] Meter `modo` en la metadata firmada del token, al lado de `tenant`.

**No inventes la verificación del JWT.** Supabase la hace: `auth.get_user(jwt)`
del cliente ya instalado.

---

## Task 3: El agente lee el modo del token

**Files:** `voice/agente.py`, `tests/test_herramientas.py`

- [x] Sacar la constante `MODO_DE_LA_SESION` y leer el modo de la metadata del
      participante (`await ctx.wait_for_participant()`, campo `.metadata`).
- [x] **Default `publico` si no viene o no se entiende.** `registry_de` ya
      falla cerrado, pero que el default esté también acá.
- [x] Test: un participante sin metadata, o con metadata rota, recibe las 4
      tools públicas y ninguna interna.

---

## Task 4: Verificación

- [ ] Suite completa + integración.
- [ ] Contra la base real: pedir un token con la sesión del dueño de
      `demo_capilar` y comprobar que **no** puede pedir modo interno sobre
      `quantumhive`.
- [ ] Documentar en `docs/resultados/`.

**Gate — no se avanza al panel sin esto:**

1. Sin sesión → `publico`, siempre.
2. Con sesión de otro negocio → `publico`. **Probado contra la base real.**
3. Con sesión del dueño → `interno`, y solo sobre su propio negocio.
4. Un JWT vencido o inventado no rompe: da `publico`.
5. El modo viaja firmado en el token, nunca en el cuerpo del pedido.

---

## Riesgos

| Riesgo | Qué hacer |
|---|---|
| **Verificar el JWT a mano** | No. Usá `auth.get_user()` de Supabase. Firmas y expiración son fáciles de arruinar y difíciles de testear |
| Alcanza con "tener sesión" | No alcanza: tiene que ser sesión **de ese negocio**. Es el test 2 y es el que evita que un cliente vea los leads de otro |
| El modo llega por el cuerpo del pedido | Nunca. Va firmado en el token, igual que el tenant y el motor |
| Se abre el modo interno "por ahora" para probar | El modo interno da los leads de un negocio real. Se prueba en local con `ENVIRONMENT=development` |
| Confundir esto con el login de la fábrica | La fábrica **no tiene login**: crea borradores. El login se entrega al pagar |
