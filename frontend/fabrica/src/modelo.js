export const PERFIL_QUANTUMHIVE = Object.freeze({
  nombre: "QuantumHive",
  rubro: "Inteligencia artificial para negocios",
  promesa: "Le damos vida digital a cada negocio con un agente que atiende, conversa y vende.",
  publico: "Dueños de negocios que pierden consultas o ventas porque no pueden responder todo el día.",
  oferta: "Web inteligente, empleado virtual multicanal, voz, avatar y catálogo conectado.",
  objetivo: "Entender el negocio del visitante, detectar su problema principal y conseguir un contacto para continuar la propuesta.",
  limites: "No inventar precios, plazos, integraciones ni resultados. Si falta un dato, decirlo y ofrecer contacto humano.",
  energia: 82,
  empatia: 76,
  iniciativa: 94,
});

export function limitar(valor, minimo = 0, maximo = 100) {
  const numero = Number(valor);
  if (!Number.isFinite(numero)) return minimo;
  return Math.min(maximo, Math.max(minimo, Math.round(numero)));
}

export function normalizarPerfil(perfil = {}) {
  return {
    ...PERFIL_QUANTUMHIVE,
    ...perfil,
    energia: limitar(perfil.energia ?? PERFIL_QUANTUMHIVE.energia),
    empatia: limitar(perfil.empatia ?? PERFIL_QUANTUMHIVE.empatia),
    iniciativa: limitar(perfil.iniciativa ?? PERFIL_QUANTUMHIVE.iniciativa),
  };
}

/** Un borrador vacío para iniciar otro negocio en este equipo. */
export function perfilVacio() {
  return normalizarPerfil({
    nombre: "",
    rubro: "",
    publico: "",
    oferta: "",
    promesa: "",
    objetivo: "",
    limites: "",
    investigacion: {},
  });
}

function texto(valor) {
  return String(valor || "").trim();
}

function lista(valor) {
  return Array.isArray(valor) ? valor.map(texto).filter(Boolean) : [];
}

/** Evita que una red entregue su avatar o ícono genérico como logo del negocio. */
export function esLogoGenericoDeRed(valor) {
  try {
    const url = new URL(String(valor || ""));
    const host = url.hostname.toLowerCase();
    const ruta = url.pathname.toLowerCase();
    return ruta.includes("/rsrc.php")
      || /(?:default|generic|placeholder|avatar|profile[_-]?icon|instagram[_-]?icon)/i.test(ruta)
      || host === "static.cdninstagram.com"
      || host.endsWith(".cdninstagram.com") && ruta.startsWith("/rsrc.php");
  } catch {
    return false;
  }
}

export function esLogoRemotoAplicable(valor) {
  return /^https:\/\//i.test(valor || "") && !esLogoGenericoDeRed(valor);
}

function marcaAplicable(marca) {
  if (!marca || typeof marca !== "object") return {};
  const resultado = { ...marca };
  if (esLogoGenericoDeRed(resultado.logo_url)) delete resultado.logo_url;
  return resultado;
}

export function integrarInvestigacion(perfil, paquete = {}) {
  const actual = normalizarPerfil(perfil);
  const negocio = paquete?.negocio && typeof paquete.negocio === "object"
    ? { ...paquete.negocio }
    : {};
  const servicios = lista(paquete?.servicios);
  const precios = lista(paquete?.precios);
  const ofertaEncontrada = [
    servicios.length ? `Servicios: ${servicios.join(", ")}` : "",
    precios.length ? `Precios publicados: ${precios.join(", ")}` : "",
  ].filter(Boolean).join("\n");
  return normalizarPerfil({
    ...actual,
    nombre: texto(negocio.nombre) || actual.nombre,
    rubro: texto(negocio.categoria) || actual.rubro,
    oferta: ofertaEncontrada || actual.oferta,
    investigacion: {
      negocio,
      servicios,
      precios,
      horarios: texto(paquete?.horarios),
      preguntas_frecuentes: Array.isArray(paquete?.preguntas_frecuentes) ? paquete.preguntas_frecuentes : [],
      marca: marcaAplicable(paquete?.marca),
      competidores: lista(paquete?.competidores),
    },
  });
}

