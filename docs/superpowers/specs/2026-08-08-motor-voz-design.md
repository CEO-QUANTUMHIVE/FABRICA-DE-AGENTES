# Diseño del Motor de Voz de QuantumHive

**Estado:** diseño para aprobación, implementación pendiente
**Fecha:** 2026-08-08
**Repositorio:** `CEO-QUANTUMHIVE/MOTOR-DE-VOZ-`
**Base:** plan "QUANTUMHIVE VOICE ENGINE" del fundador, auditado y corregido
**Autoridad superior:** `CONTEXTO_MAESTRO_VIGENTE_QUANTUMHIVE` y `CLAUDE.md`

---

## 1. Qué es y qué no es

El Motor de Voz es la **Fábrica de Voces** del §19 del contexto maestro: escucha y habla. Es un canal, no un cerebro.

El repositorio contiene además el **cerebro** (contexto, tools, datos del negocio) como paquete separado, porque hoy no existe otro lugar estable donde vivir. La frontera entre ambos es dura y verificada por test.

```text
MOTOR-DE-VOZ-        esqueleto y lógica del motor        (este repo)
fabrica-de-agentes-  frontend donde el cliente elige     (repo separado)
texto-voz-avatar     voz, avatar y carga su negocio
```

Los dos repos **no se pisan**. Este es backend. El otro es la interfaz guiada donde el cliente configura su agente.

### No es

- Un agente por cliente.
- Un prompt universal para todo.
- Un IDE, un orquestador, ni un reemplazo de Quantum Core.
- El reproductor de guiones cacheados (eso vive en el frontend/catálogo).

### Es

```text
UN RUNTIME + PERFILES POR VERTICAL + CONFIGURACIÓN POR TENANT
```

---

## 2. Decisiones cerradas

| # | Decisión | Valor |
|---|---|---|
| 1 | Primer consumidor | `www.quantumhive.com` — nuestro propio sitio es la demo |
| 2 | Tenant #1 | `quantumhive`, perfil receptor |
| 3 | Tenant #2 | `demo_capilar`, vertical barbería. Existe solo para probar aislamiento |
| 4 | Estructura | Un repo, dos paquetes blindados: `voice/` y `brain/` |
| 5 | Groq | Pago por uso. API key y facturación ya activas |
| 6 | Fish Audio | Pago por uso. `s2.1-pro`, con `s2.1-pro-free` por configuración |
| 7 | Transporte Live | **LiveKit self-hosted.** El binario `livekit-server` corre en nuestro backend. **LiveKit Cloud queda fuera de alcance** |
| 8 | Control plane | Supabase |
| 9 | Ubicación local | `C:\Users\sergio\Desktop\FABRICA-DE-AGENTES`, fuera de la bóveda |

Estas decisiones cierran, para este motor, varios pendientes del §33 del contexto maestro: proveedor de voz, proveedor de modelos e infraestructura Live. Se registran como decididas **para este motor**, no para todo el ecosistema.

---

## 3. Los tres modos

El motor expone tres modos. Comparten cerebro, no comparten transporte.

| Modo | Transporte | Latencia objetivo | Sirve a |
|---|---|---|---|
| **Live** | LiveKit / WebRTC | Conversacional, con barge-in | Web, consultas puntuales, conversación de muestra, agente receptor |
| **Asíncrono** | Archivo → archivo | Segundos, sin interrupción | WhatsApp, Telegram **y generación de guiones cacheados** |
| **Clonación** | Batch + consentimiento | No aplica | Alta de voces y asignación a agentes |

El modo asíncrono cubre mensajería y precacheo con el mismo código porque la operación técnica es idéntica: texto → archivo de audio, o archivo de audio → texto. No se duplica.

**Consecuencia arquitectónica:** el modo asíncrono no pasa por LiveKit. Por eso el cerebro no puede vivir adentro del runtime de LiveKit.

---

