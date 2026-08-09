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

### 3.1 Poner la API y el agente en la VM ← ARRANCAR POR ACÁ

**Es lo único que separa el motor de estar en producción.** Hoy en la VM
solo corre LiveKit y Caddy; la API y el agente siguen únicamente en local.

Decisión ya tomada: **van en la VM, no en Cloud Run.** El servicio de Cloud
Run está desplegado pero devuelve 403 porque la política de organización
`iam.allowedPolicyMemberDomains` bloquea `allUsers`, y Sergio eligió no
aflojarla. Servir desde la VM además evita CORS —mismo origen que LiveKit—
y es gratis.

Pasos:

1. Clonar el repo en la VM (es público) en la rama `arquitectura/spec-motor-voz`
2. Crear el `.env` con las claves. Están en Secret Manager:
   `motor-voz-groq`, `motor-voz-fish`, `motor-voz-livekit-key`,
   `motor-voz-livekit-secret`
3. `LIVEKIT_URL=wss://voz.quantumhive.com.ar`
4. Dos servicios systemd con `Restart=always`:
   - `motor-voz-api` → `python -m motor_voz.api.servidor` en el puerto 8080
   - `motor-voz-agente` → `python -m motor_voz.voice.agente start`
5. Ampliar el `Caddyfile` para que rutee `/api/*` a `localhost:8080` y el
   resto a LiveKit en `localhost:7880`

**Atención con la memoria.** La VM tiene 969 MB y ya hay 2 GB de swap
configurados. LiveKit + Caddy usan ~390 MB. El agente carga el modelo VAD
de silero y puede pedir 300-400 MB. Va a entrar, pero **verificá `free -m`
después de levantar todo** — si el agente muere sin explicación, es OOM.

### 3.2 Probar el nivel 2 (Gemini) en vivo

**Nunca se ejecutó.** El modelo y la región ya están corregidos copiando lo
que usa Quantum Assistant, pero la conexión no se probó ni una vez.

Consume créditos de Google Cloud vía Vertex AI, no tarjeta. Si falla, el
error de Google nombra los modelos válidos y se corrige en una variable.

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
