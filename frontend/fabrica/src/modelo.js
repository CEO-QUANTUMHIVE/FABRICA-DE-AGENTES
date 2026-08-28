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

function texto(valor) {
  return String(valor || "").trim();
}

function lista(valor) {
  return Array.isArray(valor) ? valor.map(texto).filter(Boolean) : [];
}

export function integrarInvestigacion(perfil, paquete = {}) {
  const actual = normalizarPerfil(perfil);
  const investigacionActual = actual.investigacion && typeof actual.investigacion === "object"
    ? actual.investigacion
    : {};
  const negocioAnterior = investigacionActual.negocio && typeof investigacionActual.negocio === "object"
    ? investigacionActual.negocio
    : {};
  const marcaAnterior = investigacionActual.marca && typeof investigacionActual.marca === "object"
    ? investigacionActual.marca
    : {};
  const negocio = paquete?.negocio && typeof paquete.negocio === "object"
    ? { ...negocioAnterior, ...paquete.negocio }
    : negocioAnterior;
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
      marca: paquete?.marca && typeof paquete.marca === "object"
        ? { ...marcaAnterior, ...paquete.marca }
        : marcaAnterior,
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