## 4. Frontera dura entre voz y cerebro

```text
src/
  voice/     LiveKit, STT, TTS, sesión, barge-in, clonación.
             Es un canal. Puede importar livekit.

  brain/     tenant resolver, loader, context builder, tools,
             datos del negocio, Supabase.
             PROHIBIDO importar livekit. Nunca.

  channels/  adaptadores: web_live, whatsapp, telegram.
             Cada uno traduce su transporte al contrato de brain/.
```

### Regla

`brain/` no importa `livekit` ni ningún símbolo de `voice/`. La dependencia va en un solo sentido.

### Cómo se hace cumplir

Un test recorre el AST de todos los módulos bajo `brain/` y falla si aparece un import de `livekit` o de `voice`. No es una convención escrita en un README: es rojo en CI.

### Por qué

El plan original ponía `context_builder`, `tools/` y `bookings` adentro del runtime de LiveKit. Con esa forma, WhatsApp — que es texto sobre HTTP, sin room ni WebRTC — no puede reusar nada. Habría que duplicar el cerebro entero o forzar mensajería por un room de audio. Separarlo ahora cuesta un día; separarlo después de tres verticales cuesta meses.

Esto además cumple el §19 ("la Fábrica de Voces no decide qué responder") y el §34 ("mezcla de voz y cerebro") del contexto maestro.

---

## 5. Multi-tenant

### Modelo

```text
tenant  →  profile (vertical)  →  config + datos del negocio
```

Un runtime. N perfiles. N tenants. **Prohibido** que aparezca en el código:

```python
if tenant == "barberia_pepe":
if rubro == "barberia":
```

El comportamiento sale de datos, nunca de ramas en el código.

### Tenants del MVP

| Tenant | Perfil | Rol |
|---|---|---|
| `quantumhive` | `receptor` | Atiende visitantes, explica servicios, capta interesados, guía la creación |
| `demo_capilar` | `capilar` | Barbería ficticia. Existe para probar que el aislamiento funciona |

### Las demos de la Web Factory son tenants, no código

Barbería, inmobiliaria, yoga, ventas: cada demo es un tenant de QuantumHive con datos ficticios y su perfil de rubro. Cuando un cliente contrata, se clona ese tenant con sus datos reales. No se escribe código nuevo por rubro.

### Resolución del tenant

El tenant se resuelve **antes** de construir el contexto del LLM, a partir de metadata firmada en el token de sesión.

El LLM **nunca** elige el tenant. El navegador **nunca** es fuente de verdad del tenant: manda un identificador, el backend lo valida contra Supabase y lo fija en la sesión.

---

## 6. Dos registries de tools separados

> **Corregido el 2026-08-15.** Este apartado decía que el agente receptor
> podía `crear_negocio`, `guardar_expediente` y `disparar_web_factory`. **Eso
> quedó sin efecto por la regla del 2026-08-11: nadie crea negocios ni agentes
> hablando** —ni el visitante ni el dueño en su modo interno—. Dar de alta es
> una operación de la fábrica detrás de login. Se corrige acá porque el texto
> viejo describía un agujero, y alguien podía leerlo e implementarlo.
> `TestNadieCreaNegociosHablando` se rompe si vuelve a aparecer una tool que
> cree: no se arregla el test, se discute.

Lo que decide qué registry toca es el **modo de la sesión**, no el vertical del
negocio. El interno es un superconjunto del público: el dueño también atiende.

```text
registry_publico    get_services, get_business_info,
                    capture_lead, transfer_to_human

registry_interno    registry_publico
                    + get_mis_leads, get_mis_metricas,
                      get_mis_conversaciones
```

Un tenant con perfil público **no puede** resolver una tool del registry del receptor, aunque el modelo la invente o alguien la inyecte por prompt. La verificación es en el resolver de tools, no en el prompt.

Esto implementa la separación modo público / modo propietario del §13 del contexto maestro.

---

