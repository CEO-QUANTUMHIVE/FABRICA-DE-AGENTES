# Resultado: persistencia multicanal durable

**Fecha:** 2026-08-13

## Implementado

- `tenant_canales`: cuenta externa resuelta a un único tenant.
- `conversaciones`: historial común para Web, WhatsApp, Instagram y Facebook.
- `mensajes`: entradas, salidas y estados de entrega.
- `eventos_inbox`: recepción durable e idempotente de webhooks.
- `eventos_outbox`: respuestas durables con reintentos.
- RPC atómica `registrar_mensaje_entrante` restringida a `service_role`.
- claves foráneas compuestas para impedir cruces tenant/canal/conversación.
- RLS y lectura del panel limitada a usuarios vinculados al tenant.
- repositorio Python para resolver cuentas, ingresar mensajes y consultar chat.

Migración aplicada: `20260813223713_persistencia_multicanal.sql`.

## Verificación real

- reintentar el mismo webhook devuelve `duplicado=true`;
- dos tenants pueden usar el mismo identificador externo sin mezclarse;
- consultar una conversación con el tenant incorrecto devuelve cero mensajes;
- un canal rechaza el `tenant_id` de otro aun usando `service_role`;
- `supabase db lint`: sin errores de esquema.

## Siguiente incremento

Procesador de inbox/outbox y adaptador de texto de WhatsApp. Antes de abrirlo
a producción siguen siendo obligatorios firma del webhook, límites de gasto,
kill-switch y derivación humana.

El panel se especificó aparte en
`docs/superpowers/plans/2026-08-13-panel-de-control.md`.
