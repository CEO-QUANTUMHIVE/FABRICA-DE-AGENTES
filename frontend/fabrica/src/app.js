import { createClient } from "@supabase/supabase-js";
import { Room, RoomEvent, Track } from "livekit-client";
import "./app.css";
import {
  PERFIL_QUANTUMHIVE,
  armarPiezasConocimiento,
  cerrarRecorrido,
  editarInvestigacion,
  hallazgosGenerales,
  integrarInvestigacion,
  normalizarPerfil,
  objetivosDeInvestigacion,
  perfilVacio,
  promptDesdeFicha,
  progresoDelPerfil,
  resumenDeFuentes,
  esLogoGenericoDeRed,
  esLogoRemotoAplicable,
  slugDeNombre,
} from "./modelo.js";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || "";
const configurado = Boolean(API_URL && SUPABASE_URL && SUPABASE_ANON_KEY);
const supabase = configurado ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null;
const STORAGE_KEY = "quantumhive:fabrica:perfil:v1";
const LOGO_STORAGE_KEY = "quantumhive:fabrica:logo:v1";
const COLORES_STORAGE_KEY = "quantumhive:fabrica:colores:v1";
const CAMPOS_ENTREVISTA = ["nombre", "rubro", "publico", "oferta", "promesa", "objetivo", "limites"];
const PREGUNTAS_ENTREVISTA = {
  nombre: "¿Cómo se llama el negocio o el agente?",
  rubro: "¿A qué se dedica el negocio?",
  publico: "¿A qué tipo de cliente ayuda principalmente?",
  oferta: "¿Qué productos o servicios ofrece?",
  promesa: "¿Qué resultado concreto promete?",
  objetivo: "¿Qué debería lograr el agente en cada conversación?",
  limites: "¿Qué no debe inventar y cuándo debe derivar a una persona?",
};
const MOTOR_DE_NIVEL = { 1: "pipeline", 2: "gemini", 3: "openai" };
const NIVEL_DE_MOTOR = { pipeline: 1, gemini: 2, openai: 3 };
const preescucha = new Audio();

const state = {
  perfil: cargarPerfilLocal(),
  logo: cargarLogoLocal(),
  colores: cargarColoresLocal(),
  perfiladorDisponible: null,
  session: null,
  tenant: null,
  conocimiento: [],
  whatsapp: null,
  whatsappDisponible: true,
  whatsappOnboarding: null,
  whatsappAlta: { code: "", waba_id: "", phone_number_id: "", completando: false },
  scout: { objetivos: [], activo: -1, corriendo: false, generales: [], reloj: null },
  publicando: false,
  voz: {
    motor: "pipeline",
    catalogo: [],
    seleccion: "",
    sala: null,
    conectando: false,
    temporizador: null,
  },
  entrevista: {
    ficha: {},
    campo: "nombre",
    progreso: 0,
    mensajes: [
      { rol: "assistant", texto: "Vamos a fabricar tu agente paso a paso. ¿Cómo se llama el negocio o el agente?" },
    ],
  },
  mensajes: [
    {
      rol: "assistant",
      texto: "Soy el agente de QuantumHive conectado al brain real. Publicá el entrenamiento y preguntame como lo haría un posible cliente.",
    },
  ],
};