## 7. Aislamiento de datos

### El problema

El runtime se conecta a Supabase con `SUPABASE_SERVICE_ROLE_KEY`, que **saltea RLS por diseño**. Cualquier policy que se escriba es decorativa para ese proceso. El aislamiento depende entonces del código, no de la base.

### La decisión

Aislamiento **en una sola capa de acceso a datos**:

- Toda query pasa por `brain/database/repositories.py`.
- El repositorio recibe el `tenant_id` del `TenantRuntimeConfig` y lo inyecta en cada consulta.
- Ningún otro módulo instancia el cliente de Supabase.
- Un test falla si aparece un uso directo del cliente fuera de ese archivo.

Se documenta explícitamente que **la RLS no es la defensa activa** en esta etapa, para no operar con una seguridad que no existe. Migrar a JWT por sesión con RLS real queda registrado como mejora posterior.

### Test crítico

Dos tenants, servicios distintos. Una sesión del tenant A debe poder ver únicamente los servicios de A, y debe ser **imposible** que alcance datos de B. Este test bloquea el merge.

---

## 8. Stack verificado

Verificado contra fuente oficial el 2026-08-08 (regla 6 del `CLAUDE.md`).

| Componente | Identificador exacto | Estado |
|---|---|---|
| Runtime de agentes | `livekit/agents`, Apache-2.0, release `1.6.9` (07/08/2026) | Activo, push diario |
| Plugin Groq | `livekit-agents[groq]~=1.5` | Publicado, v1.5.15 |
| Plugin Fish | `livekit-plugins-fishaudio` | Publicado, Python ≥3.10 |
| STT | Groq `whisper-large-v3-turbo` | Producción. Default del plugin |
| LLM | Groq `openai/gpt-oss-20b` | Producción |
| LLM complejo | Groq `openai/gpt-oss-120b` | Producción, por configuración |
| TTS | Fish `s2.1-pro` | Default del plugin. 80+ idiomas |

### Vía de facturación

Se usa el **plugin directo con `GROQ_API_KEY` propia**, no LiveKit Inference. Los IDs `groq/gpt-oss-120b` que aparecen en la documentación de LiveKit corresponden al gateway de inferencia de LiveKit, que factura por otro canal. Usar la key propia mantiene el control del proveedor y evita la dependencia irreversible que prohíbe el §34.

---

## 9. Costos y límites

### Precios verificados

| Servicio | Precio |
|---|---|
| Groq `whisper-large-v3-turbo` | $0,04 / hora de audio |
| Groq `openai/gpt-oss-20b` | $0,075 entrada / $0,30 salida por 1M tokens |
| Groq `openai/gpt-oss-120b` | $0,15 entrada / $0,60 salida por 1M tokens |
| Fish `s2.1-pro` | $0,015 / 1.000 bytes UTF-8 (= $15 / 1M) |
| Fish `Transcribe-1` | $0,006 / minuto (no se usa: Groq es 9× más barato) |
| LiveKit self-hosted | $0 por minuto. Costo fijo del VPS, no por conversación |

### Costo estimado de una conversación Live de 4 minutos

| Componente | Costo variable | Peso |
|---|---|---|
| Groq STT | $0,003 | 6% |
| Groq LLM | $0,004 | 8% |
| Fish TTS | $0,045 | **86%** |
| LiveKit self-hosted | $0 | costo fijo del VPS |
| **Total variable** | **≈ $0,052** | |

Supuestos: ~15 turnos, ~40K tokens de entrada acumulados, ~3.000 bytes sintetizados.

**Conclusión que ordena el diseño: el TTS es el 86% del costo variable. Groq es el 14%.** El ahorro no está en recortar el prompt: está en **no sintetizar audio**. Por eso el cacheo es la estrategia central y no una optimización — cada segmento pregrabado que se reutiliza es costo cero y concurrencia cero.

