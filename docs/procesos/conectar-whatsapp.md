# Conectar un WhatsApp al agente

**Cuándo:** un negocio (el nuestro o el de un cliente) tiene que atender por
WhatsApp con su agente.

El circuito propio está completo en el repo: webhook, firma, parser, cerebro,
colas, envío, worker, topes y **Embedded Signup con Coexistencia**. No usa
YCloud ni 360dialog. Meta sigue siendo obligatoria porque WhatsApp es suyo y
puede cobrar sus conversaciones; lo que eliminamos es el abono del intermediario.

---

## Lo que el motor necesita saber de un número

Solo tres datos. Todo lo demás ya está resuelto:

| Dato | Dónde va | De dónde sale |
|---|---|---|
| `phone_number_id` | columna `cuenta_externa_id` de `tenant_canales` | Meta, al conectar el número |
| Access token del número | variable de entorno `SECRETO_<REF>` | Meta (System User) o el BSP |
| Referencia al token | columna `secreto_ref` de `tenant_canales` | la inventás vos: `whatsapp_<negocio>` |

El token **nunca** se guarda en la base: `tenant_canales.secreto_ref` guarda
solo el nombre, y [`channels/secretos.py`](../../src/motor_voz/channels/secretos.py)
lo traduce a variable de entorno. `whatsapp_quantumhive` →
`SECRETO_WHATSAPP_QUANTUMHIVE`. Esa tabla la lee el panel y aparece en
cualquier dump; un token adentro es un token filtrado.

