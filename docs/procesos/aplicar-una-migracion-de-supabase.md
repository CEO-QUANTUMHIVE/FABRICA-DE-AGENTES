# Aplicar una migración de Supabase

| | |
|---|---|
| Proyecto | `bcexirhurfigrehfarol` — *motor de voz y llm* |
| Región | **`us-west-2`**, West US (Oregon) |
| Pooler (IPv4) | `aws-1-us-west-2.pooler.supabase.com` |
| Directo (IPv6) | `db.bcexirhurfigrehfarol.supabase.co` |

Las migraciones viven en `supabase/migrations/`, numeradas y en orden.

## El comando

**Usá el pooler.** El host directo es IPv6-only y el día que se caiga la
salida IPv6 no vas a poder migrar (ver abajo).

```bash
supabase db push --db-url "postgresql://postgres.bcexirhurfigrehfarol:CONTRASEÑA@aws-1-us-west-2.pooler.supabase.com:5432/postgres"
```

Ojo con dos detalles del pooler: el usuario es **`postgres.<ref>`**, no
`postgres` a secas, y el prefijo del host es **`aws-1-`**, no `aws-0-` — con
`aws-0-` este proyecto responde `tenant not found`.

La contraseña va **codificada para URL** (`$` es `%24`, `@` es `%40`). Nunca
la escribas literal en la línea de comandos: leela de un archivo o de una
variable, y filtrá la salida antes de mostrarla.

Alternativa interactiva, que no deja la contraseña en el historial:

```bash
supabase link --project-ref bcexirhurfigrehfarol
```

```bash
supabase db push
```

## Nunca edites una migración ya aplicada

Si hay que corregir un dato, se crea la siguiente. La `0002` existe justamente
por eso: la `0001` sembró un `voice_id` que era un placeholder.

## Si dice `no such host` y hace un rato andaba

**El host directo `db.<ref>.supabase.co` es IPv6-only.** Si tu conexión pierde
la salida IPv6 —cambia la red, el proveedor, o el entorno donde corrés— el
CLI dice `hostname resolving error: no such host` aunque el DNS resuelva
perfecto. Pasó el 2026-08-11: a la mañana andaba y a la tarde no.

Cómo confirmarlo en diez segundos:

```powershell
Resolve-DnsName 'db.TU-REF.supabase.co' -Type AAAA
Test-NetConnection -ComputerName 'LA-IPv6-QUE-SALIO' -Port 5432 -InformationLevel Quiet
```

Si resuelve pero el puerto da `False`, es la salida IPv6, no el DNS ni la
contraseña.

**El camino IPv4 es el pooler**, y para eso necesitás la región. La de este
proyecto está arriba: `us-west-2`, con prefijo `aws-1-`.

Si alguna vez trabajás con otro proyecto y no sabés la región, **no la
adivines** — todas responden `tenant/user not found` menos la correcta. Sale
del dashboard, en la tarjeta *Primary Database*. Y si no tenés acceso al
dashboard, el IPv6 del host directo es de AWS y su prefijo delata la región;
el de la API no sirve porque está detrás de Cloudflare.

La API por HTTPS (la que usan el motor y los tests) **no se ve afectada**: va
por IPv4 contra `https://<ref>.supabase.co`. Que los tests de integración
pasen no quiere decir que puedas migrar.

## Lo que ya nos rompió

**El MCP de Supabase no ve este proyecto.** Su token está scopeado por
organización: lista otros cuatro proyectos y para este devuelve "access
denied" sin aclarar que el problema es de alcance. Por eso se aplica con el
CLI y no con `mcp__supabase__apply_migration`.

**Un `.env` con BOM rompe el CLI.** Falla con `unexpected character '»' in
variable name`. Lo causa escribir el archivo con `Set-Content -Encoding utf8`
en Windows PowerShell 5.1, que agrega BOM. Python lo tolera, el CLI de
Supabase no. Para escribir un `.env` desde PowerShell:

```powershell
[IO.File]::WriteAllText($rutaAbsoluta, $texto, [Text.UTF8Encoding]::new($false))
```

**`[IO.File]` no respeta el `Set-Location` de PowerShell.** Usa el directorio
actual de .NET, que es otro. Siempre ruta absoluta.

## Verificar que cargó

El aislamiento entre tenants es **bloqueante**: no se entrega un cliente sin
que pase.

```bash
uv run pytest -m integracion tests/smoke/test_aislamiento_multitenant.py -v
```

Corre contra Supabase real a propósito: probar aislamiento contra un mock solo
prueba el mock.

## Por qué todo el acceso pasa por un solo archivo

El motor usa la `SERVICE_ROLE_KEY`, que **saltea RLS por diseño**. O sea que
RLS no es la defensa real del aislamiento: la defensa es que toda consulta
pase por [`brain/tenants/repositorio.py`](../../src/motor_voz/brain/tenants/repositorio.py)
y filtre por tenant ahí.

Eso lo hace cumplir `tests/test_un_solo_cliente_supabase.py`, que recorre
`src/motor_voz` entero con AST y falla si aparece `create_client` o
`acreate_client` en cualquier otro módulo. **No lo desactives.**
