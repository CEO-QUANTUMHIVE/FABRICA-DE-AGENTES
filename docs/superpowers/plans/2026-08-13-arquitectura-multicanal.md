# Arquitectura multicanal progresiva

**Canales comerciales:** Web, WhatsApp, Instagram y Facebook  
**Regla:** un solo agente por tenant; cada canal es un adaptador, nunca un bot aislado.

## Diseño fijado

```text
Web / WhatsApp / Instagram / Facebook
                  |
       adaptador del canal
  valida firma, deduplica, resuelve cuenta
                  |
          MensajeEntrante
                  |
       sesiones + memoria (comun)
                  |
              brain/
 prompt + tenant + tools + contexto
                  |
        adaptador de salida
```

El contrato común ya vive en `brain/mensajes.py`. Exige `tenant_id`, canal,
identificadores externos de conversación/remitente/mensaje y timestamp. La
clave `canal:mensaje_externo_id` permite que un reintento del proveedor no
genere dos respuestas.

El adaptador resuelve el tenant por la cuenta receptora del negocio. Nunca
acepta `tenant` desde el texto, query string o cuerpo controlado por la persona
que escribe. Es la misma regla que hoy aplica Web con el dominio.

## Qué se comparte y qué no

Se comparte por tenant: identidad, prompt, servicios, tools, historial,
memoria, límites, derivación a humano y métricas.

No se comparte entre canales: validación de webhook, identificadores externos,
reglas de ventana de respuesta, formato multimedia, permisos ni credenciales.

Los access tokens de Meta no van en `tenant_configs` ni en el repositorio.
Se guardarán cifrados en un almacén de secretos; la tabla de conexiones solo
guardará la referencia al secreto y datos no sensibles de la cuenta.

## Persistencia que precede al primer webhook — completada 2026-08-13

1. ✅ `tenant_canales`: tenant, canal, cuenta externa, estado y referencia al secreto.
2. ✅ `conversaciones`: tenant, canal, conversación externa, contacto y estado.
3. ✅ `mensajes`: conversación, id externo, dirección, contenido normalizado y fecha.
4. ✅ Restricción por cuenta + identificador externo para idempotencia.
5. ✅ Inbox/outbox durable para confirmar recepción antes de procesar.

Todas las consultas llevan `tenant_id`; las tablas públicas usan RLS como
defensa adicional, aunque el servicio siga filtrando explícitamente en el
repositorio central.

## Orden progresivo

1. **Web:** conservar LiveKit y el widget actual. Ya está operativo.
2. **WhatsApp:** primer adaptador de texto. Texto entrante/saliente, deduplicación,
   memoria, derivación humana y estado de entrega. Audio después de estabilizar texto.
3. **Instagram:** adaptar mensajes directos al mismo contrato y mismo cerebro.
4. **Facebook:** adaptar Messenger al mismo contrato; no mezclar sus permisos ni
   conexión con Instagram aunque ambos usen infraestructura de Meta.

## Gates por canal

- firma del webhook validada antes de procesar;
- cuenta externa mapeada a exactamente un tenant activo;
- evento duplicado no produce otra respuesta;
- ningún payload puede elegir otro tenant;
- credencial ausente/revocada falla cerrada y alerta, sin caer a QuantumHive;
- aislamiento probado con dos tenants reales;
- handoff humano detiene respuestas automáticas de esa conversación;
- límites de gasto por tenant y kill-switch antes de abrir producción.

## Siguiente incremento

Todavía no se conectaron cuentas reales de Meta ni se almacenaron tokens. La
persistencia ya está aplicada y probada contra Supabase real. Sigue el
procesador de inbox/outbox y luego el webhook de WhatsApp firmado.
