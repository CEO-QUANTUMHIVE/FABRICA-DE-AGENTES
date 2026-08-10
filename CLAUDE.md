# Reglas de este repo

Sergio paga por tokens y el plan semanal se le va en dos días. Estas
reglas existen para eso: no son estilo, son plata.

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

## 5. Lo demás

El resto de las reglas del proyecto —la frontera dura entre `brain/` y
`voice/`, los tres motores, las trampas que ya costaron horas— están en
[`AGENTS.md`](AGENTS.md).

Estado actual, qué falta y en qué orden:
[`docs/CONTINUAR-ACA.md`](docs/CONTINUAR-ACA.md). **Ese documento no se
actualiza solo:** al terminar un bloque de trabajo, actualizarlo es parte
del trabajo.
