# Fases 5-8 — Verificación multi-tenant

**Fecha:** 2026-08-10
**Rama:** `arquitectura/spec-motor-voz`
**Plan:** [`2026-08-09-motor-voz-fases-5-8.md`](../superpowers/plans/2026-08-09-motor-voz-fases-5-8.md)

## Estado

Las 10 tareas están implementadas. **Cuatro de los cinco puntos del gate
están verificados; el quinto es de oído y lo tiene que hacer Sergio.**

## Tests

```
180 en verde · 1 salteado · 5 deseleccionados
2 de integración en verde (contra Supabase real)
```

El plan tomaba 122 como referencia previa. El salteado espera las muestras de
voz de OpenAI (punto 3.5, trabado en la clave de Azure). Los 5 deseleccionados
son los de `smoke` e `integracion`, que no corren por defecto porque gastan
créditos o piden red.

## Lo que devuelve Supabase, leído en vivo

| | quantumhive | demo_capilar |
|---|---|---|
| nombre | QuantumHive | Barberia Demo |
| perfil | `receptor` | `capilar` |
| servicios | Web inteligente, Empleado virtual | Corte clasico, Afeitado a navaja |
| `voice_id` | `63f9f124…` (VOZ-003, clonada) | `e7e10492…` (**placeholder**) |
| sala | `demo-quantumhive-…` | `demo-demo_capilar-…` |

## El gate, punto por punto

| # | Punto | Estado | Cómo se verificó |
|---|---|---|---|
| 1 | Dos tenants con servicios y voz propios | ✅ | Leído de Supabase real |
| 2 | Test de aislamiento contra Supabase real | ✅ | `pytest -m integracion`, 2 en verde |
| 3 | Cada tenant responde solo con sus servicios | ✅ | `test_contexto.py` + prompts reales comparados |
| 4 | Cada tenant habla con su propia voz | ⚠️ **falta el oído** | Los `voice_id` son distintos en la base, pero nadie los escuchó |
| 5 | `brain/` sigue sin importar `livekit` | ✅ | `test_frontera.py`, recorre el paquete con `rglob` |

## Lo que falta, y por qué no lo hice yo

**El punto 4 es de oído y no lo puedo cerrar.** Dos motivos:

1. El `voice_id` de `demo_capilar` (`e7e1049270f649f7bd48b7b48adb8898`) es el
   placeholder que traía el plan. Que sea distinto del de QuantumHive no
   prueba que sea una voz real del catálogo de Fish — si no existe, el motor
   va a caer a la voz por defecto y los dos tenants van a sonar igual.
   **Elegir un `voice_id` real es un pendiente de Sergio.**
2. Los Steps 2 y 3 del plan piden levantar la API y el agente para escuchar.
   La regla del repo es explícita: no levantar servidores durante la
   implementación, el flujo es cambio → tests → commit → push → Sergio prueba.

Lo que sí se verificó sin levantar nada: los dos tenants se resuelven contra
Supabase real, sus servicios son disjuntos, y los prompts que arma
`construir_contexto` no se cruzan ni en identidad ni en servicios.

## Trampas que aparecieron

**Los snippets del plan estaban desactualizados y borraban código vivo.** El
plan se escribió el 2026-08-09 y desde entonces entraron commits que tocaron
esos mismos archivos. Copiar literal habría hecho estos cuatro destrozos:

| Snippet | Qué borraba |
|---|---|
| `_pipeline` en `motores.py` | La calibración del VAD (`c4abe61`), que bajó la sensibilidad del micrófono en los tres motores |
| `emitir_token` | El bloque que resuelve y valida la voz, y los campos `voz`/`nombre_voz` de la respuesta |
| `crear_app` | La ruta `/api/voces` entera, o sea el selector de voces |
| `entrypoint` del agente | `openai_voice` y la config de interrupción (`min_words: 2`), que arregló que el agente se respondiera solo |

Además el snippet de `emitir_token` usaba `voz` sin definirla, y el
`voz_de_la_sala` del plan tomaba dos argumentos cuando el real toma tres
(quedó viejo cuando OpenAI ganó catálogo de voces, commit `7985715`).

**Para el próximo plan largo: leer el archivo real antes de aplicar un
snippet, aunque el plan lo dé completo.** Un plan escrito hace un día ya
puede estar atrasado.

## Riesgos del plan que quedaron descartados

- **«El nombre de sala pasa de 3 a 4 partes y rompe al frontend».** No pasa:
  el widget nunca parsea el nombre de sala, solo usa el objeto `Room`.
  Verificado con `grep` sobre `frontend/`.
- **«`acreate_client`/`maybe_single()` cambian de nombre».** No cambiaron; el
  repositorio anda contra el paquete instalado.

## Qué sigue

Fase 9 (tools, registries, captura de leads) y Fase 10 (límites de gasto,
kill-switch, degradación, eventos hacia Quantum Core). Cada una es un plan
propio.

Decisión tomada el 2026-08-10: **`brain/` sale a un repo propio** cuando esto
cierre, porque va a ser el pilar donde vivan todos los agentes de QuantumHive,
los propios y los de los clientes. El costo de ese movimiento es bajo a
propósito: `test_un_solo_cliente_supabase.py` obliga a que todo acceso a datos
pase por `repositorio.py`, un solo archivo.