function cargarPerfilLocal() {
  try {
    return normalizarPerfil(JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"));
  } catch {
    return normalizarPerfil(PERFIL_QUANTUMHIVE);
  }
}

function cargarLogoLocal() {
  const valor = localStorage.getItem(LOGO_STORAGE_KEY) || "";
  if (esLogoGenericoDeRed(valor)) {
    localStorage.removeItem(LOGO_STORAGE_KEY);
    localStorage.removeItem(COLORES_STORAGE_KEY);
    return "";
  }
  return /^(data:image\/(png|jpeg|webp);base64,|https:\/\/)/i.test(valor) ? valor : "";
}

function cargarColoresLocal() {
  try {
    const colores = JSON.parse(localStorage.getItem(COLORES_STORAGE_KEY) || "[]");
    return Array.isArray(colores)
      ? colores.filter((color) => /^#[0-9a-f]{6}$/i.test(color)).slice(0, 4)
      : [];
  } catch {
    return [];
  }
}

function iniciales(nombre = "") {
  const partes = String(nombre).trim().split(/\s+/).filter(Boolean).slice(0, 2);
  return (partes.map((parte) => parte[0]).join("") || "QH").toUpperCase();
}

function escapeHtml(valor = "") {
  return String(valor).replace(
    /[&<>'"]/g,
    (caracter) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[caracter],
  );
}

function lineas(valor = "") {
  return String(valor).split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function preguntasDesdeTexto(valor = "") {
  return lineas(valor).map((linea) => {
    const [pregunta, ...respuesta] = linea.split("|");
    return { pregunta: pregunta.trim(), respuesta: respuesta.join("|").trim() };
  }).filter((item) => item.pregunta && item.respuesta);
}

function textoDePreguntas(preguntas = []) {
  return (Array.isArray(preguntas) ? preguntas : [])
    .map((item) => `${item?.pregunta || ""} | ${item?.respuesta || ""}`)
    .filter((item) => item !== " | ")
    .join("\n");
}

function plantilla() {
  const p = state.perfil;
  const investigacion = p.investigacion && typeof p.investigacion === "object" ? p.investigacion : {};
  const negocioInvestigado = investigacion.negocio && typeof investigacion.negocio === "object"
    ? investigacion.negocio
    : {};
  const tieneInvestigacion = Boolean(
    Object.values(negocioInvestigado).some(Boolean)
    || investigacion.servicios?.length
    || investigacion.precios?.length
    || investigacion.horarios
    || investigacion.preguntas_frecuentes?.length,
  );
  return `
    <div class="ambient ambient--cyan"></div>
    <div class="ambient ambient--violet"></div>
    <div class="hex-field" aria-hidden="true"></div>

    <header class="topbar">
      <a class="brand" href="#laboratorio" aria-label="QuantumHive Fábrica de Agentes">
        <span class="hive-mark" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span>
        <span><strong>QUANTUM HIVE</strong><small>Fábrica de agentes</small></span>
      </a>
      <div class="topbar__center">
        <span class="batch">CLIENTE 001</span>
        <strong>QuantumHive</strong>
        <span class="live-dot">tenant activo</span>
      </div>
      <button class="ghost-button" id="session-button" type="button">Ingresar</button>
    </header>

    <nav class="process-nav" aria-label="Etapas de fabricación">
      <a href="#identidad"><span>01</span> Identidad</a>
      <a href="#personalidad"><span>02</span> Personalidad</a>
      <a href="#conocimiento"><span>03</span> Conocimiento</a>
      <a href="#prueba"><span>04</span> Prueba</a>
      <a href="#whatsapp"><span>05</span> WhatsApp</a>
    </nav>

    <main id="laboratorio" class="factory-shell">
      <section class="control-column control-column--left">
        <article class="glass-card identity-card" id="identidad">
          <header class="card-heading">
            <span class="module-number">MÓDULO 01</span>
            <h2>Identidad</h2>
            <span class="card-status">base activa</span>
          </header>
          <label class="field-label">Nombre del agente o negocio
            <input data-profile="nombre" value="${escapeHtml(p.nombre)}" maxlength="80" />
          </label>
          <label class="field-label">Qué es
            <input data-profile="rubro" value="${escapeHtml(p.rubro)}" maxlength="160" />
          </label>
          <label class="field-label">Promesa principal
            <textarea data-profile="promesa" rows="4" maxlength="500">${escapeHtml(p.promesa)}</textarea>
          </label>
          <div class="logo-loader">
            <div class="logo-loader__preview">
              <img id="logo-preview" alt="Logo cargado" ${state.logo ? `src="${escapeHtml(state.logo)}"` : "hidden"} />
              <span id="logo-preview-fallback" ${state.logo ? "hidden" : ""}>${escapeHtml(iniciales(p.nombre))}</span>
            </div>
            <div>
              <strong>Logo de la marca</strong>
              <small id="logo-message">PNG, JPG o WebP. Se convierte en el orbe central.</small>
              <label class="logo-loader__button" for="logo-input">Cargar imagen</label>
              <input id="logo-input" type="file" accept="image/png,image/jpeg,image/webp" hidden />
              <button id="logo-remove" class="text-button" type="button" ${state.logo ? "" : "hidden"}>Quitar</button>
            </div>
          </div>
        </article>

        <article class="glass-card personality-card" id="personalidad">
          <header class="card-heading">
            <span class="module-number">MÓDULO 02</span>
            <h2>Personalidad</h2>
            <span class="card-status">conducta</span>
          </header>
          ${controlRango("energia", "Energía", p.energia)}
          ${controlRango("empatia", "Empatía", p.empatia)}
          ${controlRango("iniciativa", "Iniciativa", p.iniciativa)}
          <p class="microcopy">Estos controles se convierten en instrucciones concretas. No son adjetivos decorativos.</p>
        </article>
      </section>

      <section class="core-column" aria-label="Núcleo del agente">
        <div class="core-label"><span></span> NÚCLEO DE FABRICACIÓN <span></span></div>
        <div class="agent-vat" id="agent-vat">
          <div class="vat-cap"><i></i><i></i><i></i></div>
          <div class="energy-ring energy-ring--one"></div>
          <div class="energy-ring energy-ring--two"></div>
          <div class="energy-ring energy-ring--three"></div>
          <div class="brand-orb" id="brand-orb" aria-label="Orbe de la marca">
            <div class="brand-orb__halo"></div>
            <div class="brand-orb__logo">
              <img id="orb-logo" alt="" ${state.logo ? `src="${escapeHtml(state.logo)}"` : "hidden"} />
              <span id="orb-fallback" ${state.logo ? "hidden" : ""}>${escapeHtml(iniciales(p.nombre))}</span>
            </div>
            <small>IDENTIDAD DE MARCA</small>
          </div>
          <div class="scan-line"></div>
          <div class="vat-glass"></div>
          <div class="vat-base">
            <div class="core-readout">
              <span id="core-percent">${progresoDelPerfil(p)}%</span>
              <small id="core-state">DISEÑO LOCAL</small>
            </div>
          </div>
        </div>
        <div class="agent-nameplate">
          <small>AGENTE RECEPTOR</small>
          <h1 id="agent-name">${escapeHtml(p.nombre)}</h1>
          <p id="agent-promise">${escapeHtml(p.promesa)}</p>
        </div>
        <div class="core-actions">
          <button class="primary-button" id="prepare-button" type="button"><span>✦</span> Preparar entrenamiento</button>
          <button class="secondary-button" id="voice-test-core" type="button">Hablar con el agente</button>
        </div>
        <p class="system-message" id="system-message">Tu diseño se guarda en este equipo. Para publicarlo en el agente real, ingresá con tu cuenta.</p>
      </section>

      <section class="control-column control-column--right">
        <article class="glass-card voice-card">
          <header class="card-heading">
            <span class="module-number">SALIDA</span>
            <h2>Voz</h2>
            <span class="card-status card-status--cyan">conectada</span>
          </header>
          <div class="waveform" aria-hidden="true">${Array.from({ length: 34 }, (_, i) => `<i style="--wave:${18 + ((i * 23) % 65)}%"></i>`).join("")}</div>
          <label class="field-label">Nivel de experiencia
            <select id="voice-level">
              <option value="pipeline">Nivel uno · voz clonada</option>
              <option value="gemini">Nivel dos · voz natural</option>
              <option value="openai">Nivel tres · voz premium</option>
            </select>
          </label>
          <div class="voice-catalog" id="voice-catalog" aria-live="polite"></div>
          <button class="voice-live-button" id="voice-live-button" type="button"><span></span> Probar agente con micrófono</button>
          <div class="voice-meta"><span id="voice-name">Voz Fish del negocio</span><strong id="voice-state">LISTA</strong></div>
          <p class="voice-message" id="voice-message">Fish usa la voz clonada aprobada de este negocio. La prueba conecta con el motor real.</p>
        </article>

        <article class="glass-card knowledge-card" id="conocimiento">
          <header class="card-heading">
            <span class="module-number">MÓDULO 03</span>
            <h2>Conocimiento</h2>
            <span class="card-status">versionado</span>
          </header>
          <label class="field-label">A quién ayudamos
            <textarea data-profile="publico" rows="3" maxlength="600">${escapeHtml(p.publico)}</textarea>
          </label>
          <label class="field-label">Qué ofrecemos
            <textarea data-profile="oferta" rows="4" maxlength="800">${escapeHtml(p.oferta)}</textarea>
          </label>
          <label class="field-label">Objetivo de la conversación
            <textarea data-profile="objetivo" rows="4" maxlength="800">${escapeHtml(p.objetivo)}</textarea>
          </label>
          <details class="limits-details">
            <summary>Límites y derivación humana</summary>
            <textarea data-profile="limites" rows="4" maxlength="800">${escapeHtml(p.limites)}</textarea>
          </details>
        </article>
      </section>

      <section class="onboarding-console" id="autoguiado">
        <div class="test-console__copy">
          <span class="module-number">AUTOGUIADO · BRAIN QUANTUMHIVE</span>
          <h2>Contale tu negocio al agente</h2>
          <p>Podés darle la web y las redes para que investigue primero. Después el brain solamente te pregunta lo que no pudo encontrar.</p>
          <form class="research-box" id="research-form">
            <strong>Investigar fuentes públicas</strong>
            <div class="research-grid">
              <input name="web" type="text" inputmode="url" value="${escapeHtml(negocioInvestigado.web || "")}" placeholder="Web del negocio" />
              <input name="instagram" value="${escapeHtml(negocioInvestigado.instagram || "")}" placeholder="Instagram: @usuario o URL" />
              <input name="facebook" value="${escapeHtml(negocioInvestigado.facebook || "")}" placeholder="Facebook: usuario o URL" />
              <input name="url_maps" type="text" inputmode="url" value="${escapeHtml(negocioInvestigado.url_maps || "")}" placeholder="Google Maps (opcional)" />
            </div>
            <button class="secondary-button" id="research-button" type="submit">✦ Investigar mi negocio</button>
            <button class="text-button research-reset-button" id="new-research-button" type="button">Empezar otro negocio</button>
            <small id="research-message">El token y los scrapers corren en el servidor; nunca llegan a tu navegador.</small>
            <details class="research-review" id="research-review" ${tieneInvestigacion ? "open" : ""}>
              <summary>Revisar o cargar los datos que aprenderá el agente</summary>
              <p>Podés completar esto a mano aunque la investigación automática todavía no esté conectada.</p>
              <div class="research-grid research-grid--contact">
                <input name="direccion" value="${escapeHtml(negocioInvestigado.direccion || "")}" placeholder="Dirección" />
                <input name="ciudad" value="${escapeHtml(negocioInvestigado.ciudad || "")}" placeholder="Ciudad" />
                <input name="telefono" value="${escapeHtml(negocioInvestigado.telefono || "")}" placeholder="Teléfono" />
                <input name="whatsapp" value="${escapeHtml(negocioInvestigado.whatsapp || "")}" placeholder="WhatsApp" />
                <input name="email" type="email" value="${escapeHtml(negocioInvestigado.email || "")}" placeholder="Correo" />
              </div>
              <label>Servicios <textarea name="servicios" rows="4" placeholder="Uno por línea">${escapeHtml((investigacion.servicios || []).join("\n"))}</textarea></label>
              <label>Precios publicados <textarea name="precios" rows="3" placeholder="Uno por línea; dejalo vacío si no querés publicar precios">${escapeHtml((investigacion.precios || []).join("\n"))}</textarea></label>
              <label>Horarios <textarea name="horarios" rows="2" placeholder="Ejemplo: lunes a viernes de 9 a 18">${escapeHtml(investigacion.horarios || "")}</textarea></label>
              <label>Preguntas frecuentes <textarea name="preguntas_frecuentes" rows="4" placeholder="Una por línea: Pregunta | Respuesta">${escapeHtml(textoDePreguntas(investigacion.preguntas_frecuentes))}</textarea></label>
              <button class="secondary-button" id="save-research-button" type="button">Guardar datos revisados</button>
              <small id="research-review-message">Nada se publica hasta que confirmes el entrenamiento.</small>
            </details>
          </form>
          <div class="interview-meter"><i id="interview-fill" style="--progress:0%"></i></div>
          <strong class="interview-percent" id="interview-percent">0% · 0 de 7 respuestas</strong>
          <div class="autoguide-actions">
            <button class="secondary-button" id="use-interview-button" type="button" disabled>Pasar al laboratorio</button>
            <button class="primary-button" id="draft-button" type="button" disabled>Crear agente borrador</button>
          </div>
        </div>
        <div class="chat-machine">
          <div class="scout" id="scout" hidden>
            <div class="scout__chrome">
              <i></i><i></i><i></i>
              <span class="scout__url" id="scout-url">esperando una web o una red…</span>
            </div>
            <div class="scout__viewport">
              <div class="scout__page" id="scout-page" data-tipo="vacio"></div>
              <span class="scout__beam" id="scout-beam"></span>
              <span class="scout__agent" id="scout-agent" aria-hidden="true">✦</span>
            </div>
            <ul class="scout__sources" id="scout-sources"></ul>
            <small class="scout__summary" id="scout-summary" aria-live="polite"></small>
            <small class="scout__note" id="scout-note">Cargá la web o las redes y el investigador entra a mirarlas.</small>
          </div>
          <div class="chat-log" id="interview-log" aria-live="polite"></div>
          <form class="chat-form" id="interview-form">
            <input name="mensaje" autocomplete="off" maxlength="2000" placeholder="Respondé con tus palabras…" />
            <button type="submit" aria-label="Responder">➤</button>
          </form>
        </div>
      </section>

      <section class="test-console" id="prueba">
        <div class="test-console__copy">
          <span class="module-number">MÓDULO 04 · BRAIN REAL</span>
          <h2>Probalo antes de soltarlo</h2>
          <p>Este chat usa el mismo tenant, prompt, conocimiento y herramientas que atienden en la web.</p>
          <div class="brain-path"><span>FRONTEND</span><i></i><span>BRAIN</span><i></i><span>QUANTUMHIVE</span></div>
        </div>
        <div class="chat-machine">
          <div class="chat-log" id="chat-log" aria-live="polite"></div>
          <form class="chat-form" id="chat-form">
            <input name="mensaje" autocomplete="off" maxlength="2000" placeholder="Preguntale como si fueras un cliente…" />
            <button type="submit" aria-label="Enviar">➤</button>
          </form>
        </div>
      </section>

      <section class="whatsapp-console" id="whatsapp">
        <div class="whatsapp-console__copy">
          <span class="module-number">CANAL · WHATSAPP CLOUD API</span>
          <h2>Conectar el WhatsApp del negocio</h2>
          <p>La fábrica vincula el número con este negocio. El token de Meta nunca entra al navegador ni se guarda en la base.</p>
          <div class="readiness" id="whatsapp-readiness">
            <span data-ready="meta">App Meta</span>
            <span data-ready="almacen">Almacén privado</span>
            <span data-ready="verificacion">Webhook</span>
          </div>
        </div>
        <div class="whatsapp-form" id="whatsapp-form">
          <p>Conservás el mismo número y la app de WhatsApp Business. Meta te pedirá autorizar a QuantumHive en una ventana segura.</p>
          <div class="dialog-actions">
            <button class="primary-button" id="whatsapp-connect" type="button">Conectar mi WhatsApp Business</button>
          </div>
          <p class="dialog-message" id="whatsapp-message">Ingresá como dueño para configurar el canal.</p>
        </div>
      </section>
    </main>

    <dialog class="machine-dialog" id="training-dialog">
      <button class="dialog-close" data-close-dialog type="button" aria-label="Cerrar">×</button>
      <span class="module-number">PROTOCOLO DE ENTRENAMIENTO</span>
      <h2>Publicar en el agente del negocio</h2>
      <p>Se crearán las piezas base y todo lo verificado en las fuentes públicas. El borrador no afecta al agente hasta que confirmes esta publicación.</p>
      <div class="training-pieces" id="training-pieces"></div>
      <div class="dialog-actions">
        <button class="secondary-button" data-close-dialog type="button">Seguir editando</button>
        <button class="primary-button" id="publish-button" type="button">Publicar entrenamiento</button>
      </div>
      <p class="dialog-message" id="publish-message"></p>
    </dialog>

    <dialog class="machine-dialog login-dialog" id="login-dialog">
      <button class="dialog-close" data-close-login type="button" aria-label="Cerrar">×</button>
      <span class="module-number">ACCESO DEL FUNDADOR</span>
      <h2>Entrá para fabricar</h2>
      <p>El diseño puede hacerse sin cuenta. Publicar exige tu sesión y pertenencia al negocio.</p>
      <form id="login-form" class="login-form">
        <label class="field-label">Correo<input name="email" type="email" autocomplete="email" required /></label>
        <label class="field-label">Contraseña<input name="password" type="password" autocomplete="current-password" required /></label>
        <button class="primary-button" type="submit">Conectar con QuantumHive</button>
      </form>
      <p class="dialog-message" id="login-message"></p>
    </dialog>

    <dialog class="machine-dialog" id="draft-dialog">
      <button class="dialog-close" data-close-draft type="button" aria-label="Cerrar">×</button>
      <span class="module-number">NUEVO AGENTE · BORRADOR</span>
      <h2>Crear el negocio entrevistado</h2>
      <p>El agente nace en borrador. No se activa ni atiende clientes hasta completar el circuito comercial.</p>
      <form id="draft-form" class="login-form">
        <label class="field-label">Identificador<input name="slug" maxlength="63" required /></label>
        <label class="field-label">Dominio opcional<input name="dominio" placeholder="negocio.com" /></label>
        <label class="field-label">Correo del dueño opcional<input name="email_dueno" type="email" /></label>
        <button class="primary-button" type="submit">Crear agente borrador</button>
      </form>
      <p class="dialog-message" id="draft-message"></p>
    </dialog>

    <footer class="footer-line">
      <span>QUANTUMHIVE · FABRICACIÓN MULTITENANT</span>
      <span id="footer-state">Borrador local protegido</span>
    </footer>
  `;
}

function controlRango(clave, etiqueta, valor) {
  return `
    <label class="range-control">
      <span>${etiqueta}<output data-output="${clave}">${valor}</output></span>
      <input type="range" min="0" max="100" value="${valor}" data-profile="${clave}" />
      <i style="--fill:${valor}%"></i>
    </label>`;
}

async function api(ruta, opciones = {}) {
  if (!state.session?.access_token) throw new Error("Ingresá para usar el agente real.");
  const respuesta = await fetch(`${API_URL}${ruta}`, {
    ...opciones,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${state.session.access_token}`,
      ...opciones.headers,
    },
  });
  const cuerpo = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) throw new Error(cuerpo.error || "No se pudo completar la operación.");
  return cuerpo;
}

async function apiPublica(ruta, opciones = {}) {
  if (!API_URL) throw new Error("Falta configurar la URL de la API.");
  const respuesta = await fetch(`${API_URL}${ruta}`, {
    ...opciones,
    headers: { "Content-Type": "application/json", ...opciones.headers },
  });
  const cuerpo = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) throw new Error(cuerpo.error || "No se pudo continuar.");
  return cuerpo;
}

function rutaDelTenant(sufijo = "") {
  if (!state.tenant?.slug) throw new Error("No hay un negocio seleccionado.");
  return `/api/panel/${encodeURIComponent(state.tenant.slug)}${sufijo}`;
}

function bind() {
  window.addEventListener("message", recibirSesionWhatsapp);
  document.querySelectorAll("[data-profile]").forEach((control) => {
    control.addEventListener("input", () => {
      const clave = control.dataset.profile;
      state.perfil[clave] = control.type === "range" ? Number(control.value) : control.value;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.perfil));
      actualizarNucleo();
      if (control.type === "range") {
        const output = document.querySelector(`[data-output="${clave}"]`);
        if (output) output.value = control.value;
        control.nextElementSibling?.style.setProperty("--fill", `${control.value}%`);
      }
    });
  });

  document.querySelector("#session-button").addEventListener("click", manejarSesion);
  document.querySelector("#prepare-button").addEventListener("click", prepararEntrenamiento);
  document.querySelector("#publish-button").addEventListener("click", publicarEntrenamiento);
  document.querySelector("#login-form").addEventListener("submit", ingresar);
  document.querySelector("#chat-form").addEventListener("submit", probarAgente);
  document.querySelector("#interview-form").addEventListener("submit", continuarEntrevista);
  const formularioInvestigacion = document.querySelector("#research-form");
  formularioInvestigacion.addEventListener("submit", investigarNegocio);
  formularioInvestigacion.addEventListener("input", (evento) => {
    if (["web", "instagram", "facebook", "url_maps"].includes(evento.target.name)) refrescarScout();
  });
  refrescarScout();
  document.querySelector("#save-research-button").addEventListener("click", guardarInvestigacionManual);
  document.querySelector("#new-research-button").addEventListener("click", empezarOtroNegocio);
  document.querySelector("#use-interview-button").addEventListener("click", pasarEntrevistaAlLaboratorio);
  document.querySelector("#draft-button").addEventListener("click", abrirBorrador);
  document.querySelector("#draft-form").addEventListener("submit", crearAgenteBorrador);
  document.querySelector("#whatsapp-connect").addEventListener("click", conectarWhatsapp);
  document.querySelector("#logo-input").addEventListener("change", cargarLogo);
  document.querySelector("#logo-remove").addEventListener("click", quitarLogo);
  document.querySelector("#voice-live-button").addEventListener("click", alternarVozReal);
  document.querySelector("#voice-test-core").addEventListener("click", alternarVozReal);
  document.querySelectorAll("[data-close-dialog]").forEach((boton) => boton.addEventListener("click", () => document.querySelector("#training-dialog").close()));
  document.querySelectorAll("[data-close-login]").forEach((boton) => boton.addEventListener("click", () => document.querySelector("#login-dialog").close()));
  document.querySelectorAll("[data-close-draft]").forEach((boton) => boton.addEventListener("click", () => document.querySelector("#draft-dialog").close()));
  document.querySelector("#voice-level").addEventListener("change", cambiarMotorDeVoz);
  renderChat();
  renderEntrevista();
}

function actualizarNucleo() {
  const porcentaje = progresoDelPerfil(state.perfil);
  document.querySelector("#core-percent").textContent = `${porcentaje}%`;
  document.querySelector("#agent-name").textContent = state.perfil.nombre || "Agente sin nombre";
  document.querySelector("#agent-promise").textContent = state.perfil.promesa || "Definí la promesa principal.";
  const fallback = iniciales(state.perfil.nombre);
  document.querySelector("#orb-fallback").textContent = fallback;
  document.querySelector("#logo-preview-fallback").textContent = fallback;
  document.querySelector("#agent-vat").style.setProperty("--completion", `${porcentaje}%`);
  actualizarColoresDeMarca();
  document.querySelector("#footer-state").textContent = state.tenant
    ? `Conectado a ${state.tenant.nombre}`
    : "Borrador local protegido";
}

function actualizarColoresDeMarca() {
  const vat = document.querySelector("#agent-vat");
  if (!vat) return;
  vat.style.setProperty("--brand-primary", state.colores[0] || "var(--cyan)");
  vat.style.setProperty("--brand-secondary", state.colores[1] || state.colores[0] || "var(--violet)");
}

function empezarOtroNegocio() {
  if (!window.confirm("Se limpiará el borrador local, la investigación y el logo de este equipo. El conocimiento ya publicado no se borra. ¿Continuar?")) return;
  window.clearInterval(state.scout.reloj);
  state.perfil = perfilVacio();
  state.logo = "";
  state.colores = [];
  state.scout = { objetivos: [], activo: -1, corriendo: false, generales: [], reloj: null };
  state.entrevista = {
    ficha: {},
    campo: "nombre",
    progreso: 0,
    mensajes: [
      { rol: "assistant", texto: "Vamos a fabricar tu agente paso a paso. ¿Cómo se llama el negocio o el agente?" },
    ],
  };
  state.mensajes = [{
    rol: "assistant",
    texto: "Soy el agente de QuantumHive conectado al brain real. Publicá el entrenamiento y preguntame como lo haría un posible cliente.",
  }];
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(LOGO_STORAGE_KEY);
  localStorage.removeItem(COLORES_STORAGE_KEY);
  sincronizarFormularioPerfil();
  sincronizarInvestigacion();
  document.querySelector("#research-review").open = false;
  renderScout();
  renderEntrevista();
  renderChat();
  document.querySelector("#research-message").textContent = "Borrador local limpio. Empezá con el nombre y las fuentes del nuevo negocio.";
  document.querySelector("#research-review-message").textContent = "Nada se publica hasta que confirmes el entrenamiento.";
  actualizarLogo();
}

function leerArchivoComoDataUrl(archivo) {
  return new Promise((resolve, reject) => {
    const lector = new FileReader();
    lector.onload = () => resolve(String(lector.result || ""));
    lector.onerror = () => reject(new Error("No se pudo leer la imagen."));
    lector.readAsDataURL(archivo);
  });
}

function cargarImagen(url) {
  return new Promise((resolve, reject) => {
    const imagen = new Image();
    imagen.onload = () => resolve(imagen);
    imagen.onerror = () => reject(new Error("La imagen no es válida."));
    imagen.src = url;
  });
}

async function optimizarLogo(archivo) {
  const tipos = new Set(["image/png", "image/jpeg", "image/webp"]);
  if (!tipos.has(archivo.type)) throw new Error("Usá una imagen PNG, JPG o WebP.");
  if (archivo.size > 5 * 1024 * 1024) throw new Error("El logo debe pesar menos de 5 MB.");
  const origen = await leerArchivoComoDataUrl(archivo);
  const imagen = await cargarImagen(origen);
  const lado = 512;
  const canvas = document.createElement("canvas");
  canvas.width = lado;
  canvas.height = lado;
  const contexto = canvas.getContext("2d");
  const escala = Math.min(lado / imagen.naturalWidth, lado / imagen.naturalHeight);
  const ancho = imagen.naturalWidth * escala;
  const alto = imagen.naturalHeight * escala;
  contexto.clearRect(0, 0, lado, lado);
  contexto.drawImage(imagen, (lado - ancho) / 2, (lado - alto) / 2, ancho, alto);
  return canvas.toDataURL("image/webp", 0.9);
}

async function cargarLogo(evento) {
  const archivo = evento.currentTarget.files?.[0];
  if (!archivo) return;
  const mensaje = document.querySelector("#logo-message");
  mensaje.textContent = "Convirtiendo el logo en orbe…";
  try {
    state.logo = await optimizarLogo(archivo);
    localStorage.setItem(LOGO_STORAGE_KEY, state.logo);
    actualizarLogo();
    mensaje.textContent = "Logo convertido. Quedó aplicado al orbe central.";
  } catch (error) {
    mensaje.textContent = error.message;
  } finally {
    evento.currentTarget.value = "";
  }
}

function quitarLogo() {
  state.logo = "";
  localStorage.removeItem(LOGO_STORAGE_KEY);
  actualizarLogo();
  document.querySelector("#logo-message").textContent = "Logo quitado. Podés cargar otra imagen.";
}

function actualizarLogo() {
  for (const id of ["logo-preview", "orb-logo"]) {
    const imagen = document.querySelector(`#${id}`);
    imagen.hidden = !state.logo;
    if (state.logo) imagen.src = state.logo;
    else imagen.removeAttribute("src");
  }
  document.querySelector("#logo-preview-fallback").hidden = Boolean(state.logo);
  document.querySelector("#orb-fallback").hidden = Boolean(state.logo);
  document.querySelector("#logo-remove").hidden = !state.logo;
  document.querySelector("#agent-vat").classList.toggle("has-brand-logo", Boolean(state.logo));
}

function sincronizarFormularioPerfil() {
  document.querySelectorAll("[data-profile]").forEach((control) => {
    const valor = state.perfil[control.dataset.profile];
    control.value = valor;
    if (control.type === "range") {
      document.querySelector(`[data-output="${control.dataset.profile}"]`).value = valor;
      control.nextElementSibling?.style.setProperty("--fill", `${valor}%`);
    }
  });
  actualizarNucleo();
}

function sincronizarInvestigacion() {
  const formulario = document.querySelector("#research-form");
  if (!formulario) return;
  const investigacion = state.perfil.investigacion && typeof state.perfil.investigacion === "object"
    ? state.perfil.investigacion
    : {};
  const negocio = investigacion.negocio && typeof investigacion.negocio === "object"
    ? investigacion.negocio
    : {};
  ["web", "instagram", "facebook", "url_maps", "direccion", "ciudad", "telefono", "whatsapp", "email"].forEach((clave) => {
    if (formulario.elements[clave]) formulario.elements[clave].value = negocio[clave] || "";
  });
  formulario.elements.servicios.value = (investigacion.servicios || []).join("\n");
  formulario.elements.precios.value = (investigacion.precios || []).join("\n");
  formulario.elements.horarios.value = investigacion.horarios || "";
  formulario.elements.preguntas_frecuentes.value = textoDePreguntas(investigacion.preguntas_frecuentes);
  document.querySelector("#research-review").open = true;
}

function guardarInvestigacionManual() {
  const formulario = document.querySelector("#research-form");
  const datos = new FormData(formulario);
  state.perfil = editarInvestigacion(state.perfil, {
    negocio: Object.fromEntries(
      ["web", "instagram", "facebook", "url_maps", "direccion", "ciudad", "telefono", "whatsapp", "email"]
        .map((clave) => [clave, String(datos.get(clave) || "").trim()]),
    ),
    servicios: lineas(datos.get("servicios")),
    precios: lineas(datos.get("precios")),
    horarios: String(datos.get("horarios") || "").trim(),
    preguntas_frecuentes: preguntasDesdeTexto(datos.get("preguntas_frecuentes")),
  });
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.perfil));
  sincronizarFormularioPerfil();
  sincronizarInvestigacion();
  const piezas = armarPiezasConocimiento(state.perfil).length;
  document.querySelector("#research-review-message").textContent = `Datos guardados en este equipo. Quedaron ${piezas} módulos listos para revisar antes de publicar.`;
}

function aplicarMarcaPublicada() {
  const pieza = state.conocimiento.find((item) => item.clave === "fabrica-datos-publicos");
  if (!pieza) return;
  const version = pieza.versiones?.find((item) => item.id === pieza.version_publicada_id)
    || pieza.versiones?.[0];
  const marca = version?.contenido?.marca;
  if (!marca || typeof marca !== "object") return;
  if (esLogoRemotoAplicable(marca.logo_url)) {
    state.logo = marca.logo_url;
    localStorage.setItem(LOGO_STORAGE_KEY, state.logo);
  }
  if (Array.isArray(marca.colores)) {
    state.colores = marca.colores.filter((color) => /^#[0-9a-f]{6}$/i.test(color)).slice(0, 4);
    localStorage.setItem(COLORES_STORAGE_KEY, JSON.stringify(state.colores));
  }
  actualizarLogo();
  actualizarColoresDeMarca();
}

function urlDeMuestra(ruta) {
  if (!ruta) return "";
  return new URL(ruta, `${location.origin}${import.meta.env.BASE_URL}`).href;
}

async function cambiarMotorDeVoz(evento) {
  await desconectarVoz({ silencioso: true });
  state.voz.motor = evento.currentTarget.value;
  state.voz.seleccion = "";
  document.querySelector("#agent-vat").dataset.voice = state.voz.motor;
  await cargarVoces();
}

async function cargarVoces() {
  const contenedor = document.querySelector("#voice-catalog");
  contenedor.innerHTML = '<span class="voice-loading">Cargando voces…</span>';
  if (state.voz.motor === "pipeline") {
    state.voz.catalogo = [{ voz: "", nombre: "Voz Fish clonada del negocio", genero: "" }];
    state.voz.seleccion = "";
    renderVoces();
    return;
  }
  try {
    const respuesta = await fetch(`${API_URL}/api/voces?motor=${state.voz.motor}`);
    const datos = await respuesta.json();
    if (!respuesta.ok) throw new Error(datos.error || "No se pudo cargar el catálogo.");
    state.voz.catalogo = datos.voces || [];
    state.voz.seleccion = state.voz.catalogo[0]?.voz || "";
    renderVoces();
  } catch (error) {
    state.voz.catalogo = [];
    contenedor.innerHTML = `<span class="voice-loading is-error">${escapeHtml(error.message)}</span>`;
  }
}

function renderVoces() {
  const catalogo = state.voz.catalogo;
  const contenedor = document.querySelector("#voice-catalog");
  const pipeline = state.voz.motor === "pipeline";
  contenedor.innerHTML = catalogo.map((voz) => `
    <button class="voice-chip ${voz.voz === state.voz.seleccion ? "is-selected" : ""}" data-voice="${escapeHtml(voz.voz)}" type="button">
      <span>${escapeHtml(voz.nombre)}</span>${voz.muestra ? "<small>▶ escuchar</small>" : "<small>Fish · clon aprobada</small>"}
    </button>`).join("");
  contenedor.querySelectorAll("[data-voice]").forEach((boton) => {
    boton.addEventListener("click", () => elegirVoz(boton.dataset.voice));
  });
  const elegida = catalogo.find((voz) => voz.voz === state.voz.seleccion) || catalogo[0];
  document.querySelector("#voice-name").textContent = elegida?.nombre || "Sin voces disponibles";
  document.querySelector("#voice-message").textContent = pipeline
    ? "Fish usa la voz clonada aprobada de este negocio. Tocá Probar para escucharla conversando de verdad."
    : `${catalogo.length} voces disponibles. Tocá un nombre para oír una muestra sin gastar una sesión.`;
}

async function elegirVoz(clave) {
  if (state.voz.sala) await desconectarVoz({ silencioso: true });
  state.voz.seleccion = clave;
  renderVoces();
  const voz = state.voz.catalogo.find((item) => item.voz === clave);
  if (!voz?.muestra) return;
  preescucha.pause();
  preescucha.currentTime = 0;
  preescucha.src = urlDeMuestra(voz.muestra);
  try {
    await preescucha.play();
    document.querySelector("#voice-state").textContent = "MUESTRA";
  } catch {
    document.querySelector("#voice-message").textContent = "No se pudo reproducir esta muestra. Probá otra voz.";
  }
}

function estadoVoz(estado, mensaje = "") {
  const vat = document.querySelector("#agent-vat");
  vat.dataset.audio = estado;
  document.querySelector("#voice-state").textContent = estado.toUpperCase();
  if (mensaje) document.querySelector("#voice-message").textContent = mensaje;
  const activo = Boolean(state.voz.sala);
  document.querySelector("#voice-live-button").classList.toggle("is-live", activo);
  document.querySelector("#voice-live-button").innerHTML = activo
    ? "<span></span> Terminar conversación"
    : "<span></span> Probar agente con micrófono";
  document.querySelector("#voice-test-core").textContent = activo ? "Terminar conversación" : "Hablar con el agente";
}

async function alternarVozReal() {
  if (state.voz.sala) await desconectarVoz();
  else await conectarVoz();
}

async function conectarVoz() {
  if (state.voz.conectando) return;
  state.voz.conectando = true;
  estadoVoz("conectando", "Conectando con el motor de voz real…");
  const nivel = NIVEL_DE_MOTOR[state.voz.motor] || 1;
  const headers = { "Content-Type": "application/json" };
  if (state.session?.access_token) headers.Authorization = `Bearer ${state.session.access_token}`;
  try {
    const respuesta = await fetch(`${API_URL}/api/token`, {
      method: "POST",
      headers,
      body: JSON.stringify({ nivel, tenant: "quantumhive", voz: state.voz.seleccion || undefined }),
    });
    const datos = await respuesta.json();
    if (!respuesta.ok) throw new Error(datos.error || "No se pudo iniciar la voz.");

    const sala = new Room();
    state.voz.sala = sala;
    sala.on(RoomEvent.TrackSubscribed, (track) => {
      if (track.kind !== Track.Kind.Audio) return;
      const audio = track.attach();
      audio.autoplay = true;
      audio.dataset.factoryAudio = "true";
      audio.hidden = true;
      document.body.append(audio);
      audio.play().catch(() => {});
    });
    sala.on(RoomEvent.ActiveSpeakersChanged, (participantes) => {
      const hablaAgente = participantes.some((persona) => persona.identity !== sala.localParticipant.identity);
      estadoVoz(hablaAgente ? "hablando" : "escuchando");
    });
    sala.on(RoomEvent.Disconnected, () => {
      if (state.voz.sala === sala) state.voz.sala = null;
      estadoVoz("lista", "Conversación finalizada. Podés cambiar de motor o probar otra vez.");
    });
    await sala.connect(datos.url, datos.token);
    await sala.startAudio();
    await sala.localParticipant.setMicrophoneEnabled(true);
    estadoVoz("escuchando", `Motor ${state.voz.motor} conectado al agente real de ${datos.tenant}. Ya podés hablar.`);
    clearTimeout(state.voz.temporizador);
    state.voz.temporizador = setTimeout(() => desconectarVoz(), (datos.duracion_maxima_seg || 240) * 1000);
  } catch (error) {
    await desconectarVoz({ silencioso: true });
    estadoVoz("error", error.message || "No se pudo conectar. Revisá el permiso del micrófono.");
  } finally {
    state.voz.conectando = false;
  }
}

async function desconectarVoz({ silencioso = false } = {}) {
  clearTimeout(state.voz.temporizador);
  const sala = state.voz.sala;
  state.voz.sala = null;
  if (sala) await sala.disconnect();
  document.querySelectorAll("audio[data-factory-audio]").forEach((audio) => audio.remove());
  if (!silencioso) estadoVoz("lista", "Conversación finalizada. Podés elegir otra voz o volver a probar.");
}

function actualizarSesion() {
  const boton = document.querySelector("#session-button");
  const mensaje = document.querySelector("#system-message");
  const coreState = document.querySelector("#core-state");
  if (state.session && state.tenant) {
    boton.textContent = "Cerrar sesión";
    coreState.textContent = "BRAIN CONECTADO";
    mensaje.textContent = `Conectado a ${state.tenant.nombre}. El entrenamiento se publicará solamente en este tenant.`;
    document.body.dataset.connected = "true";
  } else {
    boton.textContent = "Ingresar";
    coreState.textContent = "DISEÑO LOCAL";
    mensaje.textContent = configurado
      ? "Tu diseño se guarda en este equipo. Para publicarlo en el agente real, ingresá con tu cuenta."
      : "Configurá la API y Supabase para conectar el agente real.";
    document.body.dataset.connected = "false";
  }
  actualizarNucleo();
  renderWhatsapp();
}

async function manejarSesion() {
  if (state.session) {
    await supabase.auth.signOut();
    state.session = null;
    state.tenant = null;
    state.conocimiento = [];
    state.whatsapp = null;
    state.whatsappDisponible = true;
    state.whatsappOnboarding = null;
    actualizarSesion();
    return;
  }
  const dialogo = document.querySelector("#login-dialog");
  if (!configurado) {
    document.querySelector("#login-message").textContent = "Falta configurar la conexión pública del frontend.";
  }
  dialogo.showModal();
}

async function ingresar(evento) {
  evento.preventDefault();
  const mensaje = document.querySelector("#login-message");
  if (!supabase) {
    mensaje.textContent = "La conexión todavía no está configurada.";
    return;
  }
  const datos = new FormData(evento.currentTarget);
  mensaje.textContent = "Verificando identidad y tenant…";
  const { data, error } = await supabase.auth.signInWithPassword({
    email: datos.get("email"),
    password: datos.get("password"),
  });
  if (error) {
    mensaje.textContent = `No pudimos ingresar: ${error.message}`;
    return;
  }
  state.session = data.session;
  try {
    await cargarTenantActual();
    document.querySelector("#login-dialog").close();
    evento.currentTarget.reset();
    mensaje.textContent = "";
    actualizarSesion();
  } catch (fallo) {
    await supabase.auth.signOut();
    state.session = null;
    mensaje.textContent = fallo.message;
  }
}

async function cargarTenantActual() {
  const datos = await api("/api/panel/tenants");
  const tenants = datos.tenants || [];
  const solicitado = new URLSearchParams(window.location.search).get("tenant");
  state.tenant = solicitado
    ? tenants.find((tenant) => tenant.slug === solicitado) || null
    : tenants.find((tenant) => tenant.slug === "quantumhive") || (tenants.length === 1 ? tenants[0] : null);
  if (!state.tenant) {
    throw new Error(solicitado
      ? "La sesión es válida, pero no pertenece a ese negocio."
      : "La sesión pertenece a varios negocios. Abrí el panel con ?tenant=slug para elegir uno.");
  }
  const conocimiento = await api(rutaDelTenant("/conocimiento"));
  state.conocimiento = conocimiento.conocimiento || [];
  aplicarMarcaPublicada();
  try {
    const [canales, onboarding] = await Promise.all([
      api(rutaDelTenant("/canales")),
      api(rutaDelTenant("/canales/whatsapp/onboarding")),
    ]);
    state.whatsapp = canales.canales?.find((canal) => canal.canal === "whatsapp") || null;
    state.whatsappOnboarding = onboarding;
    state.whatsappDisponible = true;
  } catch {
    // WhatsApp se despliega por separado del panel. Una ruta todavia no
    // publicada nunca debe invalidar una sesion ni bloquear el brain.
    state.whatsapp = null;
    state.whatsappOnboarding = null;
    state.whatsappDisponible = false;
  }
  renderWhatsapp();
}

function prepararEntrenamiento() {
  const piezas = armarPiezasConocimiento(state.perfil);
  document.querySelector("#training-pieces").innerHTML = piezas.map((pieza, indice) => `
    <div class="training-piece">
      <span>${String(indice + 1).padStart(2, "0")}</span>
      <div><strong>${escapeHtml(pieza.titulo)}</strong><small>${escapeHtml(pieza.categoria)} · ${escapeHtml(pieza.clave)}</small></div>
      <i>LISTA</i>
    </div>`).join("");
  document.querySelector("#publish-message").textContent = state.session
    ? `Destino verificado: ${state.tenant?.nombre || "QuantumHive"}.`
    : "Ingresá antes de publicar. El diseño no se pierde.";
  document.querySelector("#training-dialog").showModal();
}

async function publicarEntrenamiento() {
  if (state.publicando) return;
  if (!state.session || !state.tenant) {
    document.querySelector("#training-dialog").close();
    document.querySelector("#login-dialog").showModal();
    return;
  }

  const boton = document.querySelector("#publish-button");
  const mensaje = document.querySelector("#publish-message");
  const piezas = armarPiezasConocimiento(state.perfil);
  state.publicando = true;
  boton.disabled = true;

  try {
    for (const [indice, pieza] of piezas.entries()) {
      mensaje.textContent = `Entrenando módulo ${indice + 1} de ${piezas.length}: ${pieza.titulo}…`;
      const borrador = await api(rutaDelTenant("/conocimiento/borradores"), {
        method: "POST",
        body: JSON.stringify({ ...pieza, motivo: `Fabricación inicial del agente ${state.tenant.nombre}` }),
      });
      await api(rutaDelTenant(`/conocimiento/${encodeURIComponent(borrador.borrador.version_id)}/publicar`), {
        method: "POST",
        body: JSON.stringify({ motivo: "Publicado desde la Fábrica de Agentes" }),
      });
    }
    await cargarTenantActual();
    mensaje.textContent = `Entrenamiento publicado. El brain de ${state.tenant.nombre} ya carga esta versión.`;
    document.querySelector("#core-state").textContent = "ENTRENADO";
    document.querySelector("#footer-state").textContent = `${piezas.length} módulos publicados en ${state.tenant.nombre}`;
    boton.textContent = "Entrenamiento publicado ✓";
  } catch (fallo) {
    mensaje.textContent = `Se detuvo la publicación: ${fallo.message}`;
    boton.disabled = false;
  } finally {
    state.publicando = false;
  }
}

async function cargarEstadoPerfilador() {
  const boton = document.querySelector("#research-button");
  const mensaje = document.querySelector("#research-message");
  try {
    const resultado = await apiPublica("/api/fabrica/perfilador");
    state.perfiladorDisponible = Boolean(resultado.disponible);
    boton.disabled = !state.perfiladorDisponible;
    if (!state.perfiladorDisponible) {
      mensaje.textContent = "El módulo está instalado, pero falta conectar la URL y el token en el servidor.";
    }
  } catch {
    state.perfiladorDisponible = false;
    boton.disabled = true;
    mensaje.textContent = "El servidor todavía no publicó el módulo de investigación.";
  }
}

/* ── El visor del investigador ──────────────────────────────────────────────
   Muestra al agente entrando a cada fuente que cargó el dueño. El recorrido
   marca el ritmo mientras el backend trabaja, pero los resultados salen del
   paquete real: si el Perfilador se cae, ninguna fuente queda en verde.
   ────────────────────────────────────────────────────────────────────────── */

const ESQUELETOS = {
  web: `<span class="sk sk--barra"></span><span class="sk sk--titulo"></span>
        <span class="sk sk--linea"></span><span class="sk sk--linea sk--corta"></span>
        <div class="sk-fila"><span class="sk sk--bloque"></span><span class="sk sk--bloque"></span><span class="sk sk--bloque"></span></div>`,
  instagram: `<div class="sk-perfil"><span class="sk sk--avatar"></span>
        <div class="sk-datos"><span class="sk sk--titulo"></span><span class="sk sk--linea sk--corta"></span></div></div>
        <div class="sk-grilla"><i></i><i></i><i></i><i></i><i></i><i></i></div>`,
  facebook: `<span class="sk sk--portada"></span>
        <div class="sk-perfil"><span class="sk sk--avatar"></span>
        <div class="sk-datos"><span class="sk sk--titulo"></span><span class="sk sk--linea sk--corta"></span></div></div>
        <span class="sk sk--linea"></span><span class="sk sk--linea sk--corta"></span>`,
  url_maps: `<div class="sk-mapa"><span class="sk-pin">◈</span></div>
        <span class="sk sk--titulo"></span><span class="sk sk--linea sk--corta"></span>`,
  vacio: `<span class="sk sk--linea"></span><span class="sk sk--linea sk--corta"></span>`,
};

function entradasDeInvestigacion() {
  const formulario = document.querySelector("#research-form");
  if (!formulario) return {};
  const datos = new FormData(formulario);
  return {
    web: datos.get("web"),
    instagram: datos.get("instagram"),
    facebook: datos.get("facebook"),
    url_maps: datos.get("url_maps"),
  };
}

function refrescarScout() {
  if (state.scout.corriendo) return;
  const previos = new Map(state.scout.objetivos.map((o) => [o.clave, o]));
  state.scout.objetivos = objetivosDeInvestigacion(entradasDeInvestigacion()).map((objetivo) => {
    const previo = previos.get(objetivo.clave);
    const mismoDestino = previo && previo.destino === objetivo.destino;
    return mismoDestino ? { ...objetivo, estado: previo.estado, hallazgos: previo.hallazgos || [] } : { ...objetivo, estado: "pendiente", hallazgos: [] };
  });
  renderScout();
}

function renderScout() {
  const visor = document.querySelector("#scout");
  if (!visor) return;
  const { objetivos, activo, corriendo, generales } = state.scout;
  visor.hidden = objetivos.length === 0;
  if (!objetivos.length) return;

  const enFoco = corriendo && activo >= 0 ? objetivos[activo] : null;
  visor.dataset.estado = corriendo ? "visitando" : "quieto";

  const url = document.querySelector("#scout-url");
  url.textContent = enFoco ? enFoco.destino : `${objetivos.length} fuente${objetivos.length > 1 ? "s" : ""} para revisar`;

  const pagina = document.querySelector("#scout-page");
  const tipo = enFoco ? enFoco.clave : "vacio";
  if (pagina.dataset.tipo !== tipo) {
    pagina.dataset.tipo = tipo;
    pagina.innerHTML = ESQUELETOS[tipo] || ESQUELETOS.vacio;
  }

  document.querySelector("#scout-sources").innerHTML = objetivos
    .map((objetivo, indice) => {
      const foco = corriendo && indice === activo;
      const estado = foco ? "visitando" : objetivo.estado || "pendiente";
      const detalle = (objetivo.hallazgos || []).join(" · ");
      let leyenda = {
        visitando: "mirando el perfil…",
        encontrado: detalle,
        "sin-datos": "sin datos públicos",
        fallo: "no se pudo entrar",
        pendiente: "en la cola",
      }[estado];
      if (estado === "sin-datos" && objetivo.clave === "instagram") {
        leyenda = "Instagram no entregó datos públicos";
      }
      return `<li class="scout-src" data-estado="${estado}">
        <span class="scout-src__icono">${objetivo.icono}</span>
        <span class="scout-src__texto"><b>${escapeHtml(objetivo.destino)}</b><small>${escapeHtml(leyenda || "")}</small></span>
      </li>`;
    })
    .join("");

  const resumen = resumenDeFuentes(objetivos);
  document.querySelector("#scout-summary").textContent = [
    resumen.encontrado ? `${resumen.encontrado} encontrada${resumen.encontrado > 1 ? "s" : ""}` : "",
    resumen["sin-datos"] ? `${resumen["sin-datos"]} sin datos` : "",
    resumen.fallo ? `${resumen.fallo} con fallo` : "",
    resumen.pendiente ? `${resumen.pendiente} pendiente${resumen.pendiente > 1 ? "s" : ""}` : "",
  ].filter(Boolean).join(" · ");

  const nota = document.querySelector("#scout-note");
  if (corriendo) nota.textContent = "El investigador corre en el servidor. Tu navegador nunca ve el token.";
  else if (generales?.length) nota.textContent = `Además, sin poder atribuirlo a una fuente: ${generales.join(", ")}.`;
  else nota.textContent = "Cargá la web o las redes y el investigador entra a mirarlas.";
}

function arrancarRecorrido() {
  const objetivos = state.scout.objetivos;
  if (!objetivos.length) return;
  state.scout.corriendo = true;
  state.scout.activo = 0;
  state.scout.generales = [];
  renderScout();
  state.scout.reloj = window.setInterval(() => {
    state.scout.activo = (state.scout.activo + 1) % state.scout.objetivos.length;
    renderScout();
  }, 1700);
}

function cerrarRecorridoVisual(paquete, fallo) {
  window.clearInterval(state.scout.reloj);
  state.scout.reloj = null;
  state.scout.corriendo = false;
  state.scout.activo = -1;
  state.scout.objetivos = cerrarRecorrido(state.scout.objetivos, paquete, fallo);
  state.scout.generales = fallo ? [] : hallazgosGenerales(paquete || {});
  renderScout();
}

async function investigarNegocio(evento) {
  evento.preventDefault();
  const formulario = evento.currentTarget;
  const boton = document.querySelector("#research-button");
  const mensaje = document.querySelector("#research-message");
  const datos = new FormData(formulario);
  const nombre = String(state.entrevista.ficha.nombre || state.perfil.nombre || "").trim();
  if (!nombre) {
    mensaje.textContent = "Primero escribí el nombre del negocio en Identidad o respondé la primera pregunta.";
    return;
  }
  boton.disabled = true;
  boton.textContent = "Investigando fuentes públicas…";
  mensaje.textContent = "Buscando web, redes, servicios, horarios y marca. Puede tardar hasta un minuto.";
  arrancarRecorrido();
  try {
    const resultado = await apiPublica("/api/fabrica/investigar", {
      method: "POST",
      body: JSON.stringify({
        nombre,
        web: datos.get("web"),
        instagram: datos.get("instagram"),
        facebook: datos.get("facebook"),
        url_maps: datos.get("url_maps"),
      }),
    });
    cerrarRecorridoVisual(resultado.perfil, false);
    state.perfil = integrarInvestigacion(state.perfil, resultado.perfil);
    const negocio = resultado.perfil?.negocio || {};
    const servicios = resultado.perfil?.servicios || [];
    const precios = resultado.perfil?.precios || [];
    state.entrevista.ficha = {
      ...state.entrevista.ficha,
      ...(negocio.nombre ? { nombre: negocio.nombre } : {}),
      ...(negocio.categoria ? { rubro: negocio.categoria } : {}),
      ...(servicios.length || precios.length ? { oferta: state.perfil.oferta } : {}),
    };
    const faltantes = CAMPOS_ENTREVISTA.filter((campo) => !state.entrevista.ficha[campo]);
    state.entrevista.campo = faltantes[0] || null;
    state.entrevista.progreso = Math.round(100 * (CAMPOS_ENTREVISTA.length - faltantes.length) / CAMPOS_ENTREVISTA.length);
    const marca = resultado.perfil?.marca || {};
    if (esLogoRemotoAplicable(marca.logo_url)) {
      state.logo = marca.logo_url;
      localStorage.setItem(LOGO_STORAGE_KEY, state.logo);
      actualizarLogo();
    }
    state.colores = Array.isArray(marca.colores)
      ? marca.colores.filter((color) => /^#[0-9a-f]{6}$/i.test(color)).slice(0, 4)
      : [];
    localStorage.setItem(COLORES_STORAGE_KEY, JSON.stringify(state.colores));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.perfil));
    sincronizarFormularioPerfil();
    sincronizarInvestigacion();
    const hallazgos = [
      servicios.length ? `${servicios.length} servicios` : "",
      precios.length ? `${precios.length} precios` : "",
      resultado.perfil?.horarios ? "horarios" : "",
      resultado.perfil?.preguntas_frecuentes?.length ? `${resultado.perfil.preguntas_frecuentes.length} preguntas frecuentes` : "",
      marca.logo_url ? "logo" : "",
    ].filter(Boolean);
    const siguiente = state.entrevista.campo ? ` Ahora sigamos: ${PREGUNTAS_ENTREVISTA[state.entrevista.campo]}` : " La ficha quedó completa.";
    const resumen = hallazgos.length
      ? `Investigación lista. Encontré ${hallazgos.join(", ")}.`
      : "La fuente respondió, pero no entregó información pública utilizable. No voy a inventar datos ni usar imágenes genéricas de la red social.";
    state.entrevista.mensajes.push({
      rol: "assistant",
      texto: `${resumen}${siguiente}`,
    });
    renderEntrevista();
    mensaje.textContent = hallazgos.length
      ? `Investigación aplicada a ${state.perfil.nombre}. Revisá lo encontrado y completá lo que falta con el guía.`
      : "Instagram no entregó datos públicos del perfil. Probá también con la web o Google Maps, o completá la ficha manualmente.";
  } catch (fallo) {
    cerrarRecorridoVisual(null, true);
    mensaje.textContent = fallo.message;
  } finally {
    boton.textContent = "✦ Investigar mi negocio";
    boton.disabled = state.perfiladorDisponible === false;
  }
}

async function continuarEntrevista(evento) {
  evento.preventDefault();
  if (!state.entrevista.campo) return;
  const input = evento.currentTarget.elements.mensaje;
  const texto = input.value.trim();
  if (!texto) return;
  const campo = state.entrevista.campo;
  state.entrevista.mensajes.push({ rol: "user", texto });
  state.entrevista.mensajes.push({ rol: "assistant", texto: "El brain está armando la ficha…", pendiente: true });
  input.value = "";
  renderEntrevista();
  try {
    const respuesta = await apiPublica("/api/fabrica/entrevista", {
      method: "POST",
      body: JSON.stringify({ campo, mensaje: texto, ficha: state.entrevista.ficha }),
    });
    state.entrevista.ficha = respuesta.ficha;
    state.entrevista.campo = respuesta.siguiente;
    state.entrevista.progreso = respuesta.progreso;
    state.entrevista.mensajes.pop();
    state.entrevista.mensajes.push({ rol: "assistant", texto: respuesta.respuesta });
  } catch (fallo) {
    state.entrevista.mensajes.pop();
    state.entrevista.mensajes.push({ rol: "assistant", texto: fallo.message, error: true });
  }
  renderEntrevista();
}

function renderEntrevista() {
  const entrevista = state.entrevista;
  const log = document.querySelector("#interview-log");
  if (!log) return;
  log.innerHTML = entrevista.mensajes.map((mensaje) => `
    <div class="chat-message chat-message--${mensaje.rol} ${mensaje.pendiente ? "is-pending" : ""} ${mensaje.error ? "is-error" : ""}">
      <small>${mensaje.rol === "user" ? "VOS" : "GUÍA QH"}</small>
      <p>${escapeHtml(mensaje.texto)}</p>
    </div>`).join("");
  log.scrollTop = log.scrollHeight;
  const respondidas = Object.keys(entrevista.ficha).length;
  document.querySelector("#interview-fill").style.setProperty("--progress", `${entrevista.progreso}%`);
  document.querySelector("#interview-percent").textContent = `${entrevista.progreso}% · ${respondidas} de 7 respuestas`;
  document.querySelector("#use-interview-button").disabled = entrevista.progreso !== 100;
  document.querySelector("#draft-button").disabled = entrevista.progreso !== 100;
  const input = document.querySelector("#interview-form input");
  input.disabled = entrevista.progreso === 100;
  input.placeholder = entrevista.progreso === 100 ? "Ficha completa" : "Respondé con tus palabras…";
}

function pasarEntrevistaAlLaboratorio() {
  if (state.entrevista.progreso !== 100) return;
  state.perfil = normalizarPerfil(state.entrevista.ficha);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.perfil));
  sincronizarFormularioPerfil();
  document.querySelector("#identidad").scrollIntoView({ behavior: "smooth" });
}

function abrirBorrador() {
  if (state.entrevista.progreso !== 100) return;
  if (!state.session) {
    document.querySelector("#login-dialog").showModal();
    return;
  }
  const dialogo = document.querySelector("#draft-dialog");
  dialogo.querySelector('[name="slug"]').value = slugDeNombre(state.entrevista.ficha.nombre);
  document.querySelector("#draft-message").textContent = "Se creará como borrador, sin activar ventas ni canales.";
  dialogo.showModal();
}

async function crearAgenteBorrador(evento) {
  evento.preventDefault();
  const mensaje = document.querySelector("#draft-message");
  const datos = new FormData(evento.currentTarget);
  mensaje.textContent = "Creando el agente aislado en su propio negocio…";
  try {
    const resultado = await api("/api/fabrica/negocios", {
      method: "POST",
      body: JSON.stringify({
        slug: datos.get("slug"),
        nombre: state.entrevista.ficha.nombre,
        perfil: "receptor",
        prompt_propio: promptDesdeFicha(state.entrevista.ficha),
        dominio: datos.get("dominio"),
        email_dueno: datos.get("email_dueno"),
      }),
    });
    mensaje.textContent = `Agente ${resultado.negocio.slug} creado como borrador. Ya puede seguir al entrenamiento y activación comercial.`;
  } catch (fallo) {
    mensaje.textContent = fallo.message;
  }
}

function renderWhatsapp() {
  const mensaje = document.querySelector("#whatsapp-message");
  const formulario = document.querySelector("#whatsapp-form");
  const boton = document.querySelector("#whatsapp-connect");
  if (!mensaje || !formulario) return;
  const canal = state.whatsapp;
  const alta = state.whatsappOnboarding || {};
  const mapa = {
    meta: Boolean(alta.app_id && alta.configuration_id),
    almacen: alta.almacen_configurado,
    verificacion: alta.disponible,
  };
  Object.entries(mapa).forEach(([clave, listo]) => {
    document.querySelector(`[data-ready="${clave}"]`)?.classList.toggle("is-ready", Boolean(listo));
  });
  mensaje.textContent = !state.session
    ? "Ingresá como dueño para configurar el canal."
    : !state.whatsappDisponible
      ? "El agente y el entrenamiento están activos. Falta publicar el módulo seguro de WhatsApp en el servidor."
    : canal
      ? `Estado: ${canal.estado}. ${canal.estado === "conectado" ? "El canal puede recibir y responder." : "Guardado; faltan credenciales o la verificación final."}`
      : !alta.disponible
        ? "Falta completar la configuración única de la app de QuantumHive en Meta."
        : "Listo para vincular el WhatsApp Business de QuantumHive sin cambiar el número.";
  if (boton) {
    boton.disabled = !state.session || !state.whatsappDisponible || !alta.disponible || state.whatsappAlta.completando;
    boton.textContent = state.whatsappAlta.completando
      ? "Conectando con Meta…"
      : canal?.estado === "conectado"
        ? "Volver a autorizar WhatsApp"
        : "Conectar mi WhatsApp Business";
  }
}

function cargarSdkMeta(appId, version) {
  if (window.FB) {
    window.FB.init({ appId, cookie: true, xfbml: false, version });
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    window.fbAsyncInit = () => {
      window.FB.init({ appId, cookie: true, xfbml: false, version });
      resolve();
    };
    const existente = document.querySelector("#facebook-jssdk");
    if (existente) return;
    const script = document.createElement("script");
    script.id = "facebook-jssdk";
    script.src = "https://connect.facebook.net/es_LA/sdk.js";
    script.async = true;
    script.defer = true;
    script.onerror = () => reject(new Error("No se pudo cargar la ventana segura de Meta."));
    document.head.appendChild(script);
  });
}

