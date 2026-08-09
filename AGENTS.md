# Para agentes que trabajen en este repo

Leé esto antes de abrir un solo archivo.

---

## 1. Consultá el grafo ANTES de releer el repo

Hay un grafo de conocimiento en `graphify-out/` (local, no versionado) que
se **regenera solo en cada commit**. Para "¿dónde está X?", "¿cómo se
conecta Y con Z?" o cualquier pregunta de arquitectura, preguntale al grafo
antes de abrir archivos sueltos.

```bash
graphify query "como se elige el motor segun el plan" --budget 800
graphify explain "opciones_gemini"
graphify path "AgentSession" "normalizar"
graphify affected "Config"          # qué se rompe si toco esto
```

Releer el repo entero es el último recurso, no el primero. Si
`graphify-out/` no existe, reconstruilo con `graphify update .`

---

## 2. Qué es esto

El motor de voz de QuantumHive. Un visitante habla por el navegador y un
agente le contesta hablando, con tres motores intercambiables que son tres
planes comerciales.

```
basico    pipeline    Groq STT + Groq LLM + Fish TTS   voz clonada · sirve en WhatsApp
medio     gemini      Gemini Live, voz a voz            voz de Google
premium   openai      OpenAI Realtime, voz a voz        voz de OpenAI
```

Se elige con `MOTOR=` en el `.env`, o por sesión desde la demo web.

---

## 3. La frontera que no se cruza

```
src/motor_voz/
  brain/    cerebro: prompts, normalización, contexto, tools
            PROHIBIDO importar livekit. Hay un test que lo hace cumplir.
  voice/    canal: LiveKit, STT, TTS, sesión, motores
  api/      HTTP: emisión de tokens y límites
```

`brain/` no puede depender de `voice/` ni de `livekit`. Si lo hiciera,
WhatsApp, Telegram y el asistente de escritorio no podrían reusar el
cerebro, porque esos canales no pasan por LiveKit.

**Antes de dar por terminado cualquier cambio:** `uv run pytest -q`

---

## 4. El repositorio es PÚBLICO

- Ninguna clave en ningún archivo. Solo `.env.example` con valores vacíos.
- Las muestras de voz **no se versionan**: un wav limpio alcanza para
  clonar a una persona.
- Antes de commitear, verificá que no se cuele nada.

---

## 5. Cosas que ya nos rompieron

No las vuelvas a romper. Cada una está cubierta por un test.

| Trampa | Qué pasó |
|---|---|
| `groq.STT` viene con `language="en"` | Transcribía español como inglés, sin error |
| `groq.LLM` viene con `llama-3.3`, no gpt-oss | Se pagaba otro modelo sin darse cuenta |
| Vertex nombra los modelos distinto que `ai.google.dev` | Gemini Live no conectaba |
| El TTS lee literal | `24/7` sonaba "veinticuatro séptimo" |
| Pedirle al LLM "no uses símbolos" | Dejó de usar `¡!` y la voz salió plana |
| Pedirle brevedad sin iniciativa | Contestaba una frase y dejaba colgado al visitante |
| `scripts/token.py` | Le hacía sombra al módulo `token` de la stdlib |
| El plugin de Fish fuera del worker | Falla sin `utils.http_context.open()` |

---

## 6. Dónde está lo importante

| Necesitás | Mirá |
|---|---|
| Entender el diseño | `docs/superpowers/specs/2026-08-08-motor-voz-design.md` |
| Escribir la personalidad de un agente | `docs/guia-de-prompts.md` |
| Clonar una voz | `docs/voces/registro-de-consentimiento.md` |
| Levantar todo en local | `.\arrancar.ps1` |
| Ver el mapa del código | `graphify query "..."` |
