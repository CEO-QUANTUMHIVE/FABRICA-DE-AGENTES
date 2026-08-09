# Widget embebible del orbe — Diseño

**Estado:** diseño aprobado, implementación pendiente
**Fecha:** 2026-08-09
**Repositorio:** `CEO-QUANTUMHIVE/MOTOR-DE-VOZ-`

---

## 1. Qué es y qué no es

Un `<script>` de una línea que cualquier página — la landing de QuantumHive, el catálogo vivo de un cliente, o la página que sea — pega antes de `</body>` y le suma el orbe: un botón flotante que al abrirse conecta por voz y texto al motor de voz que ya está en producción (`voz.quantumhive.com.ar`).

QuantumHive es el tenant #1: la landing (`www.quantumhive.com.ar`) es la primera instalación y la prueba de que el proceso es repetible. Todo lo que se construya acá tiene que quedar documentado como pasos simples y automatizables — no un procedimiento a mano que se reinventa por cliente.

### No es

- Una reescritura del cerebro ni del motor: consume la API que ya existe (`POST /api/token`, `wss://voz.quantumhive.com.ar`).
- Un asistente de escritorio: es la versión web del orbe de `QUANTUM-ASISTENTE-`, sin captura de pantalla ni IPC de Electron.
- Multi-tenant real todavía: usa el sistema de `nivel` (1/2/3) que ya está en producción. Cuando aterricen las Fases 5-8 de multi-tenant (`docs/superpowers/plans/2026-08-09-motor-voz-fases-5-8.md`), el widget no cambia — el backend empieza a resolver tenant de verdad y el widget sigue mandando lo mismo.

### Es

```text
UN SCRIPT LIVIANO EN LA PAGINA DEL CLIENTE
        +
UNA APP AISLADA, SERVIDA DESDE NUESTRA INFRAESTRUCTURA
        +
EL MISMO BACKEND DE VOZ QUE YA ESTA EN PRODUCCION
```

---

## 2. Decisiones cerradas

| # | Decisión | Valor |
|---|---|---|
| 1 | Origen del diseño visual | Puerto de `Orbe.tsx`/`orbe.css` de `CEO-QUANTUMHIVE/QUANTUM-ASISTENTE-`, rama `agent/navegador-integrado` (la real; `main` está desactualizada) |
| 2 | Empaquetado | Script diminuto + `<iframe allow="microphone">`, no un bundle de React/Preact suelto en la página del cliente |
| 3 | Runtime de la app interna | Preact (API compatible con los hooks que ya usa `Orbe.tsx`, ~4 KB contra ~45 KB de React) |
| 4 | Qué se quita del original | Todo lo de visión/captura de pantalla (`fuentes`, `elegirFuente`, el botón 👁): no aplica a una landing |
| 5 | Qué se agrega | Selector de motor de 3 botones (clonación / voz humana / realismo extremo) |
| 6 | Marca en el orbe | El logo **del cliente**, no el de QuantumHive — es su superficie de cara al público |
| 7 | Publicidad de QuantumHive | Un "Con tecnología de QuantumHive" chico, con link, dentro del panel expandido — nunca reemplaza el logo del orbe |
| 8 | Dónde vive el peso real | Servido como estático desde `livekit-quantumhive` (la VM que ya sirve `voz.quantumhive.com.ar` vía Caddy). Cacheado por el navegador, se actualiza para todos los clientes a la vez |
| 9 | Primer despliegue | La landing de QuantumHive (`www.quantumhive.com.ar`), código en `C:\Users\sergio\Desktop\boveda obsidian\landing`, servida en Cloud Run (`landing-quantumhive`), desplegada con `gcloud run deploy --source .` — no tiene CI, no está en un repo |

---

## 3. Arquitectura

```text
Página del cliente (landing, catálogo vivo, cualquier sitio)
  <script src="https://voz.quantumhive.com.ar/widget.js"
          data-tenant="quantumhive"
          data-logo="https://.../logo-del-cliente.png"   ← opcional
          defer></script>
        │
        │  loader.js: ~30 líneas. Crea un <iframe allow="microphone">
        │  posicionado fixed abajo a la derecha. Nada más.
        ▼
<iframe src="https://voz.quantumhive.com.ar/widget.html?tenant=quantumhive&logo=..."
        allow="microphone">
        │
        │  Aislado 100% del CSS/JS de la página del cliente: documento
        │  propio, origen propio.
        ▼
Orbe (Preact) — puerto de Orbe.tsx/orbe.css
        │
        ├─ POST https://voz.quantumhive.com.ar/api/token {nivel, tenant}
        │     → {token, url, sala, tenant, plan, duracion_maxima_seg}
        │
        └─ livekit-client conecta a wss://voz.quantumhive.com.ar,
           publica el micrófono, reproduce el audio del agente,
           recibe transcripción y texto por data channel (igual que
           frontend/demo/main.js, que ya hace esto mismo hoy)
```

