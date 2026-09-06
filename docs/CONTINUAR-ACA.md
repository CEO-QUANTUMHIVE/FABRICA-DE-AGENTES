# Brief de continuación — Motor de Voz

> ## ⚡ Estado al 2026-09-02 — Apify integrado y webhook de Meta publicado
>
> **Instagram público:** `INTELIGENCIA-COMERCIAL-SCRAP` ya tiene la integración
> backend con el Actor oficial `apify/instagram-scraper`, en la rama
> `codex/apify-instagram-perfilador`, commit `483478e` (41 pruebas en verde).
> Hace una sola consulta `details` por alta, manda el token como Bearer y cae al
> lector público anterior si Apify falla. **Todavía no está activo en producción:**
> falta crear/cargar `APIFY_TOKEN` en Secret Manager, desplegar esa revisión y
> ejecutar un smoke real.
>
> **Meta:** `GET /webhooks/whatsapp` ya atraviesa Caddy hacia la API. Se agregó
> `handle /webhooks/*` en `livekit-quantumhive`, se validó el Caddyfile antes de
> recargar y se conservó `/etc/caddy/Caddyfile.bak-20260902-whatsapp`. Evidencia:
> `/api/salud` 200, `/widget.js` 200 y webhook 403 — rechazo correcto mientras
> `WHATSAPP_VERIFY_TOKEN` no esté cargado. Ya no hay un 404 de ruteo.
>
> **Siguiente acción humana en Meta:** crear/confirmar la app Business, pedir
> acceso avanzado y App Review, completar Tech Provider y crear la configuración
> de Embedded Signup. De ahí salen `META_APP_ID`, `META_APP_SECRET` y
> `META_EMBEDDED_SIGNUP_CONFIG_ID`; ningún agente opera el panel de Meta. El
> diseño para sumar Instagram y Facebook sin duplicar el cerebro está en
> [`superpowers/plans/2026-09-02-meta-canales-unificados.md`](superpowers/plans/2026-09-02-meta-canales-unificados.md).

> ## ⚡ Estado al 2026-08-31 — Meta verificó la empresa. Esto manda sobre todo lo de abajo
>
> **El bloqueo de Meta del 2026-08-16 está resuelto por la vía limpia.** Hay un
> portfolio nuevo y sano:
>
> | | |
> |---|---|
> | Portfolio | `Quantumhive`, **`business_id 1339027384106629`** |
> | Verificación de la empresa | ✅ **Verificada**, "originalmente el Aug 31, 2026" |
> | Evidencia | mail de Meta for Business + Centro de seguridad del portfolio |
> | Caso de uso elegido | "La aplicación requiere acceso a permisos en Meta for Developers" |
>
> **El portfolio viejo `1079094061364956` queda abandonado.** Donde aparezca más
> abajo en este documento, está desactualizado.
>
> **El código no se toca:** el `waba_id` se resuelve en tiempo de ejecución desde
> el onboarding (`channels/whatsapp/onboarding.py`), nunca está cableado. Cambiar
> de portfolio es cero líneas de Python.
>
> **Lo que esto desbloquea y lo que no:**
>
> - ✅ Ya se puede **pedir acceso avanzado** a `whatsapp_business_management` y
>   `whatsapp_business_messaging`: ese pedido exigía la empresa verificada.
> - ✅ Ya se puede conectar **el número propio de QuantumHive** con la app en modo
>   desarrollo, agregando el número como tester. No hace falta nada más de Meta.
> - ❌ **Todavía falta App Review publicada + Tech Provider** para ofrecer
>   Coexistencia a **clientes externos**. Ese es el único tramo abierto.
>
> Descartado el 2026-08-31: **no se usa un agregador externo** (Zernio/Late ni
> ningún BSP). La conexión la hace QuantumHive directo contra Meta, con la
> custodia del token del cliente en nuestra bóveda. Ver §11.
>
> Siguiente paso operativo: continuar
> [`procesos/conectar-whatsapp.md`](procesos/conectar-whatsapp.md). La regla de
> Caddy ya está aplicada; faltan credenciales de la app, verificar el webhook en
> Meta, confirmar migraciones/worker y ejecutar el alta desde el botón del panel.

> ## ⚡ Estado al 2026-08-24 — Perfilador conectado a la Fábrica
>
> Se integró el repo `INTELIGENCIA-COMERCIAL-SCRAP` sin copiarlo ni modificarlo:
>
> - la Fábrica llama `POST /clientes/investigar` desde su backend;
> - el token interno nunca llega al navegador;
> - el autoguiado acepta web, Instagram, Facebook y Google Maps;
> - servicios, precios, horarios, preguntas frecuentes y datos públicos se
>   transforman en piezas versionadas del conocimiento del tenant;
> - el logo y los colores encontrados se aplican al orbe y se recuperan desde
>   el conocimiento publicado al volver a iniciar sesión;
> - una caída del Perfilador no rompe el brain, voz, panel ni WhatsApp;
> - **449 tests backend + 5 frontend en verde** y build Vite correcto.
>
> Para encenderlo en producción faltan solamente tres pasos operativos:
>
> 1. desplegar el Perfilador con su `TOKEN_INTERNO` y una URL HTTPS privada;
> 2. cargar esa URL y token como `CENTRO_INTELIGENCIA_URL` y
>    `CENTRO_INTELIGENCIA_TOKEN` en el backend de la Fábrica;
> 3. desplegar API y frontend de la Fábrica.
>
> Procedimiento: [`procesos/conectar-perfilador.md`](procesos/conectar-perfilador.md).

> ## ⚡ Estado al 2026-08-23 — reemplaza las decisiones viejas sobre BSP
>
> Se eligió **infraestructura propia, directo con Meta**, sin YCloud ni
> 360dialog. Ya está implementado Embedded Signup con Coexistencia en el panel:
>
> - botón **Conectar mi WhatsApp Business**;
> - código temporal canjeado únicamente en el backend;
> - descubrimiento y validación del número dentro del WABA autorizado;
> - registro del número y suscripción del webhook;
> - token en bóveda privada de la VM (`WHATSAPP_SECRET_DIR`, archivo `0600`),
>   nunca en navegador ni Supabase;
> - asociación global segura `phone_number_id → tenant`, sin reasignar números;
> - **443 tests backend en verde**, 4 del frontend y build Vite correcto.
>
> Lo que falta para probar con el número real ya no se resuelve programando:
>
> 1. Sergio entra manualmente a Meta; ningún agente opera esa cuenta.
> 2. QuantumHive crea/recupera su app, completa Business Verification y Tech
>    Provider, y crea la configuración de Embedded Signup.
> 3. En la VM se cargan `META_APP_ID`, `META_APP_SECRET`,
>    `META_EMBEDDED_SIGNUP_CONFIG_ID`, `WHATSAPP_VERIFY_TOKEN`,
>    `WHATSAPP_REGISTRATION_PIN` y `WHATSAPP_SECRET_DIR`.
> 4. Publicar `/webhooks/whatsapp` en Caddy, desplegar API + worker y verificar
>    el campo `messages` en Meta.
> 5. Sergio pulsa el botón del panel y autoriza su número. Conserva el número y
>    la app de WhatsApp Business mediante Coexistencia.
>
> Meta sigue siendo obligatoria y puede cobrar sus conversaciones. Lo que esta
> arquitectura elimina es el software y abono mensual de un BSP intermediario.

