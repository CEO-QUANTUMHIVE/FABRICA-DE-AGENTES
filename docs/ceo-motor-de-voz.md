# CEO departamental de Motor de Voz

> Documento histórico: este contrato pertenecía a la identificación errónea
> del checkout como `motor-de-voz`. El contrato vigente de este repositorio es
> [`ceo-fabrica-de-agentes.md`](ceo-fabrica-de-agentes.md). El departamento
> `motor-de-voz` permanece separado y apunta a `SOLO-MOTOR-DE-VOZ-`.

## Propósito y frontera

El CEO es la interfaz privada por la que QuantumCore puede descubrir este
departamento, hacer consultas cerradas y entregar trabajos estructurados. No
duplica objetivos, colas, presupuestos ni auditoría durable: esas funciones
siguen perteneciendo a QuantumCore.

```text
Dominus -> QuantumCore -> CEO Motor de Voz -> worker registrado -> resultado
```

El código departamental es `motor-de-voz`, el contrato es `1.0`, el
repositorio autorizado es `C:\Users\sergio\Desktop\FABRICA-DE-AGENTES` y una acción
solo puede apuntar a una rama `quantumcore/*`. `main` se rechaza siempre.

La implementación vive fuera de `brain/`:

- `src/motor_voz/ceo/departamento.py`: políticas, validación, idempotencia y
  despacho.
- `src/motor_voz/api/ceo.py`: autenticación, autorización multitenant y HTTP.
- `src/motor_voz/api/servidor.py`: incorpora las rutas al servidor `aiohttp`
  existente.
- `brain/tenants/repositorio.py`: sigue siendo el único acceso a Supabase.

## Autenticación

Las tres rutas requieren:

```http
Authorization: Bearer <QUANTUMCORE_TOKEN>
```

`QUANTUMCORE_TOKEN` es una credencial máquina-a-máquina exclusiva. Si la
variable falta o está vacía, las rutas fallan cerradas con `401`. El valor no
se devuelve ni se registra.

Cuando la consulta o acción incluye `tenant`, también es obligatoria la sesión
del actor humano que QuantumCore está representando:

```http
X-QuantumCore-Actor-Token: <access token de Supabase del actor>
```

El servidor valida ese token con `auth.get_user`, resuelve el tenant activo y
comprueba la fila de membresía para el par exacto `usuario_id + tenant_id`. La
credencial de QuantumCore por sí sola no permite cruzar negocios.

## Contrato HTTP

### Describir

```http
GET /v1/departamentos/motor-de-voz/descripcion
```

Devuelve identidad, versión, capacidades reales, consultas y trabajos
admitidos, perfiles de workers, familias de cerebros/modelos, límites, pruebas
y estado booleano de dependencias. Nunca devuelve valores de configuración.

### Consultar

```http
POST /v1/consultas
Content-Type: application/json

{"tipo":"arquitectura","correlacion_id":"corr-123"}
```

Tipos admitidos: `arquitectura`, `capacidades`, `estado_modulos`,
`documentacion`, `comandos_prueba`, `configuracion_publica`, `salud` y
`tenant`. No se aceptan rutas arbitrarias, comandos, scripts ni campos libres.

Ejemplo tenant-scoped:

```json
{
  "tipo": "tenant",
  "tenant": "quantumhive",
  "correlacion_id": "corr-tenant-001"
}
```

La respuesta de tenant contiene únicamente identificador, slug, nombre,
idioma y estado activo después de validar identidad y membresía.

### Accionar

```http
POST /v1/acciones
Content-Type: application/json
```

Ejemplo sin secretos:

```json
{
  "trabajo_id": "job-018",
  "clave_idempotencia": "motor-de-voz:job-018:v1",
  "departamento": "motor-de-voz",
  "repositorio": "C:\\Users\\sergio\\Desktop\\FABRICA-DE-AGENTES",
  "tipo_trabajo": "implementar_codigo",
  "titulo": "Agregar una validación",
  "objetivo": "Implementar el cambio autorizado por QuantumCore.",
  "resultado_esperado": "Suite en verde y evidencia estructurada.",
  "rama": "quantumcore/job-018",
  "worker": "codex-local",
  "cerebro": "openai",
  "modelo": "codex-seleccionado-por-quantumcore",
  "tiempo_maximo_segundos": 600,
  "presupuesto_maximo_usd": 2.0,
  "herramientas_permitidas": ["leer_archivos", "editar_archivos", "pytest"],
  "rutas": ["src/motor_voz", "tests"],
  "auditoria": {
    "solicitado_por": "quantumcore",
    "correlacion_id": "corr-job-018",
    "objetivo_id": "objetivo-7"
  }
}
```

Antes de despachar se validan departamento, repositorio, tenant y membresía
cuando corresponden, tipo, rama, worker, cerebro/modelo, herramientas, tiempo,
presupuesto, idempotencia y rutas. Se rechazan campos de comando, shell,
script, entorno o código ejecutable. El texto de `objetivo` describe el
resultado: no puede ampliar las herramientas ni cambiar las políticas.

Una respuesta completada tiene esta forma:

```json
{
  "trabajo_id": "job-018",
  "clave_idempotencia": "motor-de-voz:job-018:v1",
  "estado": "completado",
  "resumen": "Cambio terminado.",
  "archivos_modificados": ["tests/test_validacion.py"],
  "pruebas_ejecutadas": ["uv run pytest -q"],
  "resultado_pruebas": "426 passed",
  "rama": "quantumcore/job-018",
  "commit": "abcdef1",
  "evidencia": [{"tipo": "test", "resultado": "ok"}],
  "tokens": {"entrada": 1200, "salida": 300},
  "costo_usd": 0.08,
  "duracion_ms": 42000,
  "motivo": null,
  "departamento": "motor-de-voz",
  "tenant": null,
  "worker": "codex-local",
  "cerebro": "openai",
  "modelo": "codex-seleccionado-por-quantumcore",
  "herramientas": ["leer_archivos", "editar_archivos", "pytest"],
  "correlacion_id": "corr-job-018",
  "inicio": "2026-08-20T12:00:00+00:00",
  "fin": "2026-08-20T12:00:42+00:00"
}
```

Una prueba fallida produce `estado: error`; no se convierte en éxito. Los
errores del worker no exponen excepciones internas y las claves/valores
sensibles se redactan.

## Workers y cerebros

Los perfiles declarados son:

| Worker | Puede | No puede |
|---|---|---|
| `codex-local` | leer/editar dentro del checkout, Git local, pruebas, build y documentación | salir del checkout, `main`, push, deploy o comandos recibidos |
| `claude-local` | las mismas operaciones locales autorizadas | las mismas prohibiciones |
| `modelo-directo` | analizar texto y redactar | archivos, comandos, Git, build, red libre |

Las combinaciones se validan por tipo de trabajo. Codex usa cerebro `openai`
y modelos `codex*`; Claude usa `anthropic` y `claude*`; modelo directo admite
las familias declaradas `gpt*`, `claude*`, `gemini*`, `llama*` y
`openai/gpt-oss*`. No hay claves ni un proveedor fijado dentro del contrato.

Los tipos implementados son `analizar_codigo`, `implementar_codigo`,
`ejecutar_pruebas`, `actualizar_documentacion`, `clasificar`, `resumir` y
`redactar_documentacion`. No se declara todavía un worker especializado de
operaciones de voz.

## Conectar un worker

Declarar un perfil no lo vuelve ejecutable. El proceso que arranca la API debe
registrar adaptadores concretos y auditados:

```python
from motor_voz.api.servidor import crear_app
from motor_voz.ceo.departamento import RegistroWorkers

registro = RegistroWorkers()
registro.registrar("codex-local", adaptador_codex_seguro)
registro.registrar("claude-local", adaptador_claude_seguro)

app = crear_app(registro_workers_ceo=registro)
```

Cada adaptador es asíncrono, recibe un mapa ya normalizado y devuelve un mapa
de resultado. El adaptador debe aplicar las herramientas autorizadas como una
lista cerrada; nunca debe construir un comando desde `objetivo`, documentos o
salida de un modelo. No se suministra un adaptador de shell genérico.

## Registro en QuantumCore

1. Registrar un único departamento con código `motor-de-voz`, estado `activo`,
   este repositorio y prefijo `quantumcore/`. Si ya existe, actualizarlo: no
   crear un duplicado.
2. Guardar `QUANTUMCORE_TOKEN` en el almacén de secretos de QuantumCore y en el
   entorno de esta API; nunca en la base ni en el repositorio.
3. Configurar la URL base de la API existente y las tres rutas `/v1`.
4. Cargar en QuantumCore los mismos límites, tipos, workers y combinaciones que
   devuelve `descripcion`; la descripción en vivo es la fuente verificable.
5. Para operaciones de tenant, reenviar el access token Supabase del actor en
   `X-QuantumCore-Actor-Token` y el slug en la solicitud.
6. Conectar al arranque los adaptadores de workers que realmente estén
   instalados. `workers_conectados` permite verificar cuáles están listos.
7. Usar `trabajo_id`, `clave_idempotencia` y `correlacion_id` durables de
   QuantumCore; persistir allí la respuesta completa y su evidencia.

## Pruebas y build

```powershell
$env:UV_CACHE_DIR='C:\Users\sergio\Desktop\FABRICA-DE-AGENTES\.uv-cache'
uv run pytest -q tests/test_ceo_departamental.py
uv run pytest -q
npm.cmd run build --prefix frontend/panel
npm.cmd run build --prefix frontend/widget
```

## Limitaciones actuales

- El repositorio incluye el registro y los perfiles, pero no instala ni lanza
  procesos Codex/Claude. Sin adaptador inyectado, una acción válida se rechaza
  como `worker_no_conectado`.
- La deduplicación local cubre solicitudes concurrentes y repetidas mientras
  vive el proceso. QuantumCore conserva la idempotencia durable entre
  reinicios; este repositorio no replica su base ni sus colas.
- No existe todavía un worker especializado para acciones reales de voz.
- No se realizaron push, PR, merge ni despliegue como parte de esta entrega.