**Por qué iframe y no Shadow DOM:** un widget que se instala en WordPress, Wix o una página armada a mano (promesa ya escrita en `docs/instalar-el-agente-en-una-landing.md`) no puede arriesgarse a que el CSS o el JS del sitio choque con el nuestro. El iframe es aislamiento real, no una convención que se puede romper. El costo — un viewport HTTP más — es aceptable para un widget que no es crítico en el primer render de la página (carga `defer`).

**Por qué el peso real vive en nuestra infraestructura:** el fragmento que el cliente pega no cambia nunca. Arreglar un bug del orbe, sumar el motor `realismo extremo` cuando esté listo, o cambiar el copy del panel — todo eso se sirve solo, sin que ningún cliente tenga que volver a pegar nada. Es el mismo principio que ya aplica `voice/agente.py` y `api/servidor.py`: una infraestructura compartida, N instalaciones.

---

## 4. Componentes nuevos

```text
frontend/widget/
  loader.js              El script de una linea que pega el cliente.
                         Lee sus propios data-* attributes, crea el
                         iframe, lo posiciona, y no hace nada mas.
                         Se sirve publicamente como widget.js — el
                         nombre que ya prometio docs/instalar-el-agente-
                         en-una-landing.md. loader.js es el nombre del
                         archivo fuente; widget.js es el nombre servido.
  widget.html             La pagina que carga adentro del iframe.
  src/
    Orbe.tsx               Puerto de orbe/Orbe.tsx de QUANTUM-ASISTENTE-.
                           Misma estructura de estados (sesion, hablando,
                           frenado, expandido), misma logica de turnos.
                           Cambia window.qh (IPC de Electron) por
                           src/conexion.ts.
    orbe.css                Puerto casi literal de orbe.css: mismo
                            lenguaje visual (esfera, animaciones de
                            estado, panel expandido). Se le agregan los
                            estilos del selector de motor y del badge
                            "Con tecnologia de QuantumHive".
    conexion.ts              Reemplaza a window.qh: pide el token a
                             /api/token, conecta con livekit-client,
                             expone los mismos eventos que Orbe.tsx ya
                             consume (alTexto, alTranscripcion, alAudio,
                             alTurnoFin, alInterrumpido, alError).
    selector-motor.tsx        Los tres botones (clonacion / voz humana /
                              realismo extremo). Vive fuera de Orbe.tsx
                              como componente propio: el original no lo
                              tiene y no hay que tocar su logica interna
                              para agregarlo.
```

Todo esto se sirve como archivos estáticos desde `livekit-quantumhive`, con un `handle` más en el `Caddyfile` (además del que ya rutea `/api/*` a la VM del agente). No toca la API ni el agente.

---

## 5. Selector de motor

Tres botones dentro del panel expandido, mapeados al catálogo de niveles que **ya existe y funciona** en `GET /api/niveles`:

| Botón | Nivel | Motor | Estado |
|---|---|---|---|
| Clonación | 1 | pipeline (Groq + Fish, voz clonada) | Anda hoy |
| Voz humana | 2 | gemini (Gemini Live) | Anda hoy |
| Realismo extremo | 3 | openai (OpenAI Realtime) | Visible, deshabilitado — falta el recurso de Azure OpenAI |

El tercero se muestra pero al tocarlo no conecta: un aviso ("Todavía no disponible") en vez de intentar y fallar. Se habilita solo — sin tocar el widget — el día que exista `AZURE_OPENAI_ENDPOINT`/`AZURE_OPENAI_DEPLOYMENT` en el `.env` de producción, porque el widget solo pregunta a `/api/niveles` qué motores están configurados; no lo tiene hardcodeado.

Cambiar de motor a mitad de conversación corta la sesión activa y arranca una sala nueva con el nivel elegido — no hay mezcla de motores dentro de una misma sala.

---

## 6. Marca por cliente

