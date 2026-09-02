# Canales Meta después de crear el agente

**Estado:** decisión de arquitectura cerrada el 2026-09-02. La empresa
Quantumhive está verificada. WhatsApp Embedded Signup ya está implementado en
el backend y el panel; falta configuración externa y prueba real. Instagram y
Facebook todavía no tienen adaptadores de mensajes.

## Experiencia de producto

Después de crear y activar el agente, el dueño ve una sola sección:

> **Conectá los canales donde querés que atienda tu agente**

La sección contiene dos autorizaciones oficiales:

1. **Conectar WhatsApp Business** — WhatsApp Embedded Signup, ya implementado.
2. **Conectar Facebook e Instagram** — Facebook Login for Business. Si la
   Página tiene un Instagram profesional vinculado, el mismo alta descubre y
   asocia ambos activos.

Para un Instagram Business/Creator que no tenga Página vinculada se ofrece
**Conectar solo Instagram**, usando Instagram Login. Meta documenta que esa
variante no exige Página de Facebook.

No se debe vender como «un popup conecta los tres»: Meta mantiene WhatsApp
Embedded Signup y Facebook/Instagram Login como autorizaciones diferentes. La
experiencia sí queda en una única pantalla y sin copiar IDs o tokens.

## Proveedores y responsabilidades

| Momento | Fuente | Uso |
|---|---|---|
| Antes de crear el agente | Apify | Investigar datos públicos del perfil |
| Después de crear el agente | API oficial de Meta | Atender mensajes del negocio |
| Sin autorización | Ninguna | El agente no lee ni responde mensajes privados |

Apify no reemplaza la conexión oficial y sus datos no se usan como credencial.
Meta no reemplaza Apify para investigar perfiles públicos arbitrarios.

## Lo que ya existe y se reutiliza

- `tenant_canales` admite `web`, `whatsapp`, `instagram` y `facebook`.
- El tenant se resuelve por la cuenta receptora, nunca por datos del mensaje.
- Inbox, conversaciones, mensajes, outbox, límites y cerebro son comunes.
- Los tokens viven en la bóveda privada; Supabase guarda solo `secreto_ref`.
- El worker ya rechaza de forma cerrada canales sin enviador registrado.
- WhatsApp ya tiene firma, parser, cliente, webhook y Embedded Signup.

## Fase 1 — activar WhatsApp de QuantumHive

Trabajo manual en Meta:

1. Crear o confirmar la app Business del portfolio `1339027384106629`.
2. Agregar WhatsApp y crear la configuración de Embedded Signup.
3. Solicitar acceso avanzado y App Review para `business_management`,
   `whatsapp_business_management` y los permisos necesarios para mensajería.
4. Completar la habilitación como Tech Provider para clientes externos.

Configuración privada del servidor:

- `META_APP_ID`
- `META_APP_SECRET`
- `META_EMBEDDED_SIGNUP_CONFIG_ID`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_REGISTRATION_PIN`
- `WHATSAPP_SECRET_DIR`

El ruteo público `https://voz.quantumhive.com.ar/webhooks/whatsapp` ya está
aplicado. Devuelve 403 hasta cargar el verify token, que es el fallo cerrado
esperado.

Gate: conectar primero un número de QuantumHive/tester, mandar un mensaje desde
otro teléfono y comprobar entrada, respuesta, persistencia y aislamiento. Recién
después se prueba un cliente externo.

## Fase 2 — Instagram oficial

Crear `channels/instagram/` con la misma separación que WhatsApp:

- `payload.py`: traduce webhooks `messages` y `messaging_postbacks`.
- `firma.py`: valida la firma de Meta antes de leer el cuerpo.
- `cliente.py`: envía texto por `graph.instagram.com/{version}/{ig_user_id}/messages`.
- `onboarding.py`: canjea el código, descubre el IG profesional y suscribe la app.

Permisos mínimos para Instagram Login:

- `instagram_business_basic`
- `instagram_business_manage_messages`

Agregar permisos de comentarios o publicación únicamente si un producto futuro
los necesita. No pedirlos para el agente conversacional.

Gate: cuenta Business/Creator tester, mensaje iniciado por el usuario, respuesta
del agente, idempotencia y prueba de que un IG no puede asociarse a dos tenants.

## Fase 3 — Facebook Messenger

Crear `channels/facebook/`:

- webhook de Página con firma validada;
- parser neutral hacia `MensajeEntrante`;
- cliente Send API registrado en el mapa de enviadores;
- Facebook Login for Business para descubrir las Páginas autorizadas;
- token de Página en bóveda y Page ID en `tenant_canales`.

Solicitar solo los permisos de Página y mensajería efectivamente usados. Los
nombres y requisitos deben confirmarse contra la documentación vigente al
momento del App Review.

Gate: Página tester, mensaje real, respuesta, webhook duplicado y aislamiento.

## Fase 4 — panel unificado

Reemplazar la sección visual exclusiva de WhatsApp por tres tarjetas:

- WhatsApp: desconectado / pendiente / conectado / error.
- Instagram: no profesional / desconectado / conectado / error.
- Facebook: sin Página / desconectado / conectado / error.

La interfaz nunca recibe access tokens. Solo recibe IDs públicos, nombres,
estado y la URL/configuration ID necesaria para abrir el SDK oficial.

## Fase 5 — clientes externos

No habilitar el botón a clientes externos hasta tener:

- app publicada y App Review aprobada;
- acceso avanzado para los permisos usados;
- Tech Provider habilitado para Embedded Signup;
- política de privacidad y eliminación de datos accesibles públicamente;
- monitoreo de webhooks, revocaciones y expiración de tokens;
- soporte operativo y procedimiento para desconectar un canal.

## Fuentes oficiales verificadas

- Meta, WhatsApp Embedded Signup:
  https://www.postman.com/meta/whatsapp-business-platform/documentation/du6gzjv/embedded-signup
- Meta, Instagram API:
  https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api