Al self-hostear LiveKit el transporte sale del costo por conversación y pasa a ser un gasto fijo mensual de servidor, independiente del volumen.

El español se cobra por bytes UTF-8; las tildes y la ñ ocupan 2 bytes, lo que agrega ~5-8% sobre el conteo de caracteres.

### Techo de concurrencia

**LiveKit no impone ningún techo, porque lo self-hosteamos.** `livekit/livekit` es Apache-2.0: sin fee por minuto, sin tope de participantes, sin cuenta de terceros. El único límite es el CPU y el ancho de banda del servidor propio. LiveKit Cloud no se usa en ninguna etapa.

Despliegue:

```text
Fases 0-4 (desarrollo)   livekit-server --dev en la máquina local.
                         Sin cuenta, sin costo, sin internet de por medio.

Producción               el mismo binario en un VPS con dominio, TLS
                         y puertos UDP abiertos para media WebRTC.
```

El único techo de terceros que queda es el TTS:

| Servicio | Límite | Cómo escala |
|---|---|---|
| Fish Audio | **5 solicitudes concurrentes** con < $100 consumidos | 15 con $100, 50 con $1.000, luego Enterprise |

**Una solicitud concurrente no es una conversación.** El slot se ocupa solo mientras se sintetiza audio, no durante toda la sesión. Con turnos de agente de ~5 s en conversaciones de ~4 min, el ciclo de trabajo ronda el 30%: 5 slots sostienen del orden de **15 conversaciones Live simultáneas**, y muchas más si el guión está cacheado. Al superarse, la API devuelve 429 y el router encola: se traduce en unos cientos de milisegundos de espera, no en un error visible.

El valor real del ciclo de trabajo depende de si el plugin usa requests por frase o un WebSocket persistente por sesión. **Se mide en la Fase 4** y se elige el modo que maximice conversaciones por slot.

Aun así, depender de un solo proveedor de TTS viola el §34 del contexto maestro. De ahí el pool.

### Estrategia de concurrencia en tres capas

1. **Cache.** Todo lo guionado va pregrabado y **no consume ningún slot**: onboarding, catálogo vivo, saludos, confirmaciones, respuestas frecuentes. Elimina la mayor parte de la demanda.
2. **Pool de proveedores.** `voice/providers/tts/` nace como **router sobre varios proveedores**, no como un proveedor único. Los slots se suman. El router elige por disponibilidad, voz solicitada, latencia y costo, y cae al siguiente cuando uno se satura. Ver §9.bis.
3. **TTS self-hosteado.** Un modelo propio con licencia que permita uso comercial convierte la concurrencia en función de la GPU contratada, sin cuota de terceros. Investigación delegada en `docs/briefs/2026-08-08-investigacion-tts-rioplatense.md`.

Mientras las tres capas no estén, el pico se maneja con **cola y mensaje honesto**, nunca con un error crudo.

### 9.bis Contrato del pool de TTS

```text
TTSProvider (interfaz)
  synthesize(texto, voice_id, formato) -> audio
  supports_streaming: bool
  max_concurrent: int
  slots_libres() -> int
  costo_por_1k_bytes: float
```

El router mantiene el pool y aplica, en orden: proveedor que tenga la voz pedida → con slot libre → de menor latencia → de menor costo. Si ninguno tiene slot, encola y avisa.

`fish-speech` **no puede** entrar al pool self-hosteado: su licencia prohíbe expresamente el uso comercial, incluido el servicio hosteado. Verificado el 2026-08-08.

Ningún módulo fuera del router conoce el proveedor concreto. Agregar, quitar o cambiar un TTS es configuración, no código.

### Controles de gasto y abuso

Obligatorios antes de exponer cualquier cosa al público:

- Tope de duración de sesión del lado del servidor: **4 minutos**, el agente cierra el room.
- Rate limit por IP en el endpoint de token.
- Contador global diario en Supabase con **kill-switch** que degrada a texto al superarse.
- Alerta al 80% del presupuesto mensual de TTS y de la capacidad del servidor LiveKit.
- Instrumentación de tokens, bytes sintetizados y minutos por sesión desde la primera fase con LLM.

