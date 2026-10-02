import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// `evento.currentTarget` sólo existe mientras se despacha el evento: despues
// del primer `await` vuelve `null` y el handler revienta con
// "Cannot read properties of null". El 2026-10-02 eso dejo el login de la
// Fabrica en bucle: cargaba el tenant, tiraba en el `reset()`, el `catch`
// cerraba la sesion y el boton seguia pintado como habilitado.
//
// Cada handler tiene que guardar la referencia ANTES del primer `await`.

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const archivos = ["frontend/fabrica/src/app.js", "frontend/panel/src/app.js"];

function funcionesConCurrentTargetTardio(texto) {
  const lineas = texto.split("\n");
  const arranques = lineas
    .map((linea, indice) => (/^(export )?(async )?function \w+/.test(linea) ? indice : -1))
    .filter((indice) => indice >= 0);
  arranques.push(lineas.length);

  const fallas = [];
  for (let i = 0; i < arranques.length - 1; i += 1) {
    const inicio = arranques[i];
    const cuerpo = lineas.slice(inicio, arranques[i + 1]);
    const primerAwait = cuerpo.findIndex((linea) => linea.includes("await "));
    if (primerAwait < 0) continue;
    cuerpo.forEach((linea, j) => {
      if (j > primerAwait && linea.includes("currentTarget")) {
        fallas.push({ funcion: cuerpo[0].trim(), linea: inicio + j + 1, texto: linea.trim() });
      }
    });
  }
  return fallas;
}

for (const archivo of archivos) {
  test(`${archivo}: ningun handler usa currentTarget despues de un await`, () => {
    const texto = readFileSync(path.join(raiz, archivo), "utf8");
    const fallas = funcionesConCurrentTargetTardio(texto);
    assert.deepEqual(
      fallas.map((f) => `${f.linea} ${f.texto}`),
      [],
      `${archivo} lee currentTarget despues de await: guardalo en una variable antes`
    );
  });
}
