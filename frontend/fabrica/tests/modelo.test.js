import test from "node:test";
import assert from "node:assert/strict";

import {
  PERFIL_QUANTUMHIVE,
  armarPiezasConocimiento,
  instruccionDePersonalidad,
  normalizarPerfil,
  progresoDelPerfil,
  promptDesdeFicha,
  slugDeNombre,
} from "../src/modelo.js";

test("QuantumHive nace con una ficha completa", () => {
  assert.equal(progresoDelPerfil(PERFIL_QUANTUMHIVE), 100);
  assert.match(PERFIL_QUANTUMHIVE.promesa, /vida digital/i);
});

test("el entrenamiento genera piezas versionables y claves estables", () => {
  const piezas = armarPiezasConocimiento(PERFIL_QUANTUMHIVE);
  assert.equal(piezas.length, 5);
  assert.equal(new Set(piezas.map((pieza) => pieza.clave)).size, piezas.length);
  assert.ok(piezas.every((pieza) => pieza.clave.startsWith("fabrica-")));
  const permitidas = new Set(["horario", "precio", "servicio", "politica", "faq", "tono", "otro"]);
  assert.ok(piezas.every((pieza) => permitidas.has(pieza.categoria)));
});

test("la ficha se convierte en un slug y un prompt de agente", () => {
  assert.equal(slugDeNombre("Óptica Sergio & Hijos"), "optica-sergio-hijos");
  const prompt = promptDesdeFicha({ nombre: "Óptica Sergio", rubro: "Óptica" });
  assert.match(prompt, /agente receptor de Óptica Sergio/i);
  assert.match(prompt, /Óptica/i);
});

test("los controles de personalidad se normalizan", () => {
  const perfil = normalizarPerfil({ energia: 500, empatia: -10, iniciativa: "50" });
  assert.equal(perfil.energia, 100);
  assert.equal(perfil.empatia, 0);
  assert.equal(perfil.iniciativa, 50);
  assert.match(instruccionDePersonalidad(perfil), /entusiasmo/i);
});
