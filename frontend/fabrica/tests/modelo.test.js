import test from "node:test";
import assert from "node:assert/strict";

import {
  PERFIL_QUANTUMHIVE,
  armarPiezasConocimiento,
  editarInvestigacion,
  integrarInvestigacion,
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

test("la investigación completa identidad, oferta y piezas verificables", () => {
  const perfil = integrarInvestigacion(
    { nombre: "Borrador", rubro: "Sin definir", oferta: "Sin definir" },
    {
      negocio: {
        nombre: "Taller Norte",
        categoria: "Mecánica",
        whatsapp: "+5491112345678",
        web: "https://taller.test",
      },
      servicios: ["Service", "Frenos"],
      precios: ["Service desde $10"],
      horarios: "Lunes a viernes",
      preguntas_frecuentes: [{ pregunta: "¿Dan turnos?", respuesta: "Sí" }],
      marca: { logo_url: "https://taller.test/logo.png", colores: ["#112233"] },
      competidores: ["Taller Sur"],
    },
  );

  assert.equal(perfil.nombre, "Taller Norte");
  assert.equal(perfil.rubro, "Mecánica");
  assert.match(perfil.oferta, /Service/);
  const piezas = armarPiezasConocimiento(perfil);
  assert.equal(piezas.length, 10);
  assert.ok(piezas.some((pieza) => pieza.categoria === "faq"));
  assert.ok(piezas.some((pieza) => pieza.clave === "fabrica-datos-publicos"));
  assert.ok(!piezas.some((pieza) => JSON.stringify(pieza).includes("Taller Sur")));
});

test("el dueño puede corregir los hallazgos antes de publicarlos", () => {
  const investigado = integrarInvestigacion({}, {
    negocio: { nombre: "Taller Norte", web: "https://vieja.test", telefono: "111" },
    servicios: ["Service"],
    precios: ["$10"],
    horarios: "Lunes",
    preguntas_frecuentes: [],
    marca: { logo_url: "https://vieja.test/logo.png", colores: ["#112233"] },
  });
  const corregido = editarInvestigacion(investigado, {
    negocio: { web: "https://nueva.test", telefono: "222", instagram: "@tallernorte" },
    servicios: ["Service completo", "Frenos"],
    precios: [],
    horarios: "Lunes a sábado",
    preguntas_frecuentes: [{ pregunta: "¿Dan turnos?", respuesta: "Sí" }],
  });

  assert.equal(corregido.investigacion.negocio.web, "https://nueva.test");
  assert.equal(corregido.investigacion.negocio.telefono, "222");
  assert.equal(corregido.investigacion.negocio.instagram, "@tallernorte");
  assert.deepEqual(corregido.investigacion.servicios, ["Service completo", "Frenos"]);
  assert.deepEqual(corregido.investigacion.precios, []);
  assert.equal(corregido.investigacion.marca.logo_url, "https://vieja.test/logo.png");
  assert.ok(armarPiezasConocimiento(corregido).some((pieza) => pieza.categoria === "faq"));
});
