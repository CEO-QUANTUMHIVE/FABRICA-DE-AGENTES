import test from "node:test";
import assert from "node:assert/strict";

import {
  PERFIL_QUANTUMHIVE,
  armarPiezasConocimiento,
  cerrarRecorrido,
  destinoLegible,
  editarInvestigacion,
  hallazgosGenerales,
  hallazgosPorFuente,
  integrarInvestigacion,
  instruccionDePersonalidad,
  normalizarPerfil,
  objetivosDeInvestigacion,
  perfilVacio,
  progresoDelPerfil,
  promptDesdeFicha,
  resumenDeFuentes,
  esLogoGenericoDeRed,
  esLogoRemotoAplicable,
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

test("un borrador vacío no conserva identidad ni conocimiento del negocio anterior", () => {
  const vacio = perfilVacio();
  assert.equal(vacio.nombre, "");
  assert.equal(vacio.rubro, "");
  assert.deepEqual(vacio.investigacion, {});
  assert.equal(progresoDelPerfil(vacio), 0);
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

test("una investigación nueva reemplaza datos y marca de la anterior", () => {
  const anterior = integrarInvestigacion({}, {
    negocio: { nombre: "Negocio Viejo", telefono: "111", web: "https://viejo.test" },
    servicios: ["Servicio viejo"],
    marca: { logo_url: "https://viejo.test/logo.png", colores: ["#112233"] },
  });
  const actual = integrarInvestigacion(anterior, {
    negocio: { nombre: "Negocio Nuevo", web: "https://nuevo.test" },
    servicios: ["Servicio nuevo"],
    marca: {},
  });

  assert.equal(actual.nombre, "Negocio Nuevo");
  assert.equal(actual.investigacion.negocio.telefono, undefined);
  assert.deepEqual(actual.investigacion.servicios, ["Servicio nuevo"]);
  assert.equal(actual.investigacion.marca.logo_url, undefined);
  assert.deepEqual(actual.investigacion.marca.colores, undefined);
});

test("los logos genéricos de redes nunca son aplicables", () => {
  assert.equal(esLogoGenericoDeRed("https://static.cdninstagram.com/rsrc.php/v4/yR/r/blank_profile.png"), true);
  assert.equal(esLogoGenericoDeRed("https://static.xx.fbcdn.net/rsrc.php/v3/yZ/r/default-avatar.png"), true);
  assert.equal(esLogoRemotoAplicable("https://negocio.test/logo.png"), true);
  assert.equal(esLogoRemotoAplicable("https://instagram.test/profile-icon.png"), false);
});

test("destinoLegible acorta webs y perfiles a algo mostrable", () => {
  assert.equal(destinoLegible("web", "https://www.tallernorte.com.ar/turnos"), "tallernorte.com.ar");
  assert.equal(destinoLegible("instagram", "https://instagram.com/tallernorte/"), "@tallernorte");
  assert.equal(destinoLegible("instagram", "@tallernorte"), "@tallernorte");
  assert.equal(destinoLegible("facebook", "facebook.com/tallernorte?ref=1"), "@tallernorte");
  assert.equal(destinoLegible("web", "   "), "");
});

test("solo se visita la fuente que el dueño cargó", () => {
  const objetivos = objetivosDeInvestigacion({
    web: "https://tallernorte.com.ar",
    instagram: "@tallernorte",
    facebook: "",
  });
  assert.deepEqual(objetivos.map((o) => o.clave), ["web", "instagram"]);
  assert.equal(objetivos[1].destino, "@tallernorte");
});

test("los hallazgos salen del paquete real, no se inventan", () => {
  const hallazgos = hallazgosPorFuente({
    negocio: { texto_web: "hola", tecnologias: ["wordpress"], puntuacion_google: 4.7 },
    marca: { bio_instagram: "Taller", seguidores: 1200 },
  });
  assert.deepEqual(hallazgos.web, ["leyó la página", "1 tecnologías"]);
  assert.deepEqual(hallazgos.instagram, ["bio del perfil", "1200 seguidores"]);
  assert.deepEqual(hallazgos.facebook, []);
  assert.deepEqual(hallazgos.url_maps, ["4.7 ★"]);
});

test("una fuente sin evidencia queda en sin-datos, nunca en encontrado", () => {
  const objetivos = objetivosDeInvestigacion({ web: "x.com", facebook: "@y" });
  const cerrado = cerrarRecorrido(objetivos, { negocio: { texto_web: "hola" }, marca: {} });
  assert.equal(cerrado[0].estado, "encontrado");
  assert.equal(cerrado[1].estado, "sin-datos");
  assert.deepEqual(cerrado[1].hallazgos, []);
});

test("si el Perfilador falla ninguna fuente se da por visitada", () => {
  const objetivos = objetivosDeInvestigacion({ web: "x.com", instagram: "@y" });
  const cerrado = cerrarRecorrido(objetivos, null, true);
  assert.deepEqual(cerrado.map((o) => o.estado), ["fallo", "fallo"]);
  assert.ok(cerrado.every((o) => o.hallazgos.length === 0));
});

test("el resumen de fuentes distingue encontradas, sin datos, fallos y pendientes", () => {
  assert.deepEqual(resumenDeFuentes([
    { estado: "encontrado" },
    { estado: "sin-datos" },
    { estado: "fallo" },
    {},
    { estado: "encontrado" },
  ]), { encontrado: 2, "sin-datos": 1, fallo: 1, pendiente: 1 });
});

test("los hallazgos sin fuente atribuible van aparte", () => {
  const generales = hallazgosGenerales({
    servicios: ["a", "b"],
    precios: [],
    horarios: "Lunes",
    preguntas_frecuentes: [{ pregunta: "p", respuesta: "r" }],
    marca: { logo_url: "https://x.test/l.png", colores: ["#112233"] },
  });
  assert.deepEqual(generales, ["2 servicios", "horarios", "1 preguntas frecuentes", "logo", "1 colores de marca"]);
});
