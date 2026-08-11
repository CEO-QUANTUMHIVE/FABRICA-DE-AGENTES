# Aplicar una migración de Supabase

Proyecto: `bcexirhurfigrehfarol`. Las migraciones viven en
`supabase/migrations/`, numeradas y en orden.

## El comando

```bash
supabase db push --db-url "postgresql://postgres:CONTRASEÑA@db.bcexirhurfigrehfarol.supabase.co:5432/postgres"
```

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
