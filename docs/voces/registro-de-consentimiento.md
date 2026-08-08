# Registro de consentimiento de voces clonadas

El §19 del contexto maestro exige que toda clonación sonora registre propietario, consentimiento, muestras, versión, idioma, restricciones, aprobación y estado. Este archivo es ese registro mientras la tabla `voice_profiles` de Supabase no exista (llega en la Fase 5).

**Regla:** ninguna voz se habilita en el motor sin una entrada acá con estado `aprobada`.

**Las muestras de audio no se versionan.** Un wav limpio de una voz alcanza para clonarla y este repositorio es público. Quedan locales, fuera de git.

---

## VOZ-001 — Sergio Palomba

| Campo | Valor |
|---|---|
| Propietario | Sergio Palomba, fundador de QuantumHive |
| Relación | Voz propia. El propietario es quien autoriza |
| Consentimiento | Explícito, otorgado el 2026-08-08 en sesión de desarrollo |
| Muestra | Grabación propia, 60,8 s, mono 44,1 kHz, MP3 |
| Contenido de la muestra | Pitch comercial de QuantumHive, leído por el propietario |
| Proveedor | Fish Audio |
| Modelo de entrenamiento | `fast` |
| Identificador | `72042614…` (completo en `FISH_VOICE_ID` del `.env` local) |
| Visibilidad en el proveedor | **privada** |
| Idioma | Español rioplatense |
| Versión | 1 |
| Estado | **aprobada** |

### Restricciones de uso

- Solo para el agente receptor de QuantumHive en canales propios de la empresa.
- No se cede ni se asigna a agentes de clientes.
- No se publica el modelo ni se cambia su visibilidad a pública.
- Si el propietario revoca el consentimiento, se elimina el modelo en Fish y se marca esta entrada como `revocada`.

### Motivo de la clonación

La voz por defecto de Fish es inglesa y lee el español con acento extranjero — verificado a oído el 2026-08-08. Las voces argentinas del catálogo público eran una alternativa, pero la voz del fundador garantiza acento rioplatense y coherencia de marca.

---

## Plantilla para voces de clientes

Cuando la Fábrica de Voces empiece a clonar voces de terceros, cada entrada debe sumar a lo anterior:

- Identidad verificada de la persona cuya voz se clona.
- Consentimiento firmado, con fecha y alcance de uso.
- Tenant al que queda asociada la voz.
- Fecha de vencimiento del consentimiento, si la hubiera.
- Procedimiento de revocación acordado.

Una voz de un tercero **nunca** se clona con material obtenido sin autorización, por más que esté disponible públicamente.