function recibirSesionWhatsapp(evento) {
  if (!["https://www.facebook.com", "https://web.facebook.com"].includes(evento.origin)) return;
  let datos = evento.data;
  try {
    if (typeof datos === "string") datos = JSON.parse(datos);
  } catch {
    return;
  }
  if (datos?.type !== "WA_EMBEDDED_SIGNUP") return;
  if (!["FINISH", "FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING"].includes(datos.event)) return;
  state.whatsappAlta.waba_id = String(datos.data?.waba_id || "");
  state.whatsappAlta.phone_number_id = String(datos.data?.phone_number_id || "");
  terminarConexionWhatsapp();
}

async function conectarWhatsapp() {
  const mensaje = document.querySelector("#whatsapp-message");
  if (!state.session || !state.tenant) {
    document.querySelector("#login-dialog").showModal();
    return;
  }
  if (!state.whatsappDisponible) {
    mensaje.textContent = "WhatsApp todavía no está habilitado en el servidor. El resto del agente sigue operativo.";
    return;
  }
  const alta = state.whatsappOnboarding;
  if (!alta?.disponible) {
    mensaje.textContent = "Primero hay que completar la configuración única de QuantumHive en Meta.";
    return;
  }
  try {
    state.whatsappAlta = { code: "", waba_id: "", phone_number_id: "", completando: false };
    mensaje.textContent = "Abriendo la autorización oficial de Meta…";
    await cargarSdkMeta(alta.app_id, alta.api_version);
    window.FB.login((respuesta) => {
      const code = respuesta?.authResponse?.code;
      if (!code) {
        mensaje.textContent = "La autorización fue cancelada o Meta no devolvió el permiso.";
        return;
      }
      state.whatsappAlta.code = code;
      terminarConexionWhatsapp();
    }, {
      config_id: alta.configuration_id,
      response_type: "code",
      override_default_response_type: true,
      extras: {
        setup: {},
        featureType: alta.feature_type,
        sessionInfoVersion: "3",
      },
    });
  } catch (fallo) {
    mensaje.textContent = fallo.message;
  }
}

