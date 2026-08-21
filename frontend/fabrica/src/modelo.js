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
  return [
    {
      categoria: "otro",
      clave: "fabrica-identidad",
      titulo: "Identidad de QuantumHive",
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
