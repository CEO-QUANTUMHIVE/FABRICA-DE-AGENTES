# Reglas de este repo

## 1. REGLA DURA: el grafo primero, siempre

Hay un grafo de conocimiento en `graphify-out/` que **se regenera solo en
cada commit** (hook de git), así que nunca está desactualizado. Hoy son
~600 nodos y ~810 aristas.

**Antes de buscar cualquier cosa en este repo, preguntale al grafo.** No es
una sugerencia: es el orden de trabajo. Abrir archivos a mano o grepear
para orientarte quema tokens al pedo, es más lento, y te hace leer cosas
que no necesitás.

```bash
graphify query "como se elige la voz segun el motor" --budget 700
graphify explain "catalogo_de_voces"
graphify path "AgentSession" "normalizar"
graphify affected "Config"
```

Una consulta devuelve archivo, línea, comunidad y las relaciones —
`calls`, `references`, `inherits`, `rationale_for`. Con eso ya sabés qué
archivo abrir y en qué línea.

**Grep y leer archivos completos vienen DESPUÉS del grafo, nunca antes.**
El grafo dice dónde mirar; recién ahí se abre el archivo puntual. Releer
el repo entero es el último recurso.

Si `graphify-out/` no existe: `graphify update .`

## 2. Lo demás

El resto de las reglas del proyecto —la frontera dura entre `brain/` y
`voice/`, los tres motores, las trampas que ya costaron horas— están en
[`AGENTS.md`](AGENTS.md). Leelo antes de tocar código.

Estado actual, qué falta y en qué orden: [`docs/CONTINUAR-ACA.md`](docs/CONTINUAR-ACA.md).
