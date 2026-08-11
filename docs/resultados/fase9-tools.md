# Fase 9 — Verificación de tools y registries

**Fecha:** 2026-08-11
**Plan:** [`2026-08-11-motor-voz-fase-9.md`](../superpowers/plans/2026-08-11-motor-voz-fase-9.md)

## Estado

Las 6 tasks implementadas. **252 tests en verde**, 2 de integración contra
Supabase real, y la verificación end-to-end pasa entera.

```
publico   4 tools: get_services, get_business_info, capture_lead, transfer_to_human
interno   7 tools: las de arriba + get_mis_leads, get_mis_metricas, get_mis_conversaciones
```

## Lo que se verificó en vivo

| Qué | Resultado |
|---|---|
| Cada tenant responde con sus propios servicios | ✅ disjuntos |
| **Un lead de `demo_capilar` NO lo ve `quantumhive`** | ✅ |
| Desde el modo público no se alcanza ninguna tool interna | ✅ |
| Ningún modo alcanza `crear_negocio` ni `crear_agente` | ✅ |
| Ninguna tool expone `tenant`, `config` ni `sala` al modelo | ✅ |
| `brain/tools/` no importa `livekit` | ✅ |

El segundo es el que importa y el único que no se puede probar con un mock:
se guardó un lead con la barbería y se pidió la lista con los dos tenants.
Aparece en uno y no en el otro. El lead de prueba se borró.

## La regla que cambió el diseño

**Nadie crea negocios ni agentes hablando** — decisión de Sergio, 2026-08-11.
Ni el visitante, ni el dueño en su modo interno.

Esto **contradice el §6 del spec**, que le daba `crear_negocio`,
`guardar_expediente` y `disparar_web_factory` al registry del receptor.
**Falta actualizar el spec.**

Es más seguro: si crear un negocio fuera una tool conversacional, cualquiera
que llegue al agente receptor podría dar de alta uno convenciéndolo. Taparlo
con autenticación es defender un agujero que no hacía falta abrir. Dar de alta
es una operación de la fábrica detrás de login.

Hay un test (`TestNadieCreaNegociosHablando`) que se rompe si alguien agrega
una tool que cree. **No se arregla el test: se discute la decisión.**

## Decisiones de implementación que valen

**El registry es un mapa explícito de nombre a función, no un `getattr`.** Con
`getattr` sobre el módulo, cualquier función que alguien agregue queda
expuesta al modelo sin que nadie lo decida.

**`registry_de` lista lo que abre, no lo que cierra.** Solo el string exacto
`interno` abre lo interno; vacío, con mayúsculas, con espacios o inventado cae
en público. Es el chequeo que decide si alguien ve los leads de un negocio, y
un typo no puede abrirlo. Siete casos parametrizados lo fijan.

**Ninguna tool ve el tenant ni la sala.** `voice/herramientas.py` los ata y los
saca de la firma antes de entregarle la tool al modelo. Si los viera, podría
pasarle el de otro negocio: el modelo le hace caso a quien le habla.

**`MODO_DE_LA_SESION` está fijo en `publico`**, no leído de la sala ni del
token. Hoy no hay forma de saber quién está del otro lado, y el modo interno
da acceso a los leads. Se deja fijo a propósito para que nadie lo confunda con
algo que ya funciona.

## Trampas que aparecieron

**El host directo de Supabase es IPv6-only, y hoy se cayó la salida IPv6.**
Media hora antes andaba. El camino IPv4 es el pooler, que necesita la región
del proyecto — que no estaba anotada en ningún lado y adivinándola no aparece:
todas responden `tenant not found` menos la correcta.

Ya quedó en el runbook: **`us-west-2`, y el prefijo es `aws-1-`, no `aws-0-`**.

**No todas las tools aceptan `sala`.** Atársela a todas era un `TypeError` en
medio de una conversación. Se ata solo cuando la firma la pide.

## Lo que falta

- **Actualizar el §6 del spec** con la regla nueva.
- **Autenticación**, que abre el modo interno de verdad. Va antes del panel de
  control: si el panel sale primero, sale con la puerta abierta.
- La verificación a oído con el agente hablando. Lo de arriba prueba el
  aislamiento por código contra la base real; falta escuchar que el agente
  use las tools cuando corresponde y no invente.