async function terminarConexionWhatsapp() {
  const alta = state.whatsappAlta;
  if (!alta.code || !alta.waba_id || alta.completando) return;
  const mensaje = document.querySelector("#whatsapp-message");
  alta.completando = true;
  renderWhatsapp();
  mensaje.textContent = "Meta autorizó el número. Asignándolo al agente QuantumHive…";
  let resultadoFinal = "";
  try {
    const resultado = await api(rutaDelTenant("/canales/whatsapp/onboarding/completar"), {
      method: "POST",
      body: JSON.stringify({
        code: alta.code,
        waba_id: alta.waba_id,
        phone_number_id: alta.phone_number_id,
      }),
    });
    state.whatsapp = resultado.canal;
    resultadoFinal = `WhatsApp ${resultado.canal.numero || ""} conectado al agente ${state.tenant.nombre}.`;
  } catch (fallo) {
    resultadoFinal = fallo.message;
  } finally {
    alta.completando = false;
    alta.code = "";
    renderWhatsapp();
    mensaje.textContent = resultadoFinal;
  }
}

async function probarAgente(evento) {
  evento.preventDefault();
  const input = evento.currentTarget.elements.mensaje;
  const texto = input.value.trim();
  if (!texto) return;
  state.mensajes.push({ rol: "user", texto });
  input.value = "";
  state.mensajes.push({ rol: "assistant", texto: "Procesando con el brain…", pendiente: true });
  renderChat();

  try {
    if (!state.session || !state.tenant) throw new Error("Ingresá para probar el brain real del negocio.");
    const historial = state.mensajes
      .filter((mensaje) => !mensaje.pendiente)
      .slice(-20, -1)
      .map((mensaje) => ({ rol: mensaje.rol, texto: mensaje.texto }));
    const respuesta = await api(rutaDelTenant("/chat"), {
      method: "POST",
      body: JSON.stringify({ mensaje: texto, historial, modo: "cliente" }),
    });
    state.mensajes.pop();
    state.mensajes.push({ rol: "assistant", texto: respuesta.respuesta });
  } catch (fallo) {
    state.mensajes.pop();
    state.mensajes.push({ rol: "assistant", texto: fallo.message, error: true });
  }
  renderChat();
}

function renderChat() {
  const log = document.querySelector("#chat-log");
  log.innerHTML = state.mensajes.map((mensaje) => `
    <div class="chat-message chat-message--${mensaje.rol} ${mensaje.pendiente ? "is-pending" : ""} ${mensaje.error ? "is-error" : ""}">
      <small>${mensaje.rol === "user" ? "VOS" : "AGENTE QH"}</small>
      <p>${escapeHtml(mensaje.texto)}</p>
    </div>`).join("");
  log.scrollTop = log.scrollHeight;
}

async function start() {
  document.querySelector("#app").innerHTML = plantilla();
  bind();
  actualizarNucleo();
  actualizarLogo();
  await cargarEstadoPerfilador();
  await cargarVoces();
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    if (data.session) {
      state.session = data.session;
      try {
        await cargarTenantActual();
      } catch {
        await supabase.auth.signOut();
        state.session = null;
      }
    }
  }
  actualizarSesion();
}

start();
