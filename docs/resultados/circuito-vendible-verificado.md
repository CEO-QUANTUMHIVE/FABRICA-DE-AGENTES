# Circuito vendible verificado — 2026-08-16

No se escribió código. Se corrió el circuito completo contra **producción y la
base real** para poder decir, con evidencia, qué está terminado y qué no.

## Resultado

**Todo lo que se puede verificar sin una persona hablando, está verde.**

| Qué | Cómo se verificó | Resultado |
|---|---|---|
| Suite completa | `uv run pytest -q` | ✅ **398 passed**, 15 deseleccionados, 24 s |
| Aislamiento multi-tenant | smoke contra la base real | ✅ 8 passed |
| Borrador que no atiende | idem | ✅ incluido en esos 8 |
| Conocimiento versionado | idem | ✅ incluido en esos 8 |
| Persistencia multicanal | idem | ✅ incluido en esos 8 |
| Voces del catálogo existen en Fish | smoke contra la API de Fish | ✅ 4 passed, dos tenants con voces distintas |
| API viva | `GET /api/salud` | ✅ `{"estado":"ok","sesiones_hoy":10,"tope_diario":300}` |
| Catálogos públicos | `/api/niveles`, `/api/voces` | ✅ 200 |
| Widget servido | `/widget.js`, `/widget.html` | ✅ 200 |
| Landing con el widget embebido | `www.quantumhive.com.ar` | ✅ 200, referencia a `widget.js` presente |
| Panel servido | `/panel/` + sus assets | ✅ 200: shell, `manifest.webmanifest`, `icon.svg`, JS 260 KB, CSS 19 KB |
| Resolución de tenant por dominio | `POST /api/token` con `Origin` de la landing | ✅ `tenant: quantumhive`, sala `demo-quantumhive-pipeline--…`, plan `basico`, 240 s |
| El deploy tiene el código nuevo | rutas autenticadas responden **401**, no 404 | ✅ `/api/panel/tenants`, `/api/panel/{slug}/chat`, `/api/fabrica/negocios` |

Que las tres rutas devuelvan **401 y no 404** es la prueba de que lo desplegado
incluye el chat del panel y la fábrica: la ruta existe y exige sesión.

## Lo único que falta para cerrar, y no lo puede hacer una máquina

Entrar al panel con la sesión de Sergio, enseñarle algo al agente, publicarlo y
escucharlo. Son cinco minutos y está en la lista de abajo. No hace falta código.

## Verificación pendiente de una persona

1. `https://www.quantumhive.com.ar/panel/` → entrar.
2. Pestaña **Enseñar**: escribirle algo que hoy no sepa. Contesta el agente real.
3. Guardar el borrador y **publicar** la versión.
4. `https://www.quantumhive.com.ar/` → hablarle al widget y preguntar eso mismo.
5. Tiene que contestarlo con la voz del negocio. **Nivel 1**: la voz clonada
   solo la usa el pipeline (ver [`probar-un-tenant-a-oido.md`](../procesos/probar-un-tenant-a-oido.md)).

Si el paso 4 contesta lo viejo, el problema es la publicación, no la voz: el
borrador no atiende a propósito, y eso ya está cubierto por
`test_borrador_no_atiende.py`.

## Lo que quedó confirmado como roto (no era de este bloque)

`GET /webhooks/whatsapp` en producción devuelve **404**: falta la regla de Caddy
para `/webhooks/*`. Confirmado, no supuesto. Está en
[`conectar-whatsapp.md`](../procesos/conectar-whatsapp.md), parte A.3.