---

## 10. Degradación

El principio 10 de `quantumcore-clean-architecture.md` exige degradar con claridad. Comportamiento mínimo definido:

| Falla | Comportamiento |
|---|---|
| Fish caído o sin concurrencia | Audio pregrabado de espera y continuidad en texto. La sesión no muere |
| Groq responde 429 | Muletilla hablada breve y reintento con backoff |
| Supabase inalcanzable | No se crean ni confirman registros. El agente lo dice y deriva a humano |
| LiveKit sin slots | Cola con mensaje honesto, nunca error crudo |
| Tope diario alcanzado | Modo Live desactivado, chat de texto disponible |

Ninguna falla puede terminar en silencio ni en una conversación cortada a mitad de frase.

---

## 11. Datos

Supabase es **control plane**, no parte del pipeline de audio.

```text
tenants              identidad, perfil, voz, idioma, estado
agent_profiles       verticales, prompt base, modelos default
tenant_configs       prompt propio, zona horaria, horarios, ajustes
services             oferta real por tenant
tools                catálogo de capacidades
profile_tools        qué puede cada perfil
tenant_tools         override por tenant
customers            consumidores por tenant
sessions             sesión, canal, room, modelos usados, estado
conversation_turns   turnos, latencias, tokens
leads                interesados captados por el receptor
voice_profiles       voz, propietario, consentimiento, muestras,
                     idioma, restricciones, aprobación, estado
usage_daily          contadores de gasto y sesiones para el kill-switch
```

`voice_profiles` implementa el registro de consentimiento que exige el §19 del contexto maestro. **Sin registro de consentimiento aprobado, la clonación no se habilita.**

`bookings` queda fuera del MVP: el tenant #1 capta interesados, no reserva turnos. Entra cuando exista una vertical que lo necesite.

---

## 12. Eventos hacia Quantum Core

El motor emite los eventos del §25 del contexto maestro:

```text
live.sesion_iniciada
live.sesion_finalizada
voz.perfil_creado
```

Se emiten desde el primer día. Si el motor no habla con el ecosistema desde el arranque, queda huérfano y reconectarlo después es trabajo perdido.

---

## 13. Seguridad

