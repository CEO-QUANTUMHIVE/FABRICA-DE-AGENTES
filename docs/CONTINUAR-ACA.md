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
| Grafo de conocimiento | ✅ 438 nodos, se regenera solo en cada commit |
| Tests | ✅ **122 en verde** |

### Configuración vigente

```
VOZ-003        63f9f124b940…       clonada del fundador, 6 clips graves
FISH_MODEL     s2.1-pro            pago, saldo USD 5,00
FISH_SPEED     1.25
FISH_TEMP      1.0
GCP_PROJECT    bubbly-stone-502214-u7
GEMINI_MODEL   gemini-live-2.5-flash-native-audio   (nombre de Vertex, NO el de ai.google.dev)
GCP_LOCATION   us-east4
```

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

### 3.3 Nivel 3 (OpenAI) — bloqueado

Falta que Sergio cree un recurso de **Azure OpenAI** con un deployment del
modelo realtime. Hasta entonces ese nivel falla con un mensaje claro
diciendo qué variable falta. El código está listo.

### 3.4 Servir el widget

El playbook promete este fragmento, que **todavía no existe**:

```html
<script src="https://voz.quantumhive.com.ar/widget.js" data-tenant="..." defer></script>
```

Hay que construir el frontend de `frontend/demo/` como un bundle embebible
y servirlo desde Caddy.

### 3.5 Fase 5 — Supabase y multi-tenant

Proyecto ya creado y verificado: `bcexirhurfigrehfarol`, responde 200 con la
clave secreta. **Ninguna tabla creada todavía.** El esquema está en el §11
del spec.

El test de aislamiento entre tenants es **bloqueante**: no se entrega un
cliente sin que pase.

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

---

## 6. Lo que Sergio tiene pendiente

- **Rotar la contraseña de Supabase** — quedó expuesta en el chat
- **Crear el recurso de Azure OpenAI** para desbloquear el nivel 3
- **Probar el agente local** con el prompt nuevo, que ya es activo

---

## 7. Reglas de trabajo

Del `CLAUDE.md` de la bóveda y del contexto maestro:

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