- El centro del orbe usa `data-logo` si está presente; si no, cae a las iniciales del `tenant` (o el logo por defecto de QuantumHive, en la instalación de QuantumHive mismo).
- El panel expandido, en la esquina inferior, lleva un texto chico con link: "Con tecnología de QuantumHive" → `https://www.quantumhive.com.ar`. No se puede quitar por configuración en esta primera versión — es intencional: sacarlo queda como palanca de un plan superior más adelante, no una opción de hoy.
- Cuando aterriza Supabase (Fases 5-8), `logo_url` se suma a la tabla `tenants` (la migración ya escrita en `supabase/migrations/0001_tenants_perfiles_servicios_voces.sql` todavía no se aplicó — se le agrega la columna antes de aplicarla) y el logo se resuelve del lado del servidor en vez de venir por `data-logo`. El atributo sigue funcionando como override manual.

---

## 7. Manejo de errores

Reusa el patrón que ya prueba `Orbe.tsx` en Quantum Assistant: un estado `aviso` que se muestra sin romper el resto de la UI, y un `data-estado` en el CSS con una variante por cada cosa que puede pasar.

| Falla | Comportamiento |
|---|---|
| Sin permiso de micrófono | Aviso "No me diste permiso para usar el micrófono", el orbe sigue usable por texto |
| `/api/token` no contesta o da 429/503 | "No se pudo conectar, reintentá en un momento" — nunca una pantalla en blanco |
| Tenant no existe (esperable recién con Fases 5-8) | El widget no se muestra roto: cae al comportamiento por defecto de `quantumhive` |
| Motor "realismo extremo" tocado antes de estar listo | "Todavía no disponible", no intenta conectar |
| Se llega al tope de sesión (`max_session_seconds`) | La sesión se corta sola, como ya hace el agente hoy; el panel queda abierto para arrancar una nueva |

---

## 8. Documentación y repetibilidad

`docs/instalar-el-agente-en-una-landing.md` ya existe y ya tiene la sección del `<script>` (B.4). Se **extiende**, no se reescribe:

- B.4 pasa a incluir `data-logo` como paso opcional del fragmento.
- Se agrega un paso nuevo: "B.5 — Verificar el widget" con la lista de la sección 9 de este documento, antes de la lista de verificación que ya existe (B.5 actual pasa a B.6).
- El objetivo es que instalar el widget en un cliente nuevo sea: una fila de tenant (hoy, configuración; con Fases 5-8, una fila en Supabase) + pegar el `<script>` + correr la checklist. Nada a mano por fuera de eso.

---

## 9. Verificación

1. **Local:** servir `frontend/widget/` con un servidor estático simple, pegar el `loader.js` en un HTML de prueba minimal, confirmar que el orbe aparece, conecta contra `livekit-server --dev` local, y que los tres botones están pero "realismo extremo" avisa en vez de conectar.
2. **Contra producción:** mismo HTML de prueba pero apuntando a `https://voz.quantumhive.com.ar`, con un tenant y logo de prueba.
3. **Recién después:** tocar `index.html` de la landing real (`C:\Users\sergio\Desktop\boveda obsidian\landing`), agregar el `<script>` antes de `</body>`, y redeployar con `gcloud run deploy --source .`.
4. Checklist de aceptación (adaptada de B.5/B.6 del playbook):
   - [ ] El widget aparece en desktop y en celular.
   - [ ] Pide permiso de micrófono y conecta.
   - [ ] El agente saluda solo.
   - [ ] Entiende español y se lo puede interrumpir.
   - [ ] Los tres botones de motor están visibles; clonación y voz humana conectan; realismo extremo avisa que no está listo.
   - [ ] El logo que se ve es el del `data-logo` configurado, no el de QuantumHive.
   - [ ] El "Con tecnología de QuantumHive" aparece y linkea bien.

---

## 10. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El iframe no puede pedir permiso de micrófono en algunos navegadores/embeds sin el atributo `allow` bien puesto | El widget se ve pero no escucha | `allow="microphone"` va en el iframe que crea `loader.js`, no depende de que el cliente lo configure |
| El puerto de `Orbe.tsx` a Preact introduce una diferencia sutil de comportamiento respecto al original | Estados visuales que no coinciden con lo ya validado en Quantum Assistant | Portar 1:1 primero, correr los mismos casos a mano contra el original antes de tocar el CSS |
| La landing real no tiene control de versiones | Un cambio manual se puede perder o pisar | Al tocarla, versionarla en un repo (aunque sea privado) como parte de esta tarea, no dejarla solo en Cloud Run |
| El badge "Con tecnología de QuantumHive" no configurable genera fricción con un cliente grande que lo pida sacar | Pierde un cliente por un detalle chico | Ya está anotado como palanca de upsell (sección 6); si insiste, es una decisión de negocio, no técnica |