- Las seis claves (`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `GROQ_API_KEY`, `FISH_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`) viven solo en el entorno del hosting y en un `.env` local ignorado por git.
- Al repo sube únicamente `.env.example` con las claves vacías. **El repositorio es público.**
- Ninguna clave llega jamás al navegador. El frontend recibe únicamente un token temporal de LiveKit.
- El endpoint de token valida el tenant, verifica que esté activo, aplica los límites y fija la metadata.
- El LLM no escribe SQL. Llama tools; Python valida y ejecuta.

---

## 14. Fases

Cada fase tiene un gate. **No se avanza si la anterior está rota** (regla 3 del `CLAUDE.md`).

| Fase | Contenido | Gate |
|---|---|---|
| 0 | Esqueleto, `.env.example`, config, test de frontera `brain/` ↔ `voice/` | El test de frontera corre y falla si se viola |
| 1 | `livekit-server --dev` local, navegador ↔ agente, prompt fijo | Se escucha audio de ida y vuelta |
| 2 | Groq STT | Transcribe español correctamente |
| 3 | Groq LLM + instrumentación de tokens | Conversación coherente, con costo medido |
| 4 | Fish TTS, voz y acento rioplatense | Conversación completa con interrupción funcionando |
| 5 | Supabase, tenants, perfiles, servicios | Dos tenants cargados |
| 6 | Tenant resolver + capa única de repositorios | **Test de aislamiento en verde** |
| 7 | Context builder dinámico | Cada tenant responde solo con sus datos |
| 8 | Voz por tenant | Cada tenant habla con su propia voz |
| 9 | Tools del receptor y del público, registries separados | Captura de interesado end-to-end |
| 10 | Límites, kill-switch, degradación, eventos | Ninguna falla termina en silencio |
| 11 | Modo asíncrono (mensajería y precacheo) | Texto → archivo de audio reutilizable |

La Fase 4 no se aprueba con "se entiende": se aprueba con **acento rioplatense validado a oído**. `language = es` genérico da acento neutro y eso se nota.

---

## 15. Criterios de aceptación del MVP

1. Se puede hablar desde el navegador en `quantumhive.com`.
2. LiveKit transporta audio por WebRTC.
3. Groq transcribe español.
4. Groq genera respuestas.
5. Fish habla con voz elegida y acento rioplatense.
6. El usuario puede interrumpir al agente.
7. Existen dos tenants sobre el mismo runtime.
8. Cada tenant tiene servicios y voz propios.
9. **No existe contaminación entre tenants** y el test lo prueba.
10. Un tenant público no puede alcanzar tools del receptor.
11. Cada sesión queda registrada, con latencias y costo.
12. Se emiten los eventos hacia Quantum Core.
13. La sesión se corta sola a los 4 minutos.
14. Superado el tope diario, el sistema degrada a texto sin romperse.
15. `brain/` no importa `livekit` en ningún módulo, verificado por test.

---

## 16. Fuera de alcance

No se implementa en esta etapa: Redis, Kubernetes, Kafka, RabbitMQ, LangChain, LangGraph, base vectorial, RAG complejo, telefonía, SIP, microservicios, workers especializados, ni repositorios por rubro.

Tampoco: el reproductor de guiones cacheados (es del frontend), la producción de avatares (§17, sistema aparte), ni el sistema de reservas.

Se mantiene un **monolito modular**. La única división interna que importa hoy es `voice/` contra `brain/`.

---

## 17. Riesgos registrados

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Fish `s2.1-pro-free` vence el 31/08/2026 | El TTS pasa de gratis a $15/1M bytes | El modelo sale de configuración; cambiar es una variable de entorno |
| Techo de 5 concurrentes en Fish | La sexta conversación Live encola | Las tres capas del §9: cache, pool de proveedores y TTS propio |
| El VPS de LiveKit se satura | Caen las conversaciones en curso | Dimensionar por CPU y ancho de banda medidos, no estimados. Escalar el VPS |
| No conseguir un TTS comercial con acento rioplatense | El pool queda con un solo proveedor y vuelve el techo | Investigación delegada; si falla, negociar tramo alto con Fish |
| Acento neutro en español | La demo suena extranjera y pierde cercanía | Gate explícito en la Fase 4 |
| RLS no protege bajo service_role | Un error de código expone datos entre tenants | Capa única de repositorios más test que lo bloquea |
| Dependencia de LiveKit | Difícil de revertir | `brain/` no lo importa; cambiar de transporte no toca el cerebro |
| Inyección de prompt en demo pública | Llamada a tools privilegiadas | Registries separados, verificación en el resolver |

---

## 18. Qué se conservó del plan original

La arquitectura del plan del fundador se mantiene casi entera. Se conservan sin cambios:

- Un runtime, N perfiles, N tenants.
- No implementar WebRTC a mano; LiveKit se encarga.
- El LLM no escribe SQL; llama tools.
- Prohibido ramificar por tenant o por rubro en el código.
- La lista de "no implementar todavía".
- Orden por fases con gate y sin avance si algo está roto.
- El test de aislamiento multi-tenant como requisito crítico.

Se corrigieron: la ubicación del cerebro, el identificador del modelo gratuito de Fish, la vía de facturación de Groq, el tenant #1, la contradicción entre service_role y RLS, la ausencia de límites de gasto, la falta de degradación, y los faltantes de consentimiento de clonación y eventos hacia Quantum Core.