export function editarInvestigacion(perfil, cambios = {}) {
  const actual = normalizarPerfil(perfil);
  const investigacion = actual.investigacion && typeof actual.investigacion === "object"
    ? actual.investigacion
    : {};
  const negocio = investigacion.negocio && typeof investigacion.negocio === "object"
    ? investigacion.negocio
    : {};
  return integrarInvestigacion(actual, {
    ...investigacion,
    ...cambios,
    negocio: {
      ...negocio,
      ...(cambios.negocio && typeof cambios.negocio === "object" ? cambios.negocio : {}),
    },
    servicios: Object.hasOwn(cambios, "servicios") ? cambios.servicios : investigacion.servicios,
    precios: Object.hasOwn(cambios, "precios") ? cambios.precios : investigacion.precios,
    horarios: Object.hasOwn(cambios, "horarios") ? cambios.horarios : investigacion.horarios,
    preguntas_frecuentes: Object.hasOwn(cambios, "preguntas_frecuentes")
      ? cambios.preguntas_frecuentes
      : investigacion.preguntas_frecuentes,
  });
}

function nivel(valor, bajo, medio, alto) {
  if (valor >= 75) return alto;
  if (valor >= 40) return medio;
  return bajo;
}

export function instruccionDePersonalidad(perfil) {
  const p = normalizarPerfil(perfil);
  const energia = nivel(
    p.energia,
    "Habla con calma y deja espacio para pensar.",
    "Habla con energía equilibrada y cambia el ritmo según la conversación.",
    "Habla con entusiasmo visible, sin atropellar ni sonar desesperado.",
  );
  const empatia = nivel(
    p.empatia,
    "Prioriza claridad y decisiones concretas.",
    "Reconoce lo que vive la persona antes de proponer una solución.",
    "Escucha con mucha atención, reacciona a los detalles y hace sentir comprendida a la persona.",
  );
  const iniciativa = nivel(
    p.iniciativa,
    "Responde solamente lo necesario y evita presionar.",
    "Responde y suma una pregunta útil para avanzar.",
    "Lleva la conversación: pregunta, propone el siguiente paso y nunca deja al visitante sin rumbo.",
  );
  return `${energia} ${empatia} ${iniciativa}`;
}

export function armarPiezasConocimiento(perfil) {
  const p = normalizarPerfil(perfil);
  const piezas = [
    {
      categoria: "otro",
      clave: "fabrica-identidad",
      titulo: `Identidad de ${p.nombre}`,
      contenido: { nombre: p.nombre, rubro: p.rubro, promesa: p.promesa },
    },
    {
      categoria: "servicio",
      clave: "fabrica-oferta",
      titulo: "Oferta principal",
      contenido: { servicios: p.oferta, publico: p.publico },
    },
    {
      categoria: "politica",
      clave: "fabrica-objetivo",
      titulo: "Objetivo de cada conversación",
      contenido: { instruccion: p.objetivo },
    },
    {
      categoria: "tono",
      clave: "fabrica-personalidad",
      titulo: "Personalidad conversacional",
      contenido: {
        energia: p.energia,
        empatia: p.empatia,
        iniciativa: p.iniciativa,
        instruccion: instruccionDePersonalidad(p),
      },
    },
    {
      categoria: "politica",
      clave: "fabrica-limites",
      titulo: "Límites y derivación humana",
      contenido: { instruccion: p.limites },
    },
  ];
  const investigacion = p.investigacion;
  if (!investigacion || typeof investigacion !== "object") return piezas;

  const negocio = investigacion.negocio && typeof investigacion.negocio === "object"
    ? investigacion.negocio
    : {};
  const marca = investigacion.marca && typeof investigacion.marca === "object"
    ? investigacion.marca
    : {};
  const datosPublicos = Object.fromEntries(Object.entries({
    direccion: negocio.direccion,
    ciudad: negocio.ciudad,
    telefono: negocio.telefono,
    whatsapp: negocio.whatsapp,
    email: negocio.email,
    web: negocio.web,
    instagram: negocio.instagram,
    facebook: negocio.facebook,
    url_maps: negocio.url_maps,
  }).filter(([, valor]) => texto(valor)));
  if (Object.keys(datosPublicos).length || texto(marca.logo_url) || lista(marca.colores).length) {
    piezas.push({
      categoria: "otro",
      clave: "fabrica-datos-publicos",
      titulo: "Datos públicos y marca",
      contenido: { ...datosPublicos, marca: { logo_url: marca.logo_url || "", colores: lista(marca.colores) } },
    });
  }
  if (lista(investigacion.servicios).length) {
    piezas.push({
      categoria: "servicio",
      clave: "fabrica-servicios-investigados",
      titulo: "Servicios encontrados en fuentes públicas",
      contenido: { servicios: lista(investigacion.servicios) },
    });
  }
  if (lista(investigacion.precios).length) {
    piezas.push({
      categoria: "precio",
      clave: "fabrica-precios-investigados",
      titulo: "Precios publicados",
      contenido: { precios: lista(investigacion.precios) },
    });
  }
  if (texto(investigacion.horarios)) {
    piezas.push({
      categoria: "horario",
      clave: "fabrica-horarios-investigados",
      titulo: "Horarios publicados",
      contenido: { horarios: texto(investigacion.horarios) },
    });
  }
  if (Array.isArray(investigacion.preguntas_frecuentes) && investigacion.preguntas_frecuentes.length) {
    piezas.push({
      categoria: "faq",
      clave: "fabrica-faq-investigadas",
      titulo: "Preguntas frecuentes encontradas",
      contenido: { preguntas: investigacion.preguntas_frecuentes },
    });
  }
  return piezas;
}

