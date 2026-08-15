# Canal WhatsApp — primer adaptador de texto

**Depende de:** [`2026-08-13-arquitectura-multicanal.md`](2026-08-13-arquitectura-multicanal.md),
cuya persistencia ya está aplicada y probada contra Supabase real.

**Hito, ridículamente concreto:** mandar `hola` al WhatsApp de QuantumHive y
recibir una respuesta generada por nuestro backend, con el mismo cerebro que
atiende la web.

**Orden:** QuantumHive (`tenant_001`) primero. Jaz / Yaspapeobeauty entra como
`tenant_002` recién cuando el circuito esté probado con nuestro propio número.

---

## Lo que ya existe — no reconstruir

| Pieza | Dónde |
|---|---|
| Contrato neutral `MensajeEntrante` | `brain/mensajes.py` |
| Resolver cuenta receptora → tenant | `repositorio.canal_de_cuenta()` |
| Ingreso atómico e idempotente | `registrar_mensaje_entrante()`, migración `20260813223713` |
| Tablas de canales, conversaciones, mensajes, inbox y outbox | misma migración |
| Prompt en tres capas, contexto y tools por tenant | `brain/prompt.py`, `brain/contexto.py`, `brain/tools/` |
| Conocimiento versionado que alimenta el contexto | migración `20260813225923` |

**Lo único genuinamente nuevo es el cerebro de texto.** Hoy el LLM entra por los
plugins de LiveKit en `voice/motores.py`, y `brain/` tiene prohibido importar
`livekit` — es la frontera dura del proyecto. WhatsApp necesita un camino de
texto que no pase por ahí.

---

## El número: hay dos onboardings y no dan lo mismo

**Ningún negocio va a cambiar su número.** Esa restricción es del producto, no
negociable, y define qué camino se toma.

### Directo — el número sale de la app

Se registra el número en la Cloud API y **deja de funcionar en la app de
WhatsApp Business**; el historial de la app se pierde. A partir de ahí solo se
atiende por API. Sirve para nosotros y para nadie más.

### Coexistence — el número queda en los dos lados

Meta soporta oficialmente que un número esté **en la app y en la Cloud API a la
vez**, con el historial sincronizado. El dueño sigue contestando desde su
celular; el agente responde por API en paralelo.

Requisitos, que no son un flag:

- ser **Solution Partner o Tech Provider** registrado en Meta;
- **Embedded Signup con session logging** implementado — no hay coexistence sin
  Embedded Signup;
- el cliente con la app en **2.24.17 o superior**.

Límites:

- throughput fijo de **20 mps** (irrelevante a nuestra escala);
- la sincronización de contactos se hace **una sola vez**, y hay **24 h** desde
  el onboarding para hacerla; si se pasa, el cliente debe desconectar y repetir
  el flujo entero;
- solo viaja el historial de los **últimos 180 días**;
- lo enviado desde la app es gratis y **no consume la ventana de 24 h** de la
  API; solo se paga lo que sale por API.

Sin confirmar en la doc de Meta, visto en blogs de vendors: que 14 días sin
abrir la app cortarían la conexión con la API. Verificar antes de prometerlo.

### Qué camino para quién

| Tenant | Onboarding |
|---|---|
| `tenant_001` QuantumHive | directo. Somos el conejillo de indias y no exige Tech Provider |
| `tenant_002` Jaz y todo cliente | **Embedded Signup con coexistence**. Conserva número, app e historial |

Consecuencia de producto: con onboarding **directo**, el handoff a humano no
puede ser "que conteste el dueño desde su celular" — tiene que ser el panel. Con
**coexistence** el dueño contesta desde su app de siempre, y el Task 7 pasa de
imprescindible a comodidad.