> ## ⚡ Estado al 2026-08-16 — leé esto primero
>
> **Todo lo de abajo sigue valiendo, pero esto es lo último y lo que manda.**
>
> ### Lo que quedó andando en producción
>
> | | |
> |---|---|
> | Login del panel | ✅ `quantumhive.com.ar/panel/`, gate E2E cerrado contra la base real |
> | Chat real con el agente | ✅ `POST /api/panel/{slug}/chat`, probado en producción con Groq |
> | Alta de negocios | ✅ `POST /api/fabrica/negocios` + `/activar` |
> | Las 15 migraciones | ✅ **todas aplicadas**, verificadas en la base |
> | API y agente | ✅ desplegados, `registered worker` |
> | Landing + panel | ✅ revisión `landing-quantumhive-00040-xmc` |
> | Canal WhatsApp | ✅ código completo: parser, firma, webhook, cerebro, colas, envío, worker, topes |
> | Tests | ✅ **398 en verde** |
>
> ### Circuito vendible: verificado de punta a punta el 2026-08-16
>
> Se corrió contra producción y la base real. **398 tests en verde**, 8 smoke de
> base real, 4 de voces, API viva, panel y widget servidos, el tenant resuelto
> por dominio, y las rutas del panel y la fábrica respondiendo 401 (existen y
> exigen sesión) en lo desplegado. Detalle y evidencia en
> [`resultados/circuito-vendible-verificado.md`](resultados/circuito-vendible-verificado.md).
>
> **Falta un solo paso, y es de una persona:** entrar al panel, enseñarle algo,
> publicarlo y escucharlo en el widget. Cinco minutos, sin código.
>
> Actualizado el 2026-09-02: la regla de Caddy para `/webhooks/*` ya está
> aplicada. El endpoint devuelve 403 sin verify token, que es el cierre seguro
> esperado hasta cargar la configuración de Meta.
>
> ### Cómo se aplican migraciones ahora
>
> Con `SUPABASE_ACCESS_TOKEN` del `.env` contra la API de administración. **No
> hace falta la contraseña de la base ni `supabase link`.** Ojo: hay que mandar
> un `User-Agent`, si no Cloudflare devuelve 403 code 1010 antes de mirar el
> token.
>
> ### El repo de la landing ya existe
>
> [`CEO-QUANTUMHIVE/pagina-web-landing-quantumhive`](https://github.com/CEO-QUANTUMHIVE/pagina-web-landing-quantumhive).
> La carpeta local está en `C:\Users\sergio\Desktop\boveda obsidian\landing` y
> vive **dentro del repo de la bóveda de Obsidian**, con 1266 archivos de otros
> proyectos sin commitear: no se pushea desde ahí.
>
> ### 🔴 La corrección grande de este bloque
>
> **Ningún cliente cambia de número. Nunca.** Y hay camino para eso hoy, sin
> esperar la verificación:
>
> - **La verificación estándar ni siquiera está disponible para cuentas de
>   coexistencia.** Va *Partner-Led Business Verification*, que la hace el
>   partner.
> - O sea: **un BSP con coexistencia (360dialog, €49/mes fijo, sin recargo por
>   mensaje) conecta el número de siempre esta semana.** El dueño escanea un QR
>   desde su app de WhatsApp Business y listo: conserva número, app e historial.
> - Requisito real que **falta**: completar los datos del portfolio de Meta
>   (nombre legal, dirección, sitio, teléfono). Gratis y sin papeles.
>
> **Ir por un BSP no tira nada del código.** El grafo lo confirmó:
> `enviar_texto` no tiene dependientes, se engancha en una sola línea
> (`channels/enviador.py:52`). Cambian el cliente de envío y la validación de
> firma; parser, cerebro, colas, límites y aislamiento quedan igual. Volver a
> Meta directo el día que salga Tech Provider es cambiar esa línea al revés.
>
> ### 🚫 Estado en Meta — LA CUENTA ESTÁ DESHABILITADA
>
> **El 2026-08-16 Meta deshabilitó la cuenta personal de Facebook de Sergio por
> "integridad de la cuenta", y la pantalla dice que no hay más revisión.** Pasó
> después de que un agente le automatizara el navegador sobre
> `developers.facebook.com`: primero saltó un checkpoint, y la cuenta cayó
> igual poco después.
>
> **NUNCA manejar cuentas de Meta con automatización de navegador.** Ni para
> mirar. Esta regla costó una cuenta de años.
>
> **Tampoco abrir una segunda cuenta desde el mismo equipo/IP para seguir donde
> quedó la primera:** Meta lo llama evasión, vincula por dispositivo, navegador,
> IP y teléfono, y el resultado normal es perder las dos.
>
> - Portfolio `QuantumHive` (`business_id 1079094061364956`): entidad separada
>   de la cuenta personal, **estado desconocido**. Si sobrevivió, se recupera
>   sumándole otro administrador; si Sergio era el único admin, puede haber
>   quedado inaccesible.
>   **→ Superado el 2026-08-31:** se abandonó y hay un portfolio nuevo verificado
>   (`1339027384106629`). Ver el bloque del 2026-08-31 al principio del documento.
> - App `quantumhive`: sin confirmar si llegó a crearse.
> - Sergio tiene **CUIT y monotributo**, así que la verificación sigue siendo
>   posible el día que haya una cuenta con la que hacerla.
>
> Caminos limpios, en orden de preferencia:
>
> 1. Bajar "Descargar tu información" antes de que se pierda.
> 2. Apelar por fuera del botón: formulario de cuentas deshabilitadas y, si
>    hubo actividad comercial, soporte de Meta Business.
> 3. Que **otra persona real** del entorno (socio, familiar que trabaje con él),
>    con cuenta vieja y legítima, sea la titular del portfolio y agregue a
>    Sergio como administrador. Eso no es evasión: es otra titularidad.
>
> ### Lo próximo, en orden
>
> **Todo lo de WhatsApp está bloqueado hasta resolver el acceso a Meta.** No es
> una traba de código: el código está completo y en verde.
>
> 1. Resolver el acceso a Meta (ver arriba). Bloquea 2 y 3.
> 2. Completar datos del portfolio de Meta (5 min, de Sergio).
> 3. Onboarding de coexistencia en 360dialog con el número real.
> 4. Escribir `channels/whatsapp/cliente_360.py` + su verificación de webhook.
> 5. Regla de Caddy para `/webhooks/*` — hoy da 404 — y systemd del worker.
> 6. Handoff: contestar desde el panel.
>
> **Lo que sí se puede avanzar sin Meta:** el widget de voz en la web ya
> funciona y es el producto original; los canales que no pasan por Meta
> (Telegram) usan el mismo cerebro y las mismas colas.
>
> ### Pendientes de seguridad
>
> - **Rotar la contraseña de la base de Supabase**: se pegó en el chat.
> - El `SUPABASE_ACCESS_TOKEN` se mostró truncado en una terminal; regenerarlo
>   si se quiere estar tranquilo.

**Fecha:** 2026-08-09
**Rama:** `arquitectura/spec-motor-voz` en `CEO-QUANTUMHIVE/FABRICA-DE-AGENTES`
(se llamaba `MOTOR-DE-VOZ-` hasta el 2026-08-11; GitHub redirige el nombre
viejo, pero el paquete de Python sigue siendo `motor_voz` a propósito —
renombrarlo toca cada import y el deploy, y no devuelve nada)
**Estado:** el motor habla y está desplegado. Falta conectar las últimas piezas.

Para el agente que siga: leé `AGENTS.md` primero, y **consultá el grafo antes
de abrir archivos** (`graphify query "..."`).

---

## 1. Qué es esto

El motor de voz de QuantumHive. Un visitante habla por el navegador y un
agente le contesta hablando. Tres motores intercambiables que son tres
planes comerciales.

```
basico    pipeline   Groq STT + Groq LLM + Fish TTS   voz clonada · sirve en WhatsApp
medio     gemini     Gemini Live, voz a voz            voz de Google
premium   openai     OpenAI Realtime, voz a voz        voz de OpenAI
```

Se elige con `MOTOR=` en el `.env`, o por sesión desde la demo web.

---

## 2. Lo que YA funciona, verificado

| Pieza | Estado |
|---|---|
| Groq STT en español | ✅ probado con audio real, reconoce voseo |
| Groq LLM | ✅ probado, responde activo y con signos de entonación |
| Fish TTS con voz clonada | ✅ probado, `s2.1-pro` pago, saldo USD 5 |
| Conversación local completa | ✅ Sergio la probó, con interrupción |
| VM en Google Cloud | ✅ `livekit-quantumhive`, e2-micro gratis, us-east1-b |
| LiveKit self-hosteado | ✅ systemd, `Restart=always`, sobrevive reinicio |
| DNS + TLS | ✅ `https://voz.quantumhive.com.ar` → 200, Let's Encrypt |
| Demo web con 3 niveles | ✅ código listo, probado en local |
| API + agente en producción | ✅ VM propia `motor-voz-agente`, systemd (ver 3.1) |
| Nivel 2 · Gemini Live | ✅ probado contra Vertex AI real (ver 3.2) |
| Nivel 3 · OpenAI Realtime | ✅ vía Azure, Sergio lo probó (ver 3.3) |
| Widget embebible | ✅ en `www.quantumhive.com.ar` (ver 3.4) |
| Selector de voces | ✅ 8 de Gemini + 10 de OpenAI, agrupadas por género |
| Grafo de conocimiento | ✅ ~600 nodos, se regenera solo en cada commit |
| Tests | ✅ **252 en verde**, ninguno salteado, 5 deseleccionados |
| Multi-tenant | ✅ dos tenants en Supabase, aislamiento probado contra la base real |
| Tools del agente | ✅ Fase 9: público e interno, nadie crea negocios hablando |
| Motor de voz aislado | ✅ repo propio [`SOLO-MOTOR-DE-VOZ-`](https://github.com/CEO-QUANTUMHIVE/SOLO-MOTOR-DE-VOZ-) para que cada producto se lleve una copia |

### Configuración vigente

```
VOZ-003        63f9f124b940…       clonada del fundador, 6 clips graves
FISH_MODEL     s2.1-pro            pago, saldo USD 5,00
FISH_SPEED     1.25
FISH_TEMP      1.0
GCP_PROJECT    bubbly-stone-502214-u7
GEMINI_MODEL   gemini-live-2.5-flash-native-audio   (nombre de Vertex, NO el de ai.google.dev)
GCP_LOCATION   us-east4
VAD_SILENCIO_MS  900     cuanto silencio antes de dar el turno por terminado
VAD_RELLENO_MS   300
VAD_UMBRAL       0.6     mas alto = menos sensible. Default de silero: 0.5
```

### Infraestructura

```
livekit-quantumhive   e2-micro GRATIS, us-east1-b    LiveKit + Caddy + estáticos del widget
motor-voz-agente      e2-medium ~USD 27/mes           API de tokens + agente (IP interna 10.142.0.9)
landing-quantumhive   Cloud Run, us-central1          www.quantumhive.com.ar
```

Caddy en `livekit-quantumhive` rutea: `/api/*` → `10.142.0.9:8080`,
`/widget.js` `/widget.html` `/assets/*` → `/var/www/widget`, el resto →
LiveKit en `localhost:7880`.

**Azure OpenAI** (nivel 3) vive en una suscripción **distinta** a la de la
VM: `Azure subscription 1` (`1f885a81-…`), tipo `FreeTrial` con tope de
gasto **activado**, o sea que no puede pasarse de los USD 200. Recurso
`quantumhive-voz-openai` en `eastus2`, deployment `gpt-realtime-mini`.
La otra suscripción (`quantumhive`, la de la VM) es pago por uso **sin
tope**: no crear recursos ahí por error.

---

## 3. Lo que FALTA — en orden

### 3.1 API y agente en producción ← ✅ HECHO (2026-08-09)

**Ya no es lo que separa al motor de producción.** Terminó en una VM
separada de LiveKit, no en la misma — la razón cambió a mitad de camino.

Medimos memoria real antes de decidir: importar livekit + plugins cuesta
470 MB fijos por proceso, el modelo VAD 16 MB más, y cada conversación
solo 12 MB. Con eso, meter el agente en la e2-micro de LiveKit (969 MB)
era jugado — y los defaults de producción de LiveKit lo hacían peor:
`num_idle_processes` trae `prod_default=4`, o sea 4 procesos ociosos a
470 MB cada uno (1,9 GB) antes de atender la primera llamada. Eso se
blindó en [`agente.py`](../src/motor_voz/voice/agente.py) — commit
`6b63f9b` — con `num_idle_processes=0`, `job_executor_type=THREAD`
(comparte el costo fijo entre sesiones en vez de pagarlo por proceso) y
`job_memory_warn_mb=600`, todo configurable por entorno.

Decisión final: **dos VMs, no Cloud Run.** El servicio de Cloud Run sigue
desplegado pero devuelve 403 por la política `iam.allowedPolicyMemberDomains`
que bloquea `allUsers`, y Sergio eligió no aflojarla.

- `livekit-quantumhive` (e2-micro, gratis) — sigue solo con LiveKit + Caddy,
  **sin tocar**. 969 MB, ~594 MB disponibles sin el agente compitiendo.
- `motor-voz-agente` (e2-medium, `us-east1-b`, IP interna `10.142.0.9`) —
  VM nueva, corre la API y el agente. Necesitó:
  - IP externa propia (excepción a `constraints/compute.vmExternalIpAccess`
    agregada por Sergio — esa política no la toca un agente) porque el
    agente llama a Groq/Fish/LiveKit en cada conversación, no solo en el
    setup. No hay Cloud NAT en el proyecto.
  - `.env` armado a mano con `LIVEKIT_URL=wss://voz.quantumhive.com.ar` y
    las claves de Secret Manager (`motor-voz-groq`, `motor-voz-fish`,
    `motor-voz-livekit-key`, `motor-voz-livekit-secret`) — **cuidado**: la
    VM no tiene scope de Secret Manager (mismo scope que la de LiveKit),
    así que las claves se empujan por `scp`, no se leen desde la VM.
  - Dos servicios systemd con `Restart=always`: `motor-voz-api`
    (`python -m motor_voz.api.servidor`, puerto 8080) y `motor-voz-agente`
    (`python -m motor_voz.voice.agente start`).
- `Caddyfile` en `livekit-quantumhive` ahora usa `handle` para que
  `/api/*` vaya a `10.142.0.9:8080` (la VM del agente) y el resto a
  LiveKit en `localhost:7880`. El firewall `default-allow-internal` ya
  cubre el tráfico entre VMs, no hizo falta regla nueva.

Verificado end-to-end: `/api/salud`, `/api/niveles` y `POST /api/token`
responden por `https://voz.quantumhive.com.ar`, el token emitido trae sala
y JWT válidos, y el worker aparece `registered` en los logs de LiveKit.
`free -m` en ambas VMs con margen (594 MB y 3,2 GB disponibles).

Trampa nueva para el próximo: si copiás un `.env` local a producción,
**revisá `LIVEKIT_API_KEY`/`LIVEKIT_API_SECRET`** — el `.env` de desarrollo
tiene las credenciales de `livekit-server --dev` (`devkey`/`secret`, 6
bytes), no las de Secret Manager. Con esas el agente conecta y arranca
bien, pero LiveKit lo rechaza con 401 recién al intentar registrarse.

### 3.2 Probar el nivel 2 (Gemini) en vivo ← ✅ HECHO (2026-08-09)

**Andaba mal, y no era ni el modelo ni la región.** Al probarlo en vivo por
primera vez tiraba `RuntimeError: Plugins must be registered on the main
thread`. Causa real: `voice/motores.py` importaba `livekit.plugins.google`
recién adentro de `_gemini()`, que corre en el hilo del job, no en el
principal — y livekit-agents exige que el registro de plugins pase por
ahí. Mismo problema latente en `_openai()`. Fix en commit `25603f3`:
los tres imports (`silero`, `google`, `openai.realtime`) se movieron a
nivel de módulo.

Verificado en producción contra Vertex AI real: `model_provider: "Vertex
AI"`, `model_name: "gemini-live-2.5-flash-native-audio"`, tokens de audio
de salida generados, sin error. Consume créditos de Google Cloud del
proyecto `bubbly-stone-502214-u7`, no tarjeta.

De paso quedó una mejora de higiene que no era la causa pero no estaba de
más: la VM `motor-voz-agente` se había creado con los scopes de OAuth de
`livekit-quantumhive` (logging, monitoring, pubsub…), sin `cloud-platform`.
Se le agregó ese scope (para Vertex AI y lo que venga). El service account
ya tenía el rol IAM correcto (`roles/aiplatform.user`) desde el vamos — el
IAM nunca fue el problema, el scope de la instancia sí lo hubiera sido para
cualquier otra llamada a una API de Google Cloud desde esa VM.

### 3.3 Nivel 3 (OpenAI) — bloqueado, esperando a Sergio

El código está listo: `voice/motores.py:_openai` ya sabe hablar con Azure.
Lo que falta son datos que solo salen del portal de Azure.

**Estado real (verificado el 2026-08-09 leyendo el `.env`):**

```
AZURE_OPENAI_API_KEY       cargada
AZURE_OPENAI_ENDPOINT      VACIA   ← sin esto no hay a donde conectarse
AZURE_OPENAI_DEPLOYMENT    VACIA   ← ni que modelo usar
```

O sea: hay una clave, pero no el recurso. Una clave sin endpoint no sirve.

**Pasos para desbloquearlo** (portal de Azure, `portal.azure.com`):

1. **Crear el recurso.** Buscar "Azure OpenAI" → Crear. Elegir la
   suscripción con los créditos. En región, **elegir una que tenga
   modelos Realtime** — no todas las tienen, y es el error más común:
   el recurso se crea igual y recién al buscar el modelo se descubre que
   ahí no está. `East US 2` y `Sweden Central` son las habituales;
   confirmar en la tabla de disponibilidad de la doc de Azure antes de
   elegir, porque cambia seguido.
2. **Crear el deployment.** Entrar al recurso → Azure AI Foundry / Model
   deployments → Deploy model. Buscar un modelo **realtime** (family
   `gpt-realtime` / `gpt-4o-realtime-preview`). El **nombre del
   deployment lo elegís vos** — anotalo tal cual, con mayúsculas y
   guiones, porque es lo que va en `AZURE_OPENAI_DEPLOYMENT`.
3. **Copiar los tres datos** de "Keys and Endpoint" del recurso:
   endpoint (`https://<nombre>.openai.azure.com/`), una de las dos
   claves, y el nombre del deployment del paso 2.
4. **Pasármelos.** Yo los subo a Secret Manager (`motor-voz-azure-*`,
   mismo patrón que las otras), los cableo en el `.env` de la VM,
   reinicio el agente y lo pruebo en vivo.
5. **Sacar el candado del widget.** En `frontend/widget/app.js`,
   `NIVELES_LISTOS` pasa de `new Set([1, 2])` a `new Set([1, 2, 3])`, y
   el botón "Realismo extremo" deja de decir "Pronto".

Hasta entonces el nivel 3 se ve en el selector pero avisa que no está
disponible, en vez de intentar conectar y fallar.

### 3.4 Servir el widget ← ✅ HECHO (2026-08-09/10)

El fragmento que promete el playbook **ya existe y está instalado** en
`www.quantumhive.com.ar`:

```html
<script src="https://voz.quantumhive.com.ar/widget.js" data-tenant="quantumhive" defer></script>
```

Vive en `frontend/widget/` y es un port fiel del orbe de
`CEO-QUANTUMHIVE/QUANTUM-ASISTENTE-` (rama `agent/navegador-integrado`,
`apps/desktop/src/orbe/`): mismas clases, misma paleta negro-y-oro, mismo
halo. Se le sacó todo lo de visión/pantallas, que en una landing no aplica.

Arquitectura: `loader.js` (servido como `widget.js`) es un script mínimo
que solo crea un `<iframe allow="microphone">`; adentro corre `widget.html`
+ `app.js` + `app.css`, aislado del CSS/JS del sitio del cliente. Todo el
peso vive en `voz.quantumhive.com.ar`, así que actualizar el widget no
requiere que ningún cliente vuelva a pegar nada.

Se sirve como estático desde `livekit-quantumhive` (`/var/www/widget/`),
con un `handle` en el `Caddyfile` para `/widget.js`, `/widget.html` y
`/assets/*`.

Para desplegar una versión nueva: `npm run build` en `frontend/widget/`,
copiar `dist/*` + `loader.js` (como `widget.js`) a `/var/www/widget/` por
`scp`, y borrar los assets viejos (el nombre lleva hash, se acumulan).

### 3.5 Muestras de voz pregrabadas ← ✅ HECHO, LAS 18 (2026-08-10)

**Era lo que más plata estaba sangrando.** Cada vez que un visitante tocaba
un nombre para escuchar una voz, se reconectaba la sesión entera y se pagaba
una síntesis. Con 10 voces por motor, un curioso quemaba 10 saludos en 30
segundos. Y el spec ya dice que **el TTS es el 86% del costo variable**
(§9): el cacheo no es una optimización, es la estrategia central.

**Terminado. Las 18 grabadas, versionadas y normalizadas** a −16 LUFS, entre
3,5 y 4,9 segundos, ~25 KB cada una. Sin normalizar salían con hasta 15 dB de
diferencia entre sí y la más baja parecía peor voz cuando solo sonaba menos.

**Desplegado el 2026-08-10.** Las 18 responden 200 en
`voz.quantumhive.com.ar/assets/muestras/`.

**Pendiente: reescribir los saludos.** Hoy dicen *"Hola, soy Mateo, de
QuantumHive. ¿En qué te puedo ayudar?"*, y ese cierre no es la actitud de
QuantumHive — es el de cualquier soporte. Tienen que apuntar a lo que
QuantumHive hace de verdad, y variar entre voces en vez de ser todos iguales:

> *"Hola, soy Mateo, de QuantumHive. ¿Estás listo para darle vida a tu negocio?"*
> *"¿Te gusta esta voz para que atienda tu negocio?"*
> *"Soy Delfi, de QuantumHive. Me encantaría atender a tus clientes."*

Se cambia la constante `TEXTO` en `scripts/generar_muestras.py` y se regenera
con `--forzar`. Ojo que eso son 18 síntesis nuevas, 10 de ellas sesiones
Realtime contra la suscripción con tope: hacerlo una vez, con los textos ya
decididos.

- [`scripts/generar_muestras.py`](../scripts/generar_muestras.py) — one-shot
  e idempotente. Lee el catálogo de `motores.py`, así que no hay una segunda
  lista que se pueda desincronizar. **No regenera lo que ya existe** salvo
  `--forzar`: cada muestra de OpenAI cuesta una sesión Realtime contra una
  suscripción con tope, y correr el script dos veces no puede costar dos veces.
- Texto: `Hola, soy {nombre}, de QuantumHive. ¿En qué te puedo ayudar?` —
  mismo molde que el saludo real de `Receptor.on_enter`, sin adjetivos con
  género para que sirva igual en las 18.
- MP3 mono 48 kbps (~25 KB cada una). MP3 y no Opus porque es lo único que
  reproduce todo iPhone, y el widget se usa sobre todo desde el celular.
- Viven en `frontend/widget/public/assets/muestras/`. Vite copia `public/`
  sin hashear el nombre, así que caen en `dist/assets/muestras/` y el
  `handle` de `/assets/*` del Caddyfile **ya las sirve: no hay que tocar la
  VM.**
- `GET /api/voces` ahora devuelve `muestra` por voz. La ruta la decide el
  backend, que ya es dueño del catálogo; el navegador no arma nombres de
  archivo por convención.
- En el widget, `elegirYProbarVoz` reproduce el pregrabado **si no hay sala**.
  Si ya estás conversando reconecta como antes, porque cambiar de voz en vivo
  exige sala nueva. Un solo `<audio>` reutilizado, si no cinco toques rápidos
  superponen cinco saludos.

**Decisión que cambió respecto del plan anterior:** las 10 de OpenAI salen
todas por el deployment `gpt-realtime-mini`, que ya existe y está verificado
en producción — no por `gpt-4o-mini-tts`. Ese modelo no tiene `marin` ni
`cedar` y habría hecho falta crear un deployment nuevo en el portal. Un solo
camino en vez de dos, y cero infraestructura nueva.

**Para las 10 que faltan hace falta arreglar la clave de Azure** (§6). Con
eso: `uv run python scripts/generar_muestras.py`, escucharlas, commitear. El
script saltea lo que ya está, así que correrlo de nuevo solo graba OpenAI.

> **NO DESPLEGAR EL WIDGET HASTA QUE ESTÉN LAS 18.** Faltando las de OpenAI,
> el nivel 3 muestra los chips igual y tocarlos da 404 y avisa que no se pudo
> reproducir, y a propósito **no** cae de vuelta a conectar — sería resucitar
> en silencio el costo que vinimos a matar. O sea que desplegar ahora deja el
> selector del nivel 3 peor que antes. El nivel 2 ya está completo.
> `test_muestras.py` verifica por motor: exige las 8 de Gemini y saltea
> OpenAI hasta que aparezca la primera.

Después de esto vienen las capas 2 y 3 (respuestas frecuentes cacheadas y
sistema híbrido), que necesitan que los tenants existan primero — o sea,
después de 3.6.

### 3.6 Fases 5-8 — Supabase y multi-tenant

Plan completo y reconciliado con el código de hoy:
[`docs/superpowers/plans/2026-08-09-motor-voz-fases-5-8.md`](superpowers/plans/2026-08-09-motor-voz-fases-5-8.md).
**Las 10 tareas están implementadas y DESPLEGADAS** (2026-08-10). Resultado
completo en [`docs/resultados/fases5-8-multitenant.md`](resultados/fases5-8-multitenant.md).

Verificado en producción después del deploy: la sala sale con el formato nuevo
(`demo-quantumhive-pipeline--…`), el worker se registró en LiveKit, y **pedir
otro tenant por el cuerpo con un `curl` devuelve `quantumhive`** — el candado
del dominio funciona en vivo.

Supabase `bcexirhurfigrehfarol`, migración aplicada, dos tenants cargados
(`quantumhive` y `demo_capilar`) con sus servicios y sus voces.

**Del gate de cinco puntos, cuatro están verificados. Falta el de oído:**

| # | Punto | |
|---|---|---|
| 1 | Dos tenants con servicios y voz propios | ✅ |
| 2 | Test de aislamiento contra Supabase real | ✅ 2 en verde |
| 3 | Cada tenant responde solo con sus servicios | ✅ |
| 4 | **Cada tenant habla con su propia voz** | ⚠️ **falta escucharlo** |
| 5 | `brain/` sigue sin importar `livekit` | ✅ |

**El punto 4 depende de vos**, y hay una trampa: el `voice_id` de
`demo_capilar` es el placeholder que traía el plan. Que sea distinto del de
QuantumHive **no** prueba que sea una voz real de Fish — si no existe, el
motor cae a la voz por defecto y los dos van a sonar igual. Elegir uno real
es el pendiente de §6.

Lo que quedó blindado: `test_un_solo_cliente_supabase.py` recorre
`src/motor_voz` entero con AST y falla si aparece `create_client` o
`acreate_client` fuera de `brain/tenants/repositorio.py`. El motor usa la
`SERVICE_ROLE_KEY`, que saltea RLS por diseño, así que RLS no es la defensa
real — la defensa es que toda query pase por ese archivo. Eso además hace
barato mover `brain/` a su repo propio (ver §4).

Para escucharlo: [`docs/procesos/probar-un-tenant-a-oido.md`](procesos/probar-un-tenant-a-oido.md).
**Tiene que ser en el nivel 1** — Gemini y OpenAI hablan con voces de su
catálogo, no con la clonada del negocio, así que en los niveles 2 y 3 los dos
tenants suenan igual y parece que el aislamiento está roto.

**El tenant sale del dominio, no del navegador** (cerrado el 2026-08-10).
Antes `POST /api/token` aceptaba el `tenant` en el cuerpo del pedido, de quien
sea: con un `curl` y el slug de un negocio te llevabas su agente real, con su
prompt, sus servicios y su voz clonada.

Ahora sale de la cabecera `Origin`, que la pone el navegador y el código de
una página no puede cambiar. La tabla `tenant_dominios` dice qué dominio es de
quién. Fuera de producción el cuerpo se sigue honrando, que es como se prueba
el aislamiento a oído en local.

> **No es una frontera criptográfica.** Un cliente que no sea un navegador
> puede mandar el `Origin` que quiera. Corta el caso real —que una página se
> lleve el agente de otro negocio— y para el resto están los límites por IP.
> La protección fuerte necesita un secreto por tenant, y eso va cuando exista
> el alta de clientes.

---

### 3.7 Fase 9 — tools y registries ✅ HECHA (2026-08-11)

Plan: [`2026-08-11-motor-voz-fase-9.md`](superpowers/plans/2026-08-11-motor-voz-fase-9.md).
Resultado: [`fase9-tools.md`](resultados/fase9-tools.md).
Las 6 tasks, migración `0006` aplicada. La suite completa hoy tiene **286 tests
en verde** más 8 controles de integración.

El agente pasó de solo saber cosas a poder hacerlas:

```
publico   get_services, get_business_info, capture_lead, transfer_to_human
interno   las de arriba + get_mis_leads, get_mis_metricas, get_mis_conversaciones
```

**Regla dura, decidida el 2026-08-11: nadie crea negocios ni agentes
hablando.** Ni el visitante ni el dueño en su modo interno. Dar de alta es una
operación de la fábrica detrás de login. Esto **contradice el §6 del spec**,
que le daba `crear_negocio` al registry del receptor — **hay que actualizar el
spec**. Hay un test (`TestNadieCreaNegociosHablando`) que se rompe si alguien
agrega una tool que cree: no se arregla el test, se discute.

Tres cosas que quedaron blindadas:

- **El registry es un mapa explícito de nombre a función**, no un `getattr`
  sobre el módulo. Con `getattr`, cualquier función que alguien agregue queda
  expuesta sin que nadie lo decida.
- **`registry_de` lista lo que abre, no lo que cierra.** Solo el string exacto
  `interno` abre lo interno; vacío, con mayúsculas o inventado cae en público.
  Es lo que decide si alguien ve los leads de un negocio.
- **Ninguna tool ve el tenant ni la sala.** Se atan y se sacan de la firma
  antes de entregársela al modelo, que si no le pasaría el de otro negocio.

**Verificado contra la base real:** un lead de la barbería **no** lo ve
QuantumHive, desde el modo público no se alcanza ninguna tool interna, y
ningún modo alcanza `crear_negocio`.

**Falta la verificación a oído**: que el agente use las tools cuando
corresponde y no invente. Lo de arriba prueba el aislamiento por código.

---

### 3.8 Autenticación 🟡 CÓDIGO Y BASE LISTOS (2026-08-13)

Resultado: [`docs/resultados/autenticacion-y-base-multicanal.md`](resultados/autenticacion-y-base-multicanal.md).

La migración `20260813214636_autenticacion_panel.sql` está aplicada. Supabase
Auth valida el JWT y `tenant_usuarios` exige que el usuario pertenezca al
tenant resuelto por el dominio. Solo entonces la API firma `modo=interno`.
Sin sesión, token roto o usuario de otro negocio, firma `modo=publico`.

El worker ya quitó la constante global: lee el modo de la metadata firmada y
también falla cerrado. El cuerpo del pedido nunca puede elegirlo.

**Gate: el dueño ya existe (2026-08-15).** `ceo@quantumhive.com.ar`
(`f39393b7-e673-44cd-a045-ba3d73b21981`) está en `tenant_usuarios` como dueño de
QuantumHive, con email confirmado e identidad de email con contraseña.
`frontend/panel/.env.local` está armado con la clave publishable, verificada
contra Supabase real.

**Gate CERRADO el 2026-08-15**, probado contra la base real con una sesión
emitida por la API de admin (enlace de un solo uso, sin tocar la contraseña):

| Caso | |
|---|---|
| Sin sesión → `/api/panel/tenants` | ✅ 401 |
| Token basura | ✅ 401 |
| Sesión propia → `/api/panel/tenants` | ✅ 200, devuelve solo `quantumhive` |
| Conocimiento propio | ✅ 200 |
| **Conocimiento de `demo_capilar`** | ✅ **403** |

Y la PWA levantada en local con esa sesión muestra el selector con **un solo
negocio**, métricas en "esperando datos reales" y los cuatro canales con su
estado. El aislamiento se ve también en la interfaz.

> **Sin resolver:** el service worker no se registra en el panel de preview
> (`Failed to register a ServiceWorker`). `/panel/sw.js` se sirve con HTTP 200
> y el `manifest.webmanifest` también, y ese preview reescribe las URLs, así
> que no se pudo distinguir bug real de limitación del entorno. **Verificar en
> un navegador de verdad antes de prometer que la PWA se instala.**

> **Trampa al diagnosticar usuarios:** `auth.admin.list_users()` devuelve
> `identities: []` para todos, siempre. No significa que no tengan contraseña.
> Para saberlo hay que pedir el usuario de a uno con `get_user_by_id`. Costó
> mandar a Sergio a recrear un usuario que ya estaba bien.

También quedó fijado el contrato de Web, WhatsApp, Instagram y Facebook en
`brain/mensajes.py`. Los adaptadores reales todavía no están conectados; el
plan está en `docs/superpowers/plans/2026-08-13-arquitectura-multicanal.md`.

Después siguen sesiones/mensajes, memoria, límites de gasto/kill-switch y el
primer adaptador de texto (WhatsApp).

### 3.9 Persistencia multicanal ✅ BASE APLICADA (2026-08-13)

Resultado: [`docs/resultados/persistencia-multicanal.md`](resultados/persistencia-multicanal.md).

Ya existen en Supabase `tenant_canales`, `conversaciones`, `mensajes`,
`eventos_inbox` y `eventos_outbox`. El ingreso de un mensaje es atómico e
idempotente: si Meta reintenta un webhook no genera otra respuesta. Las claves
foráneas compuestas impiden cruzar tenant, canal y conversación incluso si el
backend se equivoca usando `service_role`.

Probado contra la base real con QuantumHive y `demo_capilar`: dos controles
nuevos en verde, incluyendo reintento y cruce deliberado de tenant.

El panel solicitado queda especificado en
[`docs/superpowers/plans/2026-08-13-panel-de-control.md`](superpowers/plans/2026-08-13-panel-de-control.md):
Métricas, Memorias, Chat con mi agente y Entrenamiento versionado.

**Siguiente:** procesador de inbox/outbox y adaptador WhatsApp de texto. En
paralelo, conocimiento versionado para horarios, precios, servicios y FAQ.

### 3.10 Conocimiento versionado ✅ APLICADO (2026-08-13)

Resultado: [`docs/resultados/conocimiento-versionado.md`](resultados/conocimiento-versionado.md).

Horarios, precios, servicios, políticas, FAQ y tono ya pueden existir como
piezas versionadas. Un borrador no modifica al agente. Publicar cambia la
versión activa; restaurar vuelve a una histórica sin borrar auditoría.

El repositorio carga únicamente versiones publicadas y `construir_contexto()`
las incorpora al mismo agente para Web, WhatsApp, Instagram y Facebook.

Probado contra Supabase real: borrador, publicación, segunda versión, rollback,
aislamiento de lectura y rechazo de publicación cruzada.

La API autenticada para listar, editar, publicar y restaurar ya está terminada
en el bloque siguiente. La vista previa quedará en la PWA usando borradores.

### 3.11 API autenticada del panel ✅ LISTA (2026-08-13)

Resultado: [`docs/resultados/api-autenticada-panel.md`](resultados/api-autenticada-panel.md).

Ya están disponibles el listado de negocios del usuario, el historial de
conocimiento, la creación de borradores y la publicación/rollback. Cada ruta
valida JWT y membresía exacta en `tenant_usuarios`; cualquier `tenant_id`
enviado por el navegador se ignora.

Verificado con **286 tests locales en verde**, incluidos `401`, `403`, cruce
deliberado de tenant, borradores inválidos y publicación segura.

**Siguiente paso:** base visual responsive de la PWA y conexión del login real
cuando se dé de alta el dueño de `tenant_001` QuantumHive.

### 3.12 Base PWA del panel ✅ LISTA (2026-08-13)

Resultado: [`docs/resultados/pwa-panel-base.md`](resultados/pwa-panel-base.md).

`frontend/panel` ya contiene una sola aplicación instalable para Windows,
macOS, Android y iPhone. Su navegación fue simplificada a Inicio, Enseñar, Mi
negocio y Conexiones. Enseñar es una charla con el agente, incluye modo de
prueba como cliente y separa Probar cambios de Aplicar cambios.

Mi negocio tiene una planilla para productos, servicios y precios. Conexiones
es un catálogo buscable y ampliable de integraciones/MCP, con categorías,
estado conectado, calendarios, ventas, mensajería, productividad, CRM y MCP
personalizado sujeto a revisión. Cada conexión se habilita por tenant.

Entrenamiento ya consume la API para guardar borradores y publicar versiones.
Compila en producción y fue verificada visualmente en escritorio, 390×844 y
360×560, sin errores de navegador ni desborde horizontal.

**Siguiente:** alta del dueño real de QuantumHive + login E2E; después, chat
interno sobre el mismo agente.

**Ojo con el estado real del usuario dueño** (verificado el 2026-08-15 contra la
base): `ceo@quantumhive.com.ar` **ya existe** y ya está en `tenant_usuarios`
como dueño de QuantumHive. Pero se creó vacío: `identities: []`, o sea **sin
contraseña**, y con el email sin confirmar contra un proyecto que tiene
`mailer_autoconfirm: false`. Así no se puede entrar. Se arregla borrándolo y
recreándolo desde el dashboard con contraseña y **Auto Confirm User** tildado, y
volviendo a vincular el UUID nuevo — al borrarlo, la fila de `tenant_usuarios`
se va en cascada.

### 3.13 Canal WhatsApp 🟡 CUATRO TASKS HECHAS, EL CIRCUITO NO CIERRA (2026-08-15)

Plan: [`2026-08-15-canal-whatsapp.md`](superpowers/plans/2026-08-15-canal-whatsapp.md).
**345 tests en verde.**

| Task | Estado |
|---|---|
| 1 · Parser del webhook de Meta | ✅ `channels/whatsapp/payload.py` |
| 2 · Firma `X-Hub-Signature-256` | ✅ `channels/whatsapp/firma.py` |
| 3 · Endpoints `GET`/`POST /webhooks/whatsapp` | ✅ en `api/servidor.py` |
| 4 · Cerebro de texto | ✅ `brain/conversacion.py` |
| 5 · Procesador de inbox | ✅ `channels/procesador.py`, cableado al repositorio |
| 6 · Envío por la Cloud API | ✅ `channels/whatsapp/cliente.py` + `channels/enviador.py` |
| — · Worker de las dos colas | ✅ `channels/worker.py` |
| 7 · Handoff a humano · 7bis · Embedded Signup | ❌ |
| 8 · Límites y kill-switch | ❌ |

**Del lado del código el circuito cierra**: entra el webhook, contesta el
agente, sale por WhatsApp. Lo que falta para que un "hola" real tenga
respuesta ya no es código nuestro:

1. **Aplicar las dos migraciones del procesador** —
   `20260815193000_procesador_inbox_outbox.sql` y
   `20260815214500_procesador_outbox.sql`. Escritas y commiteadas, **no
   aplicadas**: mismo bloqueo de §6, el MCP de Supabase no ve este proyecto y
   el CLI pide la contraseña de forma interactiva.
2. **Credenciales de Meta**, y una fila en `tenant_canales` con el
   `phone_number_id` como `cuenta_externa_id` y un `secreto_ref`.
3. **El token en el `.env` del worker**, como `SECRETO_<REF>` — ver
   `channels/secretos.py`. En la base va la referencia, nunca el token.
4. **Deploy**: el webhook tiene que ser HTTPS público, y el worker necesita su
   propio servicio de systemd (`python -m motor_voz.channels.worker`).

**Estado en Meta al 2026-08-15:** portfolio comercial `QuantumHive` creado
(`business_id 1079094061364956`, sin duplicados, **no verificado** — abandonado
el 2026-08-31, reemplazado por `1339027384106629`, ya verificado). La app
`quantumhive` quedó **sin confirmar**: se completó el asistente pero Facebook
tiró un checkpoint de "confirmá que sos una persona real" al automatizar el
navegador. **No manejar la cuenta de Meta por automatización** — Meta lo
detecta, y esa cuenta va a pedir verificación de negocio para Tech Provider.

**El cerebro de texto es la pieza que más se va a reusar.** `responder()` recibe
el tenant como parámetro: sumar un cliente es una fila en `tenant_canales`, cero
líneas de código. Instagram y Facebook cambian parser y cliente de envío, no el
cerebro.

**Y la corrección que costó una vuelta:** *ningún negocio cambia su número.* Hay
dos onboardings. El directo saca el número de la app de WhatsApp Business y
pierde su historial. **Coexistence** lo deja en los dos lados sincronizado —
pero exige ser **Tech Provider de Meta** y **Embedded Signup con session
logging**. Para clientes va coexistence, sí o sí. Está desarrollado en el plan.

---

## 4. Decisiones tomadas — no reabrir sin motivo

| Decisión | Por qué |
|---|---|
| LiveKit self-hosteado, no Cloud | Apache-2.0, sin fee por minuto, corre en VM gratis |
| No migrar a Cloudflare Realtime | Perderíamos LiveKit Agents entero. El cruce de costos está en ~500 concurrentes |
| `brain/` no importa `livekit` | Sin eso, WhatsApp y el asistente de escritorio no reusan el cerebro |
| Prompt en 3 capas, no duplicado | Dos prompts copiados derivan |
| Normalizar texto en código | Pedírselo al LLM falla, y el error sale al aire |
| API en la VM, no Cloud Run | Evita aflojar la política de organización, sin CORS, gratis |
| Cloudflare para Web Factory, no para esto | Pages + for SaaS resuelven dominios de clientes. Otro producto |
| ~~`brain/` sale a un repo propio~~ **revertida el 2026-08-10** | Se había decidido sacarlo pensando que ahí iban a vivir *todos* los agentes de QuantumHive. No es así: acá viven los **agentes conversacionales de negocio** —los de clientes y el nuestro—, y eso es exactamente lo que este repo es. Los scrapers y los agentes de desarrollo no tienen voz ni servicios ni rubro: van en Quantum Core, que es el orquestador. El spec ya lo decía en su §1 ("no es un orquestador ni un reemplazo de Quantum Core"). **El repo queda entero.** |
| Un agente por cliente, con dos modos (2026-08-10) | Modo público para atender visitantes y modo interno para métricas, en el panel de control del cliente. Un solo agente y un solo cerebro por negocio; lo que cambia son las herramientas y el contexto. Es lo que la Fase 9 llama `registry_publico` y `registry_receptor` |

---

## 5. Trampas que ya nos costaron horas

Cada una tiene un test que la cubre. **No las repitas.**

| Trampa | Síntoma |
|---|---|
| `groq.STT` viene con `language="en"` | Transcribe español como inglés, sin error |
| `groq.LLM` viene con `llama-3.3`, no gpt-oss | Se paga otro modelo sin darse cuenta |
| Vertex nombra los modelos distinto que `ai.google.dev` | Gemini Live no conecta |
| El TTS lee literal | `24/7` suena "veinticuatro séptimo" |
| Decirle al LLM "no uses símbolos" | Deja de usar `¡!` y la voz sale plana |
| Pedir brevedad sin pedir iniciativa | Contesta una frase y deja colgado al visitante |
| El proxy naranja de Cloudflare | No pasa UDP: todo parece andar y no se escucha nada |
| `scripts/token.py` | Le hacía sombra al módulo `token` de la stdlib |
| El plugin de Fish fuera del worker | Falla sin `utils.http_context.open()` |
| Un token de R2 no escribe DNS | Da "Authentication error" sin aclarar por qué |
| Importar un plugin adentro de la función | `RuntimeError: Plugins must be registered on the main thread`. Los imports de `google`/`openai` van a nivel de módulo en `motores.py` |
| `min_words: 0`, el default de livekit-agents | Alcanza UNA palabra para interrumpir. Whisper alucina una palabra con ruido → el agente se calla y después le contesta a la nada |
| Copiar el `.env` local a producción | Tiene las credenciales de `livekit-server --dev` (`devkey`/`secret`, 6 bytes). El agente arranca bien y LiveKit lo rechaza con 401 recién al registrarse |
| `gcloud run deploy --source .` sin comparar | La carpeta local estaba atrasada y **pisó la landing viva**, borrando la pestaña "Webs inteligentes". Comparar siempre contra el zip de fuente del deploy anterior en GCS |
| `hidden` contra un `display` de autor | `.orbe__voces` es `display: grid` y le gana al atributo: el menú no se ocultaba |
| Animar un `conic-gradient` con `transform: rotate()` | Gira la caja entera, no el reflejo. Se anima el ángulo con `@property` |
| `gpt-realtime-2.1-mini` en suscripción de prueba | Cuota 0 → `InsufficientQuota`. El único con cuota es `gpt-realtime-mini` |
| Un `<audio>` nuevo por cada preescucha | Cinco toques rápidos superponen cinco saludos. Se reutiliza uno solo y se corta el anterior |
| Caer a `conectar()` si la muestra no carga | Resucita en silencio el costo que 3.5 vino a matar. Si falla, se elige la voz y se avisa, nada más |
| Usar el endpoint de administración de Azure con la key de datos | Da 401 y parece clave inválida. Para saber si un deployment existe, llamarlo directo |
| Suponer que el TTS de Gemini vive donde el modelo Live | `GCP_LOCATION` es `us-east4` y ahí el TTS no está: 404 "model was not found", que se lee como nombre mal escrito y es la región. La única que responde es `us-central1`, y el modelo es `gemini-2.5-flash-preview-tts`, no el default del plugin |
| Pedir las 8 voces de Gemini de corrido | `RESOURCE_EXHAUSTED` en la séptima. El modelo preview tiene cuota corta: dos segundos entre voces alcanzan |
| Suponer que el MCP de Supabase ve todos los proyectos | Su token está scopeado por organización. `bcexirhurfigrehfarol` no aparece: lista otros cuatro y da "access denied" sin decir que es de scope |
| **Aplicar un snippet de un plan sin leer el archivo real** | Un plan de un día atrás ya puede estar atrasado. Los de las Fases 5-8 borraban, entre los cuatro, la calibración del VAD, la ruta `/api/voces`, la config de interrupción y la resolución de voz. Leer el archivo primero, siempre |
| **Una variable de entorno de usuario de Windows le gana al `.env`** | `python-dotenv` no pisa lo que ya existe. `AZURE_OPENAI_API_KEY` estaba definida a nivel usuario con la `key1` muerta, así que el `.env` no se leía nunca y todo daba 401 con el endpoint y el deployment correctos. Costó media tarde. Ante un 401 que no cierra: `[Environment]::GetEnvironmentVariable('X','User')` antes que cualquier otra cosa |
| Azure tiene dos claves y una puede estar muerta | `key1` daba 401 y `key2` conectaba. El portal las muestra iguales y no dice cuál está viva. Probar las dos antes de dar la credencial por mala |
| Publicar muestras de voz sin normalizar | Salieron con 15 dB de diferencia entre sí (`alloy` −18,6 contra `sage` −33,5). En un selector que existe para comparar, la más baja se juzga peor voz. `loudnorm=I=-16` y quedan todas parejas |
| Comparar el entorno contra una sola palabra | `if entorno == "produccion"` con un `.env` que dice `development` y una VM que dice `production` deja el candado abierto sin que se note. Se lista lo que **afloja** (`ENTORNOS_DE_DESARROLLO`), no lo que aprieta: así un valor en otro idioma, mal escrito o vacío falla cerrado |
| Desplegar sin instalar las dependencias nuevas | `git pull` trae el código pero no el paquete. En la VM no hay `uv`: va `.venv/bin/pip install -e .` en el medio. Cuando entró `supabase`, sin eso el agente arrancaba y moría al importar |
| Una variable que Supabase renombró | La VM tenía `SUPABASE_SECRET_KEY` y el código pedía `SUPABASE_SERVICE_ROLE_KEY`. No estaba entre las obligatorias, así que el servicio levantaba sin quejarse y devolvía 503 en cada token. Ahora `crear_app` no arranca sin credenciales: mejor caído y ruidoso que arriba y mudo |

---

## 6. Lo que Sergio tiene pendiente

- ~~Actualizar el §6 del spec~~ — **hecho el 2026-08-15.** Decía que el agente
  receptor podía `crear_negocio`; ahora describe los registries reales y deja
  la corrección anotada, para que nadie lo lea y reabra el agujero
- **Aplicar la migración de la Task 2** — desbloquea toda la Fase 6 en
  adelante. Dos caminos: correr `supabase link --project-ref bcexirhurfigrehfarol`
  y después `supabase db push` (el link pide la contraseña de forma
  interactiva, no queda en el historial), **o** reautenticar el MCP de
  Supabase eligiendo la organización dueña del proyecto, y que lo aplique el
  agente
- **Borrar la variable de usuario `AZURE_OPENAI_API_KEY` de Windows** —
  tiene la `key1` de Azure, que está muerta, y **le gana al `.env`** porque
  `python-dotenv` no pisa variables que ya existen. Mientras esté, cualquier
  cosa que corras en local va a dar 401 aunque el `.env` tenga la clave
  buena. La viva es `key2`. Se borra con
  `[Environment]::SetEnvironmentVariable('AZURE_OPENAI_API_KEY', $null, 'User')`
  y se reinicia la terminal
- **Rotar la contraseña de Supabase** — quedó expuesta en el chat
- ~~**Verificación de la empresa en Meta**~~ — **hecha el 2026-08-31** sobre el
  portfolio nuevo `1339027384106629`. Era el gate más lento
- **Pedir acceso avanzado** a `whatsapp_business_management` y
  `whatsapp_business_messaging` en la app. Recién ahora se puede: ese pedido
  exigía la empresa verificada
- **Terminar el alta como Tech Provider de Meta + App Review.** Es lo único que
  falta para habilitar coexistence a **clientes**, o sea que un cliente conserve
  su número **y** su app de WhatsApp Business. Sin esto, Jaz no se puede conectar
  sin perder su app. **No bloquea el número propio de QuantumHive**, que ya se
  puede conectar con la app en modo desarrollo
- ~~Recrear el usuario `ceo@quantumhive.com.ar`~~ — **hecho el 2026-08-15.**
  Creado, confirmado, con contraseña y vinculado al tenant. Falta entrar una
  vez al panel para cerrar el gate E2E
- **Elegir proveedor de SMTP** para los mails de invitación del panel. El de
  Supabase por defecto solo le escribe a miembros del equipo y manda 2 por hora:
  no sirve ni para la primera clienta
- **Elegir un `voice_id` real de Fish para `demo_capilar`**, para poder
  validar a oído que cada tenant habla con su propia voz (gate de la Fase 8)
- **Ajustar a oído la sensibilidad del micrófono** si todavía corta rápido
  o tarda mucho: `VAD_SILENCIO_MS` (hoy 900), `VAD_UMBRAL` (hoy 0.6) y
  `AGENTE_PALABRAS_INTERRUPCION` (hoy 2). Se cambian en el `.env` de la VM
  y se reinicia el agente, sin tocar código

---

## 7. Reglas de trabajo

Del `CLAUDE.md` de la bóveda y del contexto maestro:

- **El grafo primero, siempre.** Ver [`CLAUDE.md`](../CLAUDE.md) en la raíz:
  `graphify query` antes que grep, comandos que devuelvan lo mínimo, y
  subagentes con modelo barato para lo mecánico. Son reglas de costo, no
  de estilo: el plan semanal se va en dos días si no se respetan.
- **Un paso a la vez.** Si el anterior no está estable, no se avanza.
- **`git push` antes de dar algo por terminado.**
- **Verificá que un repo o API exista** —la URL exacta, el último commit—
  antes de integrarlo. Nunca de memoria.
- **Preguntá antes de cualquier acción destructiva.**
- **El repositorio es PÚBLICO.** Ninguna clave. Ninguna muestra de voz
  **clonada ni de persona real** — VOZ-003 y todo lo que tenga registro de
  consentimiento se queda afuera. Los saludos pregrabados de 3.5 sí van al
  repo: son voces stock de Google y OpenAI que ya suenan públicamente en el
  widget, no hay nada que filtrar y así el deploy no depende de tener claves.
- **Nunca `--dangerously-skip-permissions`.**
- **Todo lo visual, responsive.** Probar en 360×560, 360×640 y 390×844.
- **No tomar capturas ni levantar servidores durante la implementación.**
  El flujo es: cambio → tests → commit → push → Sergio prueba.

---

## 8. Cómo levantar todo en local

```bash
cd "C:\Users\sergio\Desktop\FABRICA-DE-AGENTES"; .\arrancar.ps1
```

Abre las cuatro ventanas, genera el token y abre el navegador. Los errores
salen en la ventana **AGENTE**.

## 9. Dónde está cada cosa

| Necesitás | Mirá |
|---|---|
| Cómo trabajar en el repo | `AGENTS.md` |
| El diseño completo | `docs/superpowers/specs/2026-08-08-motor-voz-design.md` |
| El plan de implementación | `docs/superpowers/plans/2026-08-08-motor-voz-fases-0-4.md` |
| Escribir la personalidad de un agente | `docs/guia-de-prompts.md` |
| Instalar el agente en un cliente | `docs/instalar-el-agente-en-una-landing.md` |
| Clonar una voz | `docs/voces/registro-de-consentimiento.md` |
| Buscar cualquier cosa en el código | `graphify query "..."` |

---

## 10. CEO departamental de Fábrica de Agentes — 2026-08-20

- El CEO de este checkout ahora se identifica como `fabrica-de-agentes`; ya
  no ocupa la identidad `motor-de-voz`.
- Ruta de descripción:
  `GET /v1/departamentos/fabrica-de-agentes/descripcion`.
- Consultas y acciones conservan `POST /v1/consultas` y
  `POST /v1/acciones`.
- QuantumCore incorpora un adaptador específico para este contrato. El
  adaptador genérico de OpenCode no es compatible con el cuerpo HTTP de este
  CEO.
- Verificación local real: registro productivo `saludable`, descripción y
  consulta `arquitectura` de solo lectura con correlación; costo USD 0 y cero
  acciones.
- Suite después del cambio: `427 passed, 15 deselected`.
- No se guardó ningún `QUANTUMCORE_TOKEN`: la prueba usó uno efímero y lo
  descartó al cerrar la API local.
- No se hizo commit, push ni despliegue. Los workers siguen declarados pero no
  conectados; una acción válida continúa fallando cerrada con
  `worker_no_conectado`.
- Contrato vigente: [`ceo-fabrica-de-agentes.md`](ceo-fabrica-de-agentes.md).

---

## 11. Sin agregadores: la capa de conexiones es nuestra — 2026-08-31

Se evaluó **Zernio** (ex *Late*): un agregador que ofrece "una API para todas las
conversaciones" —WhatsApp, Instagram, Facebook, Telegram, X, Reddit, Bluesky—
con Embedded Signup y Coexistencia ya resueltos, webhooks firmados con HMAC,
reintentos y SDK de Python.

**Descartado.** Los motivos, en orden de peso:

1. **La custodia del token del cliente.** El §8 del `MAPA` ya lo marca como el
   dato más sensible del sistema: un token de WhatsApp deja mandar mensajes en
   nombre del cliente. Con un agregador ese acceso vive afuera. Si el agregador
   cierra o cambia de precio, **se caen todas las conexiones de todos los
   clientes a la vez**, y no hay nada que podamos hacer.
2. **El motivo principal se evaporó.** Se lo evaluó mientras la verificación de
   Meta estaba trabada y parecía lenta. Se aprobó el 2026-08-31.
3. **Es una empresa joven** —fundada en 2025, ocho personas, autofinanciada, ya
   renombrada de Late a Zernio— y la evidencia a favor es débil: Reddit con
   promoción de proveedores y un Trustpilot fusionado tras el rebrand.

**La decisión NO es "no tener esa capa": es tenerla nosotros.** Ya está casi
entera —parser, firma, cerebro, colas, envío, worker, topes y Embedded Signup—
y `brain/` es agnóstico al canal por diseño.

**Sigue valiendo la reversibilidad, y es barata:** `enviar_texto` no tiene
dependientes y se engancha en una sola línea (`channels/enviador.py:52`). Si
algún día Meta rechaza el App Review y no hay camino, un agregador entra ahí
como un adaptador más, sin tocar cerebro, tenants, memoria, panel ni colas. Eso
es plan B, no plan A.

> **Lo que NO se decidió todavía:** si esta capa se ofrece además como producto
> aparte, a terceros. Hoy es de uso interno para nuestros clientes. Venderla es
> otro negocio, con otro soporte y otra responsabilidad sobre tokens ajenos, y
> no se abre hasta que el canal propio esté facturando.

---

## 12. Instagram público con Apify — desplegado 2026-09-02

- El lector público de Instagram quedó implementado en
  `INTELIGENCIA COMERCIAL SCRAP`, rama
  `codex/apify-instagram-perfilador`, commit
  `483478ece10e2652a2e2c788ae44ac1fe8e89801`, ya pusheado.
- Usa el actor oficial `apify/instagram-scraper`, con el token únicamente en
  Secret Manager (`perfilador-apify-token`). Si Apify falla, conserva el lector
  público anterior como degradación controlada.
- Suite completa del repo de Inteligencia Comercial: **41 passed**.
- Cloud Build real:
  `4e6465ab-9960-4ae4-82d7-f2ef469f7c65`, estado `SUCCESS`.
- Imagen desplegada por digest:
  `sha256:86c83847d8a7fbde6b3f9f4b4041c14eaf7820383b8fce4415ccb28bee5e5fe9`.
- Revisión viva: `perfilador-clientes-00008-pox`, **100 % del tráfico** del
  servicio `perfilador-clientes` en `us-east1`.
- Gate E2E desde la URL pública aprobado con `@traderboss420`: salud `ok`,
  `instagram_apify_configurado=true`, bio real presente, **498 seguidores** y
  foto de perfil real; `logo_generico=false`.
- Se comparó OpenAPI antes de promover: las siete rutas de producción siguen
  presentes y no apareció ninguna pérdida de contrato.
- La primera versión del secreto contenía el token duplicado, devolvía 401 y
  quedó **DISABLED**. Producción usa explícitamente la versión `2`.
- **Pendiente de seguridad:** rotar el token en Apify porque fue pegado en el
  chat, crear una nueva versión del secreto y desplegar otra revisión apuntando
  a esa versión. Hasta entonces funciona, pero la credencial debe considerarse
  expuesta.

---

## 13. Perfilador: investigaciones consecutivas aisladas — 2026-09-06

- Una investigación nueva reemplaza la identidad, los servicios y la marca de
  la investigación anterior; ya no mezcla datos de dos negocios en el mismo
  borrador local.
- El botón **Empezar otro negocio** pide confirmación y limpia únicamente el
  borrador, la investigación, el logo, los colores y las conversaciones de este
  navegador. El conocimiento que el dueño ya publicó para su tenant no se borra.
- Los logos genéricos de Instagram/Facebook se descartan y el visor diferencia
  fuentes encontradas, sin datos, fallidas y pendientes.
- Verificación local: **16/16** pruebas del frontend y suite completa de Python
  con **450 passed, 15 deselected**. El build de producción genera los assets
  bajo `/fabrica/`; la publicación se realiza desde el repositorio separado de
  la landing según `docs/procesos/desplegar-la-fabrica.md`.
