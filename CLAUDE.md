# Reglas de la Fábrica de Agentes

**Este repo no es el motor de voz.** Trae una copia adentro, pero lo que lo
define es la parte multi-negocio: quién es cada agente, qué sabe, con qué voz
habla y qué puede hacer. El motor aislado está en
[`SOLO-MOTOR-DE-VOZ-`](https://github.com/CEO-QUANTUMHIVE/SOLO-MOTOR-DE-VOZ-).

El paquete de Python se sigue llamando `motor_voz` por herencia: renombrarlo
toca cada import y el deploy de la VM, y no devuelve nada.


Sergio paga por tokens y el plan semanal se le va en dos días. Estas
reglas existen para eso: no son estilo, son plata.

---

> **¿Recién llegás? Empezá por [`docs/MAPA.md`](docs/MAPA.md).** Está el mapa
> de cómo encaja todo, qué existe y qué falta, y en qué orden. Cinco minutos.

## 0. ESTO ESTÁ EN PRODUCCIÓN. NO SE TOCA PARA PROBAR NADA

Este repo y su VM atienden clientes reales, ahora mismo. Cientos de sesiones
por día.

### Si viniste a usar el motor de voz para otro producto: CLONÁ, NO MODIFIQUES

El motor de voz aislado vive en su propio repositorio, y existe justamente
para esto:

> **https://github.com/CEO-QUANTUMHIVE/SOLO-MOTOR-DE-VOZ-**

Ahí está el motor solo, sin tenants ni base de datos, con su `CLAUDE.md`, sus
recetas por producto y sus trampas. Llevate una copia y adaptala en el repo de
tu producto.

**No adaptes este repo a tu producto.** Acá el motor atiende agentes
infinitos; el tuyo atiende uno. Son cosas distintas que comparten motor.

### Cómo se agrega un producto nuevo al motor — SÍ SE PUEDE

**No se comparte el `.env`. Cada producto corre su propio worker.**

Ese `.env` no es "la configuración del motor": es la del **worker de la
landing**. Agregarle `LIVEKIT_AGENT_NAME` no agrega un producto, cambia lo que
hace el worker que está atendiendo clientes ahora mismo.

Lo que se comparte es el **servidor de LiveKit**, no el archivo:

```
                voz.quantumhive.com.ar   (un solo LiveKit)
                 ↑             ↑              ↑
      worker landing   worker Quantum As.   worker Dominus
      .env propio      .env propio          .env propio
      sin AGENT_NAME   AGENT_NAME=...       AGENT_NAME=...
```

Un worker **con** `LIVEKIT_AGENT_NAME` solo atiende las salas que lo nombran.
Un worker **sin** nombre atiende las demás — ese es el de la landing, y por eso
no se le pone nombre nunca.

**La receta, sin tocar nada de lo que ya anda:**

1. Cloná `SOLO-MOTOR-DE-VOZ-` en el repo de tu producto y adaptalo.
2. Carpeta nueva en la VM (o en otra máquina), con **su propio `.env`**.
   Copiá las claves que necesites del `.env.example`, no del `.env` vivo.
3. `LIVEKIT_AGENT_NAME=tu-producto` en **ese** `.env`, nunca en el de la
   landing.
4. Servicio de systemd nuevo, con nombre propio. No toques
   `motor-voz-api` ni `motor-voz-agente`.
5. Tu producto pide el token nombrando a tu agente. Si tu worker corre el
   `api.py` del repo aislado, la clave del producto ya hace eso sola.

Pueden convivir varios en la misma VM sin pisarse. **Lo único que no se toca
es lo que ya está corriendo.**

### Prohibido, sin excepciones

- **Editar `/home/sergio/motor-voz/.env`.** Ni agregando, ni "un segundo", ni
  con backup. Agregar también rompe: `LIVEKIT_AGENT_NAME` deja al worker de la
  landing atendiendo solo salas que lo nombren, o sea ninguna.
- **Reiniciar `motor-voz-api` o `motor-voz-agente`** para probar algo.
- **Matar procesos** en la VM.
- **Levantar procesos a mano** al lado de los de systemd. Se pelean por el
  puerto 8080.

Pasó el 2026-08-11: un agente cambió tres líneas de ese `.env` para probar
Azure. No explotó de casualidad, porque los procesos ya estaban corriendo y el
`.env` solo se lee al arrancar. El primer reinicio hubiera dejado la landing
sin agente.

### Prohibido también: tocar cuentas de Meta con el navegador automatizado

**Nunca manejar Facebook, Meta Business, `developers.facebook.com` ni
WhatsApp Manager con automatización de navegador.** Ni para leer, ni "un
click", ni con la sesión ya abierta. Si hace falta algo ahí, se le dictan
los pasos a Sergio y los hace él a mano.

Pasó el 2026-08-16: un agente navegó `developers.facebook.com` automatizado.
Saltó un checkpoint, y poco después Meta deshabilitó la cuenta personal de
Sergio —de años— por "integridad de la cuenta", sin apelación. El portfolio
`QuantumHive` (`1079094061364956`) puede haber quedado inaccesible y todo el
canal de WhatsApp quedó bloqueado, con el código terminado y en verde.

Corolario: **no abrir una cuenta nueva para hacer lo que la vieja tenía
prohibido.** Meta lo llama evasión y vincula por dispositivo, IP y teléfono;
el final normal es perder las dos.

**Se recuperó por la vía limpia (2026-08-31).** Hay un portfolio nuevo y sano,
`Quantumhive` (`business_id 1339027384106629`), con la **verificación de la
empresa aprobada** — mail de Meta for Business y Centro de seguridad, "Verificada
originalmente el Aug 31, 2026". El portfolio viejo `1079094061364956` queda
abandonado; si aparece en un documento, está desactualizado. La regla de arriba
no cambia ni un punto: la cuenta se recuperó, y se pierde igual de rápido.

### Lo que sí se puede, siempre

Leer todo. Correr los tests, que no llaman a ninguna API ni gastan un peso.
Escribir código y tests, commitear y pushear. Crear tu propio worker con tu
propio `.env`, como dice la receta de arriba.

**Desplegar es otra cosa:** se hace siguiendo
[`docs/procesos/desplegar.md`](docs/procesos/desplegar.md), con sus dos reglas
duras, y no improvisando en la VM.

### Y una que aprendimos rompiéndola nosotros

**Un `voice_id` que no existe no da error: da silencio.** El agente contesta,
el LLM factura, y no se escucha nada. Si tocás voces, corré:

```bash
uv run pytest -m smoke tests/smoke/test_voces_existen.py
```

---

## 1. REGLA DURA: el grafo primero, siempre

Hay un grafo de conocimiento en `graphify-out/` que **se regenera solo en
cada commit** (hook de git), así que nunca está desactualizado. Hoy son
~600 nodos y ~810 aristas.

**Antes de buscar cualquier cosa en este repo, preguntale al grafo.**

```bash
graphify query "como se elige la voz segun el motor" --budget 700
graphify explain "catalogo_de_voces"
graphify path "AgentSession" "normalizar"
graphify affected "Config"
```

Una consulta devuelve archivo, línea, comunidad y las relaciones —
`calls`, `references`, `inherits`, `rationale_for`. Con eso ya sabés qué
archivo abrir y en qué línea. Cuesta ~700 tokens. Explorar a ciegas
cuesta cincuenta veces eso.

**Grep y leer archivos completos vienen DESPUÉS del grafo, nunca antes.**
El grafo dice dónde mirar; recién ahí se abre el archivo puntual.

### Cuándo es obligatorio, sin interpretación

Antes de la **primera** lectura o búsqueda que hagas sobre un tema, va una
consulta al grafo. Un tema nuevo = una consulta nueva. No importa que
"ya sepas dónde está": creer que sabés es exactamente el estado mental que
hace saltear el paso.

Es obligatorio antes de:

- buscar cualquier símbolo, función o archivo (`grep`, `find`, `Glob`);
- abrir un archivo que no editaste vos en esta sesión;
- responder "dónde está X" o "cómo funciona X";
- empezar cualquier bloque de trabajo nuevo.

**Lo único que no lo necesita:** archivos que creaste o editaste en esta
misma sesión, y los cuatro documentos de entrada (`CLAUDE.md`, `AGENTS.md`,
`docs/MAPA.md`, `docs/CONTINUAR-ACA.md`).

**Si el grafo no sabe, decilo y seguí.** No conoce lo que no está commiteado
—se regenera en el hook de commit— ni lo que vive en otro repo. Eso es un
resultado válido, no una excusa para saltearlo la próxima.

> **Pasó el 2026-08-15, y costó plata de verdad.** En una sesión de un día
> entero, un agente consultó el grafo dos veces y el resto lo hizo a `grep` y
> lecturas completas: `servidor.py`, `repositorio.py`, `app.js`, `motores.py`,
> varios enteros y más de una vez. Sergio lo cortó con "me tenés los huevos
> por el piso". Tenía razón: la regla estaba escrita desde el primer día y se
> ignoró igual. Por eso ahora está la lista de arriba, que no se puede
> interpretar.

**Nunca revisar el proyecto entero sin pasar por el grafo.** Si te piden
"revisá todo", empezá por `graphify query` y `graphify-out/GRAPH_REPORT.md`,
no por `find` ni por leer archivos en cadena.

Si `graphify-out/` no existe: `graphify update .`

---

## 2. Los comandos devuelven lo mínimo

Todo lo que devuelve un comando se queda en el contexto para siempre y se
recobra en cada turno siguiente. Un `journalctl -n 60` de más se paga
muchas veces.

- `grep` con patrón, no `cat` del archivo entero.
- `-n 10` antes que `-n 60`. Ampliar solo si hizo falta.
- `find` siempre con filtro; nunca `find .` a secas en un repo con
  `node_modules/` o `.venv/`.
- Leer un archivo por rangos (`offset`/`limit`) cuando ya sabés la línea
  por el grafo.
- Pedir el campo, no el JSON entero: `--format="value(...)"`,
  `--query "..."`, `-o tsv`.

---

## 3. Modelo barato para trabajo mecánico

Cuando la tarea está completamente especificada y es de ejecución —
escribir un archivo cuyo contenido ya está definido, renombrar, aplicar
un patrón repetido, correr tests y reportar— **despachar un subagente con
un modelo más barato** (`model: "sonnet"` o `"haiku"`) en vez de hacerlo
en la sesión principal.

Dos motivos: cuesta menos por token, y el contexto que gasta el subagente
es **suyo**, no de la sesión principal. Un subagente puede gastar 90k
tokens y devolver un resumen de 20 líneas.

Reservar el modelo caro para: diseño, decisiones de arquitectura,
depurar algo que no se entiende, y revisar código.

---

## 4. Avisar cuando se puede ahorrar

Si detectás que la sesión se está poniendo cara, **decilo sin que te lo
pregunten**, con la recomendación concreta:

- La conversación creció mucho y cambió de tema → sugerir cortar la
  sesión y arrancar de nuevo apuntando a `docs/CONTINUAR-ACA.md`.
- Van varias tareas mecánicas seguidas → sugerir despacharlas a
  subagentes baratos.
- Te piden explorar en vez de preguntar → sugerir la consulta al grafo
  que responde lo mismo.

No lo conviertas en sermón: una línea, la recomendación, y seguir.

**Lo que NO se recorta:** los tests y la verificación antes de decir que
algo funciona. Cuando no se verificó, el arreglo salió siempre más caro
que la verificación. Pasó el 2026-08-09: un deploy sin comparar contra lo
que estaba vivo pisó la landing de producción.

---

## 5. Cómo se hace cada cosa

Antes de grabar muestras de voz, aplicar una migración, pelearte con un 401 o
desplegar: **está escrito en [`docs/procesos/`](docs/procesos/README.md).**
Cada documento existe porque eso mismo costó horas la primera vez. Leerlo
cuesta un minuto; volver a tropezar costó una tarde.

Y al revés: **cuando resuelvas algo que costó, escribilo ahí.** Es parte del
trabajo, igual que actualizar el brief.

## 6. Lo demás

El resto de las reglas del proyecto —la frontera dura entre `brain/` y
`voice/`, los tres motores, las trampas que ya costaron horas— están en
[`AGENTS.md`](AGENTS.md).

Estado actual, qué falta y en qué orden:
[`docs/CONTINUAR-ACA.md`](docs/CONTINUAR-ACA.md). **Ese documento no se
actualiza solo:** al terminar un bloque de trabajo, actualizarlo es parte
del trabajo.
