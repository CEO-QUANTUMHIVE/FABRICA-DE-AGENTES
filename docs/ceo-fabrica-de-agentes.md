# CEO departamental de Fábrica de Agentes

## Identidad y frontera

Este CEO es la interfaz privada por la que QuantumCore descubre y coordina el
departamento que vive en este repositorio. No es el departamento Motor de Voz:
ambos conservan registros, repositorios y responsabilidades separados.

```text
Dominus -> QuantumCore -> CEO Fábrica de Agentes -> worker registrado -> evidencia
```

| Dato | Valor |
|---|---|
| Código | `fabrica-de-agentes` |
| Nombre | `Fábrica de Agentes` |
| Contrato | `1.0` |
| Repositorio | `C:\Users\sergio\Desktop\FABRICA-DE-AGENTES` |
| Ramas de trabajo | `quantumcore/*` |

QuantumCore conserva objetivos, colas, presupuestos, correlación, evidencia y
auditoría durables. Este CEO valida el contrato local y despacha solamente a
workers registrados. Nunca acepta comandos, shell, código dinámico, `main`,
push, deploy ni rutas externas al checkout.

## Autenticación

Las tres rutas requieren un secreto compartido que se entrega fuera de Git:

```http
Authorization: Bearer <QUANTUMCORE_TOKEN>
```

Si la solicitud incluye un tenant, también requiere la sesión Supabase del
actor:

```http
X-QuantumCore-Actor-Token: <sesión del actor>
```

La sesión se valida junto con la membresía exacta y el estado activo del
tenant. Tener una sesión válida de otro negocio no concede acceso.

## Rutas

### Descripción

```http
GET /v1/departamentos/fabrica-de-agentes/descripcion
```

Devuelve identidad, capacidades, políticas, límites, dependencias booleanas y
workers conectados. No devuelve valores secretos.

### Consulta de solo lectura

```http
POST /v1/consultas
Content-Type: application/json

{"tipo":"arquitectura","correlacion_id":"corr-123"}
```

Sólo se admiten los campos `tipo`, `tenant` y `correlacion_id`. La respuesta
marca `solo_lectura: true` y conserva `correlacion_id` cuando fue enviado.

### Acción

```http
POST /v1/acciones
Content-Type: application/json
```

La acción usa un objeto plano y estructurado. Debe incluir identificadores de
trabajo e idempotencia, departamento, repositorio, tipo, objetivo y resultado
esperado, rama, worker, cerebro/modelo, límites, herramientas y auditoría. El
CEO vuelve a validar todo antes de buscar un worker.

Los perfiles declarados son `codex-local`, `claude-local` y `modelo-directo`.
Declararlos no los conecta: sin un adaptador auditado inyectado al iniciar el
servidor, una acción válida responde `worker_no_conectado`.

## Conexión desde QuantumCore

QuantumCore usa `AdaptadorFabricaDeAgentes`, porque el sobre genérico de
OpenCode no coincide con este contrato. El adaptador:

- consulta la ruta exacta de `fabrica-de-agentes`;
- traduce una consulta a `{tipo, tenant?, correlacion_id?}`;
- reenvía la sesión del actor sólo en la cabecera privada;
- exige una acción plana y completa antes de hacer una llamada de red;
- no expone el secreto compartido en su representación ni en la URL.

El departamento `fabrica-de-agentes` debe permanecer asociado a este
repositorio. `motor-de-voz` sigue asociado a `SOLO-MOTOR-DE-VOZ-`; no se deben
reasignar ni fusionar sus memorias.

## Verificación local

```powershell
$env:UV_CACHE_DIR='C:\Users\sergio\Desktop\FABRICA-DE-AGENTES\.uv-cache'
uv run pytest -q tests/test_ceo_departamental.py
```

Para una prueba de integración, ambos procesos reciben temporalmente el mismo
`QUANTUMCORE_TOKEN`. El valor no se imprime ni se guarda en el repositorio. La
prueba segura termina en `POST /v1/consultas`; no invoca acciones, workers,
push ni despliegue.

## Límites actuales

- La idempotencia del CEO dura lo mismo que su proceso; la durable vive en
  QuantumCore.
- Todavía no hay un adaptador real de Codex o Claude registrado en este
  proceso.
- La consulta local demuestra contrato y autenticación, pero no publica el CEO
  en Internet ni modifica servicios productivos.