export function slugDeNombre(nombre) {
  return String(nombre || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 63);
}

export function promptDesdeFicha(ficha) {
  const p = normalizarPerfil(ficha);
  return [
    `Sos el agente receptor de ${p.nombre}.`,
    `El negocio se dedica a: ${p.rubro}.`,
    `Ayuda a: ${p.publico}.`,
    `Su oferta es: ${p.oferta}.`,
    `Su promesa es: ${p.promesa}.`,
    `Objetivo de la conversación: ${p.objetivo}.`,
    `Límites: ${p.limites}.`,
    instruccionDePersonalidad(p),
  ].join("\n");
}

export function progresoDelPerfil(perfil) {
  const p = normalizarPerfil(perfil);
  const campos = [
    [p.nombre, 2],
    [p.rubro, 6],
    [p.promesa, 12],
    [p.publico, 12],
    [p.oferta, 12],
    [p.objetivo, 12],
    [p.limites, 12],
  ];
  const completos = campos.filter(([valor, minimo]) => String(valor || "").trim().length >= minimo).length;
  return Math.round((completos / campos.length) * 100);
}

/* ── El recorrido del investigador ──────────────────────────────────────────
   Lo que se ve en pantalla mientras el Perfilador trabaja. La animación marca
   el ritmo, pero los hallazgos NO se inventan: cada uno sale de un campo real
   del paquete que devolvió el servicio. Una fuente sin evidencia queda en
   "sin datos", nunca en verde.
   ────────────────────────────────────────────────────────────────────────── */

export const FUENTES_INVESTIGACION = Object.freeze([
  Object.freeze({ clave: "web", etiqueta: "Sitio web", icono: "🌐" }),
  Object.freeze({ clave: "instagram", etiqueta: "Instagram", icono: "◉" }),
  Object.freeze({ clave: "facebook", etiqueta: "Facebook", icono: "f" }),
  Object.freeze({ clave: "url_maps", etiqueta: "Google Maps", icono: "◈" }),
]);

