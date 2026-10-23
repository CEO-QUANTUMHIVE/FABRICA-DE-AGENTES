# El webhook de Meta: dónde vive y cómo se verifica

**Cuándo:** Meta no verifica el webhook, o un mensaje entrante no llega y hay
que saber en qué punto del camino se corta.

**Lo importante:** hay **un solo webhook para todos los clientes**. Quién es el
tenant no lo decide quien escribe, lo decide el `phone_number_id` que trae el
mensaje (`brain/tenants/repositorio.py` → `canal_de_cuenta()`).

---

## La URL

```
https://voz.quantumhive.com.ar/webhooks/whatsapp
```

HTTPS, sin query, exactamente así. En Meta va en **WhatsApp → Configuración →
Webhook → URL de devolución**, con el verify token que está en la VM.

---

## El camino, trazado el 2026-10-23

```
Meta
 └─ Cloudflare  →  tunnel nombrado de cloudflared (nunca un quick tunnel)
     └─ 127.0.0.1:18082   nginx del proxy  (qh-voz-proxy)
         │                config: /home/ubuntu/.voz/nginx.conf
         ├─ location /webhooks/  → 127.0.0.1:18081  ← la API
         ├─ location /api/       → 127.0.0.1:18081  ← la API
         └─ location /           → 127.0.0.1:7880   ← LiveKit
     └─ 127.0.0.1:18081   API  (qh-motor-voz-api-canary)
         ├─ GET  /webhooks/whatsapp  → valida el verify token, devuelve hub.challenge
         └─ POST /webhooks/whatsapp  → valida X-Hub-Signature-256 con META_APP_SECRET
     └─ worker  (qh-motor-voz-worker)  → lee eventos_inbox y contesta por eventos_outbox
```

---

## Lo que estaba roto el 2026-10-23

No existía `location /webhooks/`. La petición caía en `location /`, que va a
LiveKit, y LiveKit —que está escrito en Go— contestaba **`404 page not found`**.
Meta no podía completar la verificación y ningún mensaje entrante llegaba.

La API atrás estaba bien todo el tiempo: sin tocarla, `GET /webhooks/whatsapp`
ya devolvía `403 verificacion rechazada`, que es el cierre correcto.

**Arreglo:** bloque nuevo en `/home/ubuntu/.voz/nginx.conf`, backup previo en
`nginx.conf.bak-20261023-whatsapp`, `nginx -t` y reload. La verificación real,
sin imprimir el token:

| | |
|---|---|
| verify token correcto | `200` y el cuerpo es el `hub.challenge` que se mandó |
| verify token equivocado | `403 verificacion rechazada` |

---

## Qué tiene que estar tildado en Meta

1. **URL** HTTPS como arriba.
2. **Verify token** = el valor de `WHATSAPP_VERIFY_TOKEN` en la VM (10
   caracteres). Si está vacío, el endpoint rechaza a propósito.
3. **Campo `messages` suscripto.** Sin esto Meta no manda nada y todo parece
   estar bien igual: es el error más fácil de cometer y el más difícil de ver.
4. La app en modo **Development** con el número como tester, o **publicada**
   con App Review aprobada.

Las credenciales ya están cargadas en la API y en el worker:
`META_APP_ID`, `META_APP_SECRET`, `META_EMBEDDED_SIGNUP_CONFIG_ID`,
`WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_REGISTRATION_PIN`, `WHATSAPP_SECRET_DIR`.
No se versionan nunca: viven en la VM y en el repo solo está su nombre.

---

## Cómo leer cada fallo

| Qué se ve | Qué significa | Qué hacer |
|---|---|---|
| `404 page not found` (inglés, 19 bytes) | La recibió LiveKit: falta el `location /webhooks/` | mirar `/home/ubuntu/.voz/nginx.conf` |
| `403 verificacion rechazada` | Verify token vacío o distinto | `docker exec qh-motor-voz-api-canary printenv WHATSAPP_VERIFY_TOKEN` y reiniciar la API |
| 200 en la verificación pero Meta sigue sin aceptar | Suele ser la URL (falta HTTPS, sobra una barra) o la app equivocada | revisar qué app tiene Meta abierta |
| Meta dice verificado y **no llega nada** | Falta suscribir `messages`, o `cuenta sin tenant` | suscribir el campo; fila en `tenant_canales` con ese `phone_number_id` |
| Entra y **no contesta nadie** | No hay worker, o el worker no leyó la cola | `docker ps` contra `qh-motor-voz-worker` y sus logs |
| `firma invalida` | `META_APP_SECRET` mal o pertenece a otra app | comparar contra la app que manda el webhook |
| El envío falla con `131047` | Pasaron 24 h: afuera de esa ventana hace falta una plantilla aprobada | el agente solo contesta dentro de la ventana |

---

## Comandos

```powershell
# 1. la verificación que hace Meta, hecha a mano
curl.exe -s -w "`nHTTP %{http_code}`n" `
  "https://voz.quantumhive.com.ar/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=EL_TUYO&hub.challenge=123"
# tiene que devolver HTTP 200 y el cuerpo 123

# 2. el proxy
docker exec qh-voz-proxy nginx -t
docker exec qh-voz-proxy nginx -s reload
cat /home/ubuntu/.voz/nginx.conf

# 3. qué está pasando
docker logs --tail 100 qh-motor-voz-api-canary 2>&1 | grep whatsapp
docker logs --tail 100 qh-motor-voz-worker 2>&1
```

---

## Reglas

- **Nunca** un quick tunnel (`*.trycloudflare.com`) como webhook: el hostname
  es efímero y cambia al reiniciar. Siempre el tunnel con nombre.
- **No imprimir tokens** en logs ni en chats. Para comprobar uno se usa el eco
  del challenge, como arriba.
- El verify token y el app secret viven en la VM, **nunca** en el repo (es
  público) ni en la base.
- Al tocar el nginx: backup primero, `nginx -t` después, reload recién al final.

## Sobre Telegram

El canal de Telegram **hoy anda por polling** (`getUpdates`), no por webhook:
`channels/telegram/webhook.py` es un script aparte que recibe un JSON, no una
ruta registrada en la API. El `location /webhooks/` que se agregó ya queda
listo para el día que se cablee su webhook, pero no hay que esperarlo para
probar Telegram.
