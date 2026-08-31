# Procesos

Cómo se hace cada cosa en este repo, escrito después de hacerla y de
tropezarnos. **Si vas a hacer algo que está acá, leelo antes:** cada
documento existe porque algo costó horas la primera vez.

| Proceso | Cuándo |
|---|---|
| [Grabar muestras de voz](grabar-muestras-de-voz.md) | Se agrega o cambia una voz del catálogo |
| [Probar un tenant a oído](probar-un-tenant-a-oido.md) | Hay que validar que cada negocio suene como el suyo |
| [Aplicar una migración de Supabase](aplicar-una-migracion-de-supabase.md) | Cambia el esquema o los datos semilla |
| [Diagnosticar un 401](credenciales-y-401.md) | Una credencial falla y no se entiende por qué |
| [Conectar un WhatsApp al agente](conectar-whatsapp.md) | Un negocio tiene que atender por WhatsApp |
| [Conectar el Perfilador de Clientes](conectar-perfilador.md) | La Fábrica debe investigar y precargar un negocio |
| [Desplegar](desplegar.md) | Hay que subir cambios a producción |
| [Desplegar el frontend de la Fábrica](desplegar-la-fabrica.md) | Cambió `frontend/fabrica/` y hay que verlo en `/fabrica/` |

## La regla que vale para todos

**Verificá contra lo que está vivo, no contra lo que dice el documento.**
Un plan, un README o un snippet escrito ayer ya puede estar atrasado. Antes
de aplicar algo que otro escribió, abrí el archivo real. Pasó el 2026-08-10:
cuatro snippets de un plan de un día antes borraban, entre todos, la
calibración del VAD, la ruta `/api/voces`, la configuración de interrupción y
la resolución de voz — todo código que funcionaba.