Quién es el tenant lo decide **el número que recibió** el mensaje
(`metadata.phone_number_id` del webhook), no el que escribe:
[`repositorio.canal_de_cuenta()`](../../src/motor_voz/brain/tenants/repositorio.py#L137).

---

## PARTE A — Una sola vez, para todos los clientes

Esto se hace una vez y sirve para todos los números que conectes después.

### A.1 — Cuenta y portfolio de Meta

Hace falta una cuenta de Facebook **que funcione** y un portfolio de Meta
Business con los datos del negocio completos (nombre legal, dirección, sitio,
teléfono). Para ofrecer Coexistencia a clientes, QuantumHive debe completar la
verificación del negocio y la habilitación como Tech Provider de Meta.

> ✅ **Hecho el 2026-08-31.** Portfolio `Quantumhive`,
> `business_id 1339027384106629`, con **verificación de la empresa aprobada**.
> El portfolio viejo `1079094061364956` quedó abandonado.
> **Falta todavía:** acceso avanzado a los permisos `whatsapp_business_*`, App
> Review publicada y Tech Provider — necesarios solo para **clientes externos**.
> Para el número propio de QuantumHive alcanza con la app en modo desarrollo y
> el número agregado como tester.

> ⚠️ **A mano. Nunca con automatización de navegador.** El 2026-08-16 eso
> costó una cuenta personal de años. Está en la regla 0 de `CLAUDE.md`.

### A.2 — App de Meta con el producto WhatsApp

En `developers.facebook.com`: app de tipo Business con el caso de uso
**Connect through WhatsApp**. Crear además una configuración de
**WhatsApp Embedded Signup / Tech Provider**. De ahí salen los valores que van
al `.env` de la VM:

- **App ID** → `META_APP_ID`.
- **App Secret** (Configuración → Básica) → `META_APP_SECRET`.
  Con esto se valida la firma `X-Hub-Signature-256` de cada webhook.
- **Configuration ID** de Embedded Signup →
  `META_EMBEDDED_SIGNUP_CONFIG_ID`.
- **Verify token**: lo inventás vos, cualquier string largo →
  `WHATSAPP_VERIFY_TOKEN`. Meta lo repite una sola vez, al dar de alta el
  webhook.
- **PIN de registro** de seis dígitos elegido por QuantumHive →
  `WHATSAPP_REGISTRATION_PIN`.
- Carpeta privada persistente de la VM →
  `WHATSAPP_SECRET_DIR=/var/lib/quantumhive/secretos`.

La app necesita acceso avanzado a `whatsapp_business_management` y
`whatsapp_business_messaging`. Para clientes externos también necesita App
Review aprobada y estar publicada; en modo desarrollo solo entran roles/testers.

### A.3 — El webhook

En la app, WhatsApp → Configuración → Webhook:

- URL: `https://voz.quantumhive.com.ar/webhooks/whatsapp`
- Verify token: el de A.2
- Suscribir el campo **`messages`**. Sin eso Meta no manda nada.

Meta hace un `GET` con `hub.challenge` y espera el eco. Lo contesta
[`verificar_webhook_whatsapp()`](../../src/motor_voz/api/servidor.py#L602).

**Dos cosas tienen que estar antes de tocar "Verificar", o falla:**

1. **Regla de Caddy para `/webhooks/*` al puerto 8080.** Hecha el 2026-09-02.
   El endpoint ya llega a la API y devuelve 403 mientras falta el verify token.
2. **`WHATSAPP_VERIFY_TOKEN` cargado y la API reiniciada.** Si está vacío, el
   webhook falla cerrado a propósito y Meta ve un rechazo.

### A.4 — El worker de colas

El webhook solo guarda y devuelve 200. Quien contesta es el worker, que corre
aparte:

```bash
python -m motor_voz.channels.worker
```

Necesita su unidad de systemd propia. Sin worker, los mensajes entran a
`eventos_inbox` y no contesta nadie.

---

## PARTE B — Por cada número (el paso repetible)

Esta parte se repite en cada cliente, pero ya no requiere copiar IDs, tokens,
SQL ni editar el `.env`:

1. El dueño entra al panel de **su tenant**.
2. Pulsa **Conectar mi WhatsApp Business**.
3. Meta abre su ventana oficial y el dueño autoriza el número existente con
   Coexistencia. El número y la app de WhatsApp Business se conservan.
4. El backend canjea el código temporal, verifica que el número pertenece al
   WABA autorizado, registra el número y suscribe el webhook.
5. El token se guarda como archivo `0600` en `WHATSAPP_SECRET_DIR`; nunca pasa
   por el navegador ni por Supabase.
6. `tenant_canales` recibe automáticamente `phone_number_id → tenant`. La
   restricción global impide asignar el mismo número a dos negocios.

Rutas del panel:

- `GET /api/panel/{tenant}/canales/whatsapp/onboarding`: configuración pública
  y estado de preparación.
- `POST /api/panel/{tenant}/canales/whatsapp/onboarding/completar`: finaliza el
  alta server-side. Solo el dueño autenticado del tenant puede usarla.

La variable `SECRETO_WHATSAPP_<NEGOCIO>` sigue aceptándose únicamente como
compatibilidad para números cargados antes de Embedded Signup.

---

## Verificar que quedó andando

1. Escribirle al número desde otro teléfono.
2. En los logs de la API: `whatsapp | entrante | tenant=...`.
   - `firma invalida` → `META_APP_SECRET` mal o de otra app.
   - `cuenta sin tenant` → falta B.3, o el `phone_number_id` no es el que
     manda el webhook.
3. En los logs del worker, la salida. Si no hay worker, no hay respuesta.
4. Si el envío falla, el motivo queda en `ultimo_error` de la cola, ya
   clasificado como permanente o reintentable por
   [`whatsapp/cliente.py`](../../src/motor_voz/channels/whatsapp/cliente.py).
   El más común al principio es **131047**: fuera de la ventana de 24 horas
   hace falta una plantilla aprobada. El agente solo puede contestar dentro de
   esa ventana.

---

## Lo que NO hace falta

- **YCloud, 360dialog u otro BSP.** QuantumHive habla directo con Meta.
- **Tocar código, SQL o secretos** para sumar un cliente: el dueño usa el botón.
- **Un webhook por cliente.** Uno solo, para todos: el tenant sale del
  `phone_number_id`.