**Referencias:** [Onboard WhatsApp Business app
users](https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/onboarding-business-app-users/),
[Embedded Signup
overview](https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/overview/),
[Become a Tech
Provider](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/get-started-for-tech-providers).
Modelo de datos parecido al nuestro, sobre Supabase:
[open-bsp-api](https://github.com/matiasbattocchia/open-bsp-api).

---

## Tareas

### Task 1 — Parser del payload de Meta

`channels/whatsapp/payload.py`. Convierte el webhook de Meta a `MensajeEntrante`.

- Extrae `phone_number_id` de `entry[].changes[].value.metadata`, que es la
  cuenta **receptora** y lo único que puede decidir el tenant.
- `messages[].id` → `mensaje_externo_id`; `messages[].from` → remitente;
  `conversacion_externa_id` = el `wa_id` del contacto.
- Un webhook puede traer **varios mensajes y varios entries**: devuelve una lista.
- Ignora `statuses[]` (entregado/leído) en este task — van en el Task 6.
- Tipos no soportados (imagen, audio, ubicación) devuelven un marcador explícito,
  no se caen ni se procesan como texto vacío.

**Gate:** tests con payloads reales de la documentación de Meta, incluidos uno
con dos mensajes, uno de `statuses` puro y uno con tipo desconocido.

### Task 2 — Firma del webhook

`channels/whatsapp/firma.py`. Valida `X-Hub-Signature-256`: HMAC-SHA256 del
**cuerpo crudo** con el app secret.

- Comparación en tiempo constante (`hmac.compare_digest`).
- Se valida sobre los bytes exactos recibidos, **antes** de parsear JSON. Si se
  reserializa el cuerpo, la firma no cierra nunca.
- Falta de firma, firma mal formada o secreto ausente → rechazo. Falla cerrado.

**Gate:** test de firma válida, inválida, ausente, y de que el secreto vacío
rechaza en vez de aceptar.

### Task 3 — Endpoints del webhook

En `api/servidor.py`:

- `GET /webhooks/whatsapp` — verificación de Meta. Compara `hub.verify_token`
  contra `WHATSAPP_VERIFY_TOKEN` en tiempo constante y devuelve `hub.challenge`
  en texto plano. Token distinto → 403.
- `POST /webhooks/whatsapp` — valida firma, resuelve el canal por
  `phone_number_id`, persiste con `registrar_mensaje_entrante()` y **responde 200
  enseguida**. No genera la respuesta dentro del request.

Meta reintenta si tarda o si no recibe 200. Por eso el 200 es inmediato y el
trabajo real queda en el inbox.

**Gate:** cuenta externa desconocida → 200 sin persistir nada y con log (no 404:
un 404 hace que Meta reintente para siempre). Evento repetido → 200 y un solo
registro. Ningún campo del payload puede cambiar el tenant resuelto.

### Task 4 — Cerebro de texto

`brain/conversacion.py`. **No importa `livekit`.** Lo verifica el test de
frontera que ya existe.

```
responder(config, tenant, historial, mensaje) -> str
```

- Arma el prompt con `prompt.py` y `contexto.py` — el mismo de la voz, incluido
  el conocimiento versionado publicado.
- Llama a Groq por HTTP con el modelo de texto que ya usa el nivel 1.
- Usa el mismo `registry_de(modo)` de la Fase 9, con el modo **público**.
- **No** normaliza con `brain/normalizar.py`: eso existe para que el TTS no lea
  `24/7` como "veinticuatro séptimo". En texto escrito hay que dejar los números
  como están.
- Historial acotado por cantidad de mensajes y por tokens: una conversación de
  WhatsApp de seis meses no entra en un prompt ni conviene pagarla.

**Gate:** un tenant contesta con sus servicios y no con los del otro, contra la
base real. Tools invocadas correctamente. `import livekit` ausente.

### Task 5 — Procesador de inbox → outbox

`channels/procesador.py`. Worker que toma pendientes de `eventos_inbox`, llama al
Task 4 y encola en `eventos_outbox`.

- Toma con bloqueo (`bloqueado_hasta`) para que dos workers no procesen lo mismo.
- Reintentos con backoff sobre `disponible_en` e `intentos`; tope de intentos y
  después `fallido`, nunca un loop infinito.
- `clave_idempotencia` = la del `MensajeEntrante`, así un reintento no encola dos
  respuestas.
- Respeta `modo_atencion`: si la conversación está en `humano`, **no responde**.

**Gate:** matar el worker después de encolar y antes de confirmar no produce dos
respuestas al reanudar.

### Task 6 — Envío por la Cloud API

`channels/whatsapp/cliente.py`. Consume `eventos_outbox` y hace
`POST /{version}/{phone_number_id}/messages`.

- El token sale del almacén de secretos vía `secreto_ref`. **Nunca de
  `tenant_canales` ni del repo.**
- Ventana de 24 h: fuera de ella un mensaje libre es rechazado por Meta y hace
  falta plantilla. Se detecta el error y se marca `fallido` con motivo claro, no
  se reintenta a ciegas.
- Guarda el `mensaje_externo_id` que devuelve Meta y actualiza el estado del
  mensaje saliente con los webhooks de `statuses`.

**Gate:** token revocado → `fallido` con motivo, alerta, y **no** cae al tenant
por defecto.

### Task 7bis — Embedded Signup, el alta de clientes

Lo que convierte esto en fábrica y no en un bot nuestro. Va en la pestaña
**Conexiones** de la PWA, que ya existe.

- Botón "Conectar WhatsApp" que abre el popup de Meta con session logging.
- El cliente autoriza desde su propia cuenta: **nunca nos pasa un token por
  mail ni por chat**.
- Al volver, se canjea el código por el token del cliente, se guarda en el
  almacén de secretos y se crea la fila en `tenant_canales` con estado
  `conectado` y su `secreto_ref`.
- La sincronización de contactos se dispara **en el momento**: hay 24 h y una
  sola oportunidad.

Bloqueado por el alta de QuantumHive como Tech Provider en Meta. El resto del
canal no depende de esto: con onboarding directo se prueba todo el circuito.

### Task 7 — Derivación a humano

Sin la app de WhatsApp Business, el dueño necesita poder contestar desde el
panel. Mínimo viable: `modo_atencion = 'humano'` detiene al agente, y el panel
permite escribir en esa conversación.

### Task 8 — Límites y kill-switch

Tope de gasto por tenant y un interruptor que corta las respuestas automáticas.
Antes de abrir producción, no después. Un bucle de mensajes con un LLM detrás se
paga en tokens.

---

## Configuración nueva

```
META_APP_SECRET             firma de los webhooks, comun a la app de Meta
WHATSAPP_VERIFY_TOKEN       lo inventamos nosotros, solo para el GET
WHATSAPP_API_VERSION        fijada explicita, no "la ultima"
```

El access token de cada número **no va en el `.env` del repo**: va al almacén de
secretos, y `tenant_canales.secreto_ref` guarda solo la referencia.

## Gates del canal — heredados del plan multicanal

- firma validada antes de procesar;
- cuenta externa mapeada a exactamente un tenant activo;
- evento duplicado no produce otra respuesta;
- ningún payload puede elegir otro tenant;
- credencial ausente o revocada falla cerrada y alerta, sin caer a QuantumHive;
- aislamiento probado con dos tenants reales;
- handoff humano detiene las respuestas automáticas;
- límites de gasto y kill-switch antes de abrir producción.

## Lo que bloquea el hito

Los Tasks 1, 2, 4 y 5 no necesitan ninguna credencial de Meta y se pueden
escribir y testear ya. El circuito completo necesita, de Sergio:

1. un número para QuantumHive, decidiendo antes si se sacrifica la app de
   Business (onboarding directo) o se usa uno nuevo;
2. app de Meta con WhatsApp activado, `App Secret`;
3. `Phone Number ID` y `WABA ID`;
4. token permanente de System User;
5. el webhook publicado en HTTPS — o sea, un deploy siguiendo
   [`docs/procesos/desplegar.md`](../../procesos/desplegar.md).

Y en paralelo, sin bloquear nada de lo anterior: **iniciar el alta de
QuantumHive como Tech Provider**, que es lo que habilita el Task 7bis y por lo
tanto el alta de Jaz sin que pierda su app. Tiene verificación de negocio de por
medio, así que conviene empezarlo temprano.
