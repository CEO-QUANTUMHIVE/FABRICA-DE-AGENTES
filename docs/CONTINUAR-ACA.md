# Brief de continuación — Motor de Voz

**Fecha:** 2026-08-09
**Rama:** `arquitectura/spec-motor-voz` en `CEO-QUANTUMHIVE/MOTOR-DE-VOZ-`
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
| Tests | ✅ **142 en verde** |

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

### 3.5 Muestras de voz pregrabadas ← ARRANCAR POR ACÁ

**Es lo que más plata está sangrando hoy.** Cada vez que un visitante toca
un nombre para escuchar una voz, se reconecta la sesión entera y se paga
una síntesis. Con 10 voces por motor, un curioso quema 10 saludos en 30
segundos. Y el spec ya dice que **el TTS es el 86% del costo variable**
(§9): el cacheo no es una optimización, es la estrategia central.

Plan: un saludo corto pregrabado por voz, generado una vez, servido como
estático. Tocar un nombre pasa a costar **cero** y suena al instante.

Ya está verificado lo técnico:

- **Gemini** — el plugin trae `GeminiTTS`
  (`livekit/plugins/google/beta/gemini_tts.py`) con exactamente nuestras
  8 voces. Sale directo.
- **OpenAI** — hay cuota para `gpt-4o-mini-tts` (límite 50) en la
  suscripción de prueba, pero ese modelo **no tiene `marin` ni `cedar`**,
  que son solo de Realtime. De las 10, 8 salen por TTS y esas 2 hay que
  generarlas una vez con una sesión Realtime. **No achicar el catálogo por
  una limitación de la herramienta de generación.**

Después de esto vienen las capas 2 y 3 (respuestas frecuentes cacheadas y
sistema híbrido), que necesitan que los tenants existan primero — o sea,
después de 3.6.

### 3.6 Fases 5-8 — Supabase y multi-tenant

Plan completo y reconciliado con el código de hoy:
[`docs/superpowers/plans/2026-08-09-motor-voz-fases-5-8.md`](superpowers/plans/2026-08-09-motor-voz-fases-5-8.md).
Son 10 tareas. **La Task 1 está hecha** (`Config` ya lee las credenciales
de Supabase, commit `219fadc`); quedan 9.

Proyecto de Supabase creado y verificado: `bcexirhurfigrehfarol`.
Credenciales en Secret Manager (`motor-voz-supabase-url`,
`motor-voz-supabase-service-role`) y en el `.env` local y de la VM.
**Ninguna tabla creada todavía** — eso es la Task 2.

El test de aislamiento entre tenants es **bloqueante**: no se entrega un
cliente sin que pase.

Ejecución elegida: subagent-driven (un subagente por tarea, revisión entre
tareas).

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

---

## 6. Lo que Sergio tiene pendiente

- **Rotar la contraseña de Supabase** — quedó expuesta en el chat
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
- **El repositorio es PÚBLICO.** Ninguna clave, ninguna muestra de voz.
- **Nunca `--dangerously-skip-permissions`.**
- **Todo lo visual, responsive.** Probar en 360×560, 360×640 y 390×844.
- **No tomar capturas ni levantar servidores durante la implementación.**
  El flujo es: cambio → tests → commit → push → Sergio prueba.

---

## 8. Cómo levantar todo en local

```bash
cd "C:\Users\sergio\Desktop\MOTOR-DE-VOZ"; .\arrancar.ps1
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