/** Convierte lo que escribió el dueño en algo corto y legible para el visor. */
export function destinoLegible(clave, valor) {
  const crudo = String(valor || "").trim();
  if (!crudo) return "";
  if (clave === "instagram" || clave === "facebook") {
    const usuario = crudo
      .replace(/^https?:\/\//i, "")
      .replace(/^(www\.)?(instagram|facebook|fb)\.com\//i, "")
      .replace(/^@/, "")
      .split(/[/?#]/)[0]
      .trim();
    return usuario ? `@${usuario}` : "";
  }
  const dominio = crudo
    .replace(/^https?:\/\//i, "")
    .replace(/^www\./i, "")
    .split(/[/?#]/)[0]
    .trim();
  return dominio;
}

/** Las fuentes que el dueño realmente cargó. Sin dato no hay visita. */
export function objetivosDeInvestigacion(entradas = {}) {
  return FUENTES_INVESTIGACION.map((fuente) => ({
    ...fuente,
    destino: destinoLegible(fuente.clave, entradas[fuente.clave]),
  })).filter((fuente) => Boolean(fuente.destino));
}

/** Qué se encontró en cada fuente, leído del paquete real. */
export function hallazgosPorFuente(paquete = {}) {
  const negocio = paquete?.negocio || {};
  const marca = paquete?.marca || {};
  const hallazgos = { web: [], instagram: [], facebook: [], url_maps: [] };

  if (negocio.texto_web) hallazgos.web.push("leyó la página");
  if (negocio.web_funciona === false) hallazgos.web.push("la web no responde");
  if (Array.isArray(negocio.tecnologias) && negocio.tecnologias.length) {
    hallazgos.web.push(`${negocio.tecnologias.length} tecnologías`);
  }
  if (negocio.tiene_chatbot) hallazgos.web.push("ya tiene chatbot");
  if (negocio.tiene_reservas_online) hallazgos.web.push("reservas online");

  if (marca.bio_instagram) hallazgos.instagram.push("bio del perfil");
  if (typeof marca.seguidores === "number") {
    hallazgos.instagram.push(`${marca.seguidores} seguidores`);
  }

  if (marca.descripcion_facebook) hallazgos.facebook.push("descripción de la página");

  if (typeof negocio.puntuacion_google === "number") {
    hallazgos.url_maps.push(`${negocio.puntuacion_google} ★`);
  }
  if (typeof negocio.cantidad_resenas === "number") {
    hallazgos.url_maps.push(`${negocio.cantidad_resenas} reseñas`);
  }
  if (negocio.direccion) hallazgos.url_maps.push("dirección");

  return hallazgos;
}

/**
 * Cierra el recorrido con lo que de verdad volvió.
 * `fallo` marca todas las fuentes como no alcanzadas: si el servicio se cayó,
 * ninguna se puede dar por visitada.
 */
export function cerrarRecorrido(objetivos = [], paquete = null, fallo = false) {
  const hallazgos = fallo ? {} : hallazgosPorFuente(paquete || {});
  return objetivos.map((objetivo) => {
    if (fallo) return { ...objetivo, estado: "fallo", hallazgos: [] };
    const encontrados = hallazgos[objetivo.clave] || [];
    return {
      ...objetivo,
      estado: encontrados.length ? "encontrado" : "sin-datos",
      hallazgos: encontrados,
    };
  });
}

export function resumenDeFuentes(objetivos = []) {
  return objetivos.reduce((resumen, objetivo) => {
    const estado = objetivo.estado || "pendiente";
    if (Object.hasOwn(resumen, estado)) resumen[estado] += 1;
    return resumen;
  }, { encontrado: 0, "sin-datos": 0, fallo: 0, pendiente: 0 });
}

/** Lo que se encontró pero no se le puede atribuir a una fuente puntual. */
export function hallazgosGenerales(paquete = {}) {
  const generales = [];
  const servicios = paquete?.servicios || [];
  const precios = paquete?.precios || [];
  const preguntas = paquete?.preguntas_frecuentes || [];
  if (servicios.length) generales.push(`${servicios.length} servicios`);
  if (precios.length) generales.push(`${precios.length} precios`);
  if (paquete?.horarios) generales.push("horarios");
  if (preguntas.length) generales.push(`${preguntas.length} preguntas frecuentes`);
  if (paquete?.marca?.logo_url) generales.push("logo");
  const colores = paquete?.marca?.colores || [];
  if (colores.length) generales.push(`${colores.length} colores de marca`);
  return generales;
}
