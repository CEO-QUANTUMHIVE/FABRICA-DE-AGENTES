import { createClient } from "@supabase/supabase-js";
import "./app.css";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || "";
const configurado = Boolean(API_URL && SUPABASE_URL && SUPABASE_ANON_KEY);
const supabase = configurado ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null;

const app = document.querySelector("#app");
const nav = [
  ["inicio", "⌂", "Inicio"],
  ["ensenar", "✦", "Enseñar"],
  ["negocio", "▦", "Mi negocio"],
  ["conexiones", "⌘", "Conexiones"],
];

const state = {
  demo: false,
  session: null,
  page: "inicio",
  tenants: [],
  tenant: null,
  conocimiento: [],
  installEvent: null,
  trainingMode: "ensenar",
  trainingMessages: [
    { from: "agent", text: "Contame qué querés corregir. Puede ser una palabra, mi tono, una pronunciación o una respuesta que no te gustó." },
  ],
  pendingChanges: [],
  catalog: [
    { type: "Servicio", name: "Consulta personalizada", category: "Consultas", price: "25.000", stock: "Sin límite", detail: "Incluye diagnóstico" },
    { type: "Producto", name: "Kit de cuidado", category: "Cuidado", price: "18.500", stock: "12", detail: "Stock sujeto a disponibilidad" },
  ],
  catalogImportMessage: "",
  showPasteCatalog: false,
  connectorCategory: "Todos",
  connectionQuery: "",
  connectedConnectors: ["whatsapp"],
  connectionSetup: null,
  showCustomMcp: false,
  helpOpen: false,
  helpMessages: [
    { from: "agent", text: "Hola. Soy la guía del panel. Preguntame cómo cargar tu catálogo, conectar una herramienta o enseñarle algo a tu agente." },
  ],
};

const demoTenant = { id: "demo", slug: "quantumhive", nombre: "QuantumHive", rol: "dueño" };
const demoKnowledge = [
  { id: "h1", categoria: "horario", clave: "atencion", titulo: "Horarios de atención", version_publicada_id: "v1", versiones: [{ id: "v1", numero: 1, contenido: { lunes_a_viernes: "9:00 a 18:00" } }] },
  { id: "p1", categoria: "precio", clave: "consulta", titulo: "Precio de la consulta", version_publicada_id: "v2", versiones: [{ id: "v2", numero: 2, contenido: { valor: 25000, moneda: "ARS" } }] },
  { id: "f1", categoria: "faq", clave: "reserva", titulo: "¿Cómo reservo un turno?", version_publicada_id: "v3", versiones: [{ id: "v3", numero: 1, contenido: { respuesta: "Podés reservar directamente por WhatsApp." } }] },
];

const connectorCatalog = [
  { id: "google-business", icon: "📍", name: "Google Maps y reseñas", category: "Presencia online", kind: "Google", description: "Ubicación, horarios, información del local y reseñas del negocio." },
  { id: "whatsapp", icon: "◉", name: "WhatsApp", category: "Mensajería", kind: "Canal", description: "Atención y confirmaciones desde el número del negocio." },
  { id: "sheets", icon: "▦", name: "Google Sheets", category: "Planillas", kind: "Google", description: "Leer y actualizar listas, stock, clientes y precios autorizados." },
  { id: "excel", icon: "X", name: "Microsoft Excel", category: "Planillas", kind: "Microsoft", description: "Trabajar con archivos Excel guardados en OneDrive o SharePoint." },
  { id: "tiendanube", icon: "TN", name: "Tiendanube", category: "Ventas", kind: "API", description: "Productos, stock, pedidos y seguimiento de compras." },
  { id: "mercadolibre", icon: "ML", name: "Mercado Libre", category: "Ventas", kind: "API", description: "Publicaciones, preguntas, stock y ventas." },
  { id: "mercadopago", icon: "MP", name: "Mercado Pago", category: "Pagos y cobros", kind: "Pagos", description: "Crear cobros, consultar pagos y recibir confirmaciones." },
  { id: "payway", icon: "PW", name: "Payway", category: "Pagos y cobros", kind: "Pagos", description: "Checkout, tarjetas, cuotas y operaciones de cobro online." },
  { id: "uala-bis", icon: "U", name: "Ualá Bis", category: "Pagos y cobros", kind: "Pagos", description: "Cobros online y links de pago para compartir con clientes." },
  { id: "modo", icon: "M", name: "MODO", category: "Pagos y cobros", kind: "Revisión", description: "Cobros con MODO cuando la cuenta y modalidad del comercio sean compatibles." },
  { id: "google-calendar", icon: "G", name: "Google Calendar", category: "Calendarios", kind: "OAuth", description: "Disponibilidad, reservas, reprogramaciones y cancelaciones." },
  { id: "gmail", icon: "✉", name: "Gmail", category: "Productividad", kind: "MCP", description: "Consultar y preparar correos autorizados." },
  { id: "notion", icon: "N", name: "Notion", category: "Productividad", kind: "MCP", description: "Usar páginas y bases como conocimiento del agente." },
  { id: "calendar-custom", icon: "📅", name: "Tu calendario actual", category: "Calendarios", kind: "Adaptable", description: "Adaptamos la agenda que tu negocio ya usa, sin obligarte a cambiarla." },
  { id: "outlook-calendar", icon: "O", name: "Outlook Calendar", category: "Calendarios", kind: "OAuth", description: "Turnos y disponibilidad de Microsoft 365." },
  { id: "calendly", icon: "C", name: "Calendly", category: "Calendarios", kind: "API", description: "Tipos de evento, horarios libres y reservas." },
  { id: "cal-com", icon: "Cal", name: "Cal.com", category: "Calendarios", kind: "API", description: "Agenda abierta y automatización de turnos." },
  { id: "shopify", icon: "S", name: "Shopify", category: "Ventas", kind: "API", description: "Catálogo, inventario, clientes y pedidos." },
  { id: "woocommerce", icon: "W", name: "WooCommerce", category: "Ventas", kind: "API", description: "Productos, stock y pedidos de la tienda." },
  { id: "stripe", icon: "S", name: "Stripe", category: "Pagos y cobros", kind: "Pagos", description: "Checkout, links de pago, pagos únicos y suscripciones donde esté disponible." },
  { id: "payment-links", icon: "$", name: "Links y QR de cobro", category: "Pagos y cobros", kind: "Adaptable", description: "El agente genera o comparte el link de la plataforma que ya usa el negocio." },
  { id: "instagram", icon: "◎", name: "Instagram", category: "Mensajería", kind: "Canal", description: "Mensajes y consultas desde la cuenta del negocio." },
  { id: "facebook", icon: "f", name: "Facebook Messenger", category: "Mensajería", kind: "Canal", description: "Mensajes de la página atendidos por el mismo agente." },
  { id: "drive", icon: "D", name: "Google Drive", category: "Productividad", kind: "MCP", description: "Buscar información en archivos del negocio." },
  { id: "airtable", icon: "A", name: "Airtable", category: "CRM y datos", kind: "MCP", description: "Consultar y actualizar registros del negocio." },
  { id: "hubspot", icon: "H", name: "HubSpot", category: "CRM y datos", kind: "MCP", description: "Contactos, negocios y seguimiento comercial." },
  { id: "slack", icon: "#", name: "Slack", category: "Productividad", kind: "MCP", description: "Avisos internos y consultas en canales autorizados." },
];

function escape(value = "") {
  return String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

function initials(value = "QH") {
  return value.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}

async function api(path, options = {}) {
  const token = state.session?.access_token;
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...options.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || "No se pudo completar la operación.");
  return body;
}

function renderLogin() {
  app.innerHTML = `
    <main class="login-shell">
      <section class="login-brand">
        <div class="brand"><span class="brand-mark">Q</span> QuantumHive</div>
        <div class="login-copy">
          <h1>Tu negocio,<br><span class="gradient-text">más inteligente.</span></h1>
          <p>Enseñale a tu agente, revisá cómo atiende y seguí todo desde un solo lugar.</p>
        </div>
        <small class="sub">Un mismo panel en tu computadora y tu celular.</small>
      </section>
      <section class="login-side">
        <form class="login-card" id="login-form">
          <h2>Bienvenido</h2>
          <p>Ingresá para administrar tu agente.</p>
          <label class="field">Correo electrónico<input name="email" type="email" autocomplete="email" placeholder="tu@negocio.com" required></label>
          <label class="field">Contraseña<input name="password" type="password" autocomplete="current-password" placeholder="••••••••" required></label>
          <button class="primary full" type="submit">Entrar a mi agente</button>
          <p class="form-message" id="login-message"></p>
          <div class="divider">VISTA DE DISEÑO</div>
          <button class="secondary full" id="demo-button" type="button">Explorar el panel</button>
        </form>
      </section>
    </main>`;

  document.querySelector("#demo-button").addEventListener("click", () => {
    state.demo = true;
    state.tenants = [demoTenant];
    state.tenant = demoTenant;
    state.conocimiento = demoKnowledge;
    renderShell();
  });
  document.querySelector("#login-form").addEventListener("submit", signIn);
}

function renderAccountActivation() {
  const email = state.session?.user?.email || "tu correo";
  app.innerHTML = `
    <main class="login-shell activation-shell">
      <section class="login-brand">
        <div class="brand"><span class="brand-mark">Q</span> QuantumHive</div>
        <div class="login-copy">
          <span class="eyebrow">Tu agente está listo</span>
          <h1>Activá tu<br><span class="gradient-text">panel de control.</span></h1>
          <p>La cuenta quedará vinculada solamente a los negocios que te hayan asignado.</p>
        </div>
        <small class="sub">La invitación es personal y se utiliza una sola vez.</small>
      </section>
      <section class="login-side">
        <form class="login-card" id="activation-form">
          <span class="activation-check">✓</span>
          <h2>Creá tu contraseña</h2>
          <p>Estás activando el acceso para <strong>${escape(email)}</strong>.</p>
          <label class="field">Nueva contraseña<input name="password" type="password" minlength="10" autocomplete="new-password" placeholder="Mínimo 10 caracteres" required></label>
          <label class="field">Repetir contraseña<input name="confirmation" type="password" minlength="10" autocomplete="new-password" placeholder="Repetí la contraseña" required></label>
          <button class="primary full" type="submit">Activar mi panel</button>
          <p class="form-message" id="activation-message"></p>
          <small class="security-copy">QuantumHive nunca te enviará una contraseña por correo ni te pedirá que la compartas.</small>
        </form>
      </section>
    </main>`;
  document.querySelector("#activation-form").addEventListener("submit", activateAccount);
}

async function activateAccount(event) {
  event.preventDefault();
  const message = document.querySelector("#activation-message");
  const data = new FormData(event.currentTarget);
  const password = String(data.get("password") || "");
  if (password !== data.get("confirmation")) {
    message.textContent = "Las contraseñas no coinciden.";
    return;
  }
  if (password.length < 10) {
    message.textContent = "Usá al menos 10 caracteres.";
    return;
  }
  message.textContent = "Activando tu cuenta…";
  const { error } = await supabase.auth.updateUser({ password });
  if (error) {
    message.textContent = "No pudimos activar la cuenta. Pedí una nueva invitación.";
    return;
  }
  window.history.replaceState({}, document.title, window.location.pathname);
  try {
    await loadTenants();
    renderShell();
  } catch {
    message.textContent = "La contraseña quedó creada, pero todavía no tenés un negocio asignado.";
  }
}

async function signIn(event) {
  event.preventDefault();
  const message = document.querySelector("#login-message");
  if (!configurado) {
    message.textContent = "El login real se habilita al configurar la URL pública y la clave anónima de Supabase.";
    return;
  }
  const data = new FormData(event.currentTarget);
  message.textContent = "Validando…";

  let auth;
  try {
    const respuesta = await supabase.auth.signInWithPassword({
      email: data.get("email"), password: data.get("password"),
    });
    if (respuesta.error) throw respuesta.error;
    auth = respuesta.data;
  } catch (error) {
    // El motivo real, no "revisá el correo y la contraseña". Un email sin
    // confirmar da ese mismo cartel y te manda a probar claves durante media
    // hora buscando un problema que no existe.
    message.textContent = `No pudimos ingresar: ${error?.message || "error desconocido"}`;
    return;
  }

  state.session = auth.session;
  try {
    await loadTenants();
  } catch (error) {
    // Sin esto, cualquier falla al cargar los negocios deja el cartel en
    // "Validando…" para siempre y no hay forma de saber que paso. Pasó en
    // producción con la API apuntada a un host que no existía.
    state.session = null;
    message.textContent =
      `Entraste, pero no pudimos cargar tus negocios: ${error?.message || "error de red"}. ` +
      `API: ${API_URL}`;
    return;
  }
  renderShell();
}

async function loadTenants() {
  const data = await api("/api/panel/tenants");
  state.tenants = data.tenants;
  state.tenant = state.tenants[0] || null;
  if (state.tenant) await loadKnowledge();
}

async function loadKnowledge() {
  if (state.demo) return;
  const data = await api(`/api/panel/${encodeURIComponent(state.tenant.slug)}/conocimiento`);
  state.conocimiento = data.conocimiento;
}

function navButtons(className = "") {
  return nav.map(([id, icon, label], index) => `
    <button class="nav-button ${state.page === id ? "active" : ""} ${className}" data-page="${id}">
      <span class="nav-icon">${icon}</span><span>${label}</span>
    </button>`).join("");
}

function renderShell() {
  const tenant = state.tenant || { nombre: "Sin negocio", slug: "" };
  app.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand"><span class="brand-mark">Q</span> QuantumHive</div>
        <nav class="nav">${navButtons()}</nav>
        <div class="sidebar-footer">
          <div class="agent-mini"><strong>${escape(tenant.nombre)}</strong><span><i class="status-dot"></i>Agente activo</span></div>
          <button class="ghost" id="logout">Cerrar sesión</button>
        </div>
      </aside>
      <section class="main">
        <header class="topbar">
          <select class="tenant-select" id="tenant-select" aria-label="Negocio">${state.tenants.map((item) => `<option value="${escape(item.slug)}" ${item.slug === tenant.slug ? "selected" : ""}>${escape(item.nombre || item.slug)}</option>`).join("")}</select>
          <div class="top-actions">
            <button class="secondary install-button" id="install" hidden>Instalar app</button>
            <button class="ghost" id="help">✦ Guía</button>
            <div class="avatar">${initials(tenant.nombre)}</div>
          </div>
        </header>
        <main class="content" id="page">${pageContent()}</main>
      </section>
    </div>
    <nav class="mobile-nav">${navButtons()}</nav>
    ${state.helpOpen ? helpPanel() : ""}
    ${state.connectionSetup ? connectionSetupModal() : ""}`;
  bindShell();
}

function helpPanel() {
  const messages = state.helpMessages.map((message) => `<div class="message ${message.from === "user" ? "me" : ""}">${escape(message.text)}</div>`).join("");
  return `<div class="drawer-backdrop" id="close-help-backdrop">
    <aside class="help-drawer" role="dialog" aria-modal="true" aria-label="Guía del panel" onclick="event.stopPropagation()">
      <header class="help-head"><div><span class="eyebrow">Asistente de uso</span><h2>Te acompaño paso a paso</h2></div><button class="ghost" id="close-help" aria-label="Cerrar">×</button></header>
      <div class="quick-help">
        <button data-help-question="¿Cómo cargo mi catálogo?">Cargar catálogo</button>
        <button data-help-question="¿Cómo conecto Mercado Pago?">Conectar una cuenta</button>
        <button data-help-question="¿Cómo corrijo al agente?">Corregir al agente</button>
      </div>
      <div class="messages help-messages">${messages}</div>
      <form class="composer" id="help-form"><input name="message" placeholder="Preguntame cómo usar el panel…" autocomplete="off" required><button class="primary">Enviar</button></form>
    </aside>
  </div>`;
}

function demoBanner() {
  return state.demo ? `<div class="demo-banner"><span><strong>Vista de diseño.</strong> Podés recorrer y probar el panel sin modificar un agente real.</span><button class="ghost" id="exit-demo">Salir</button></div>` : "";
}

function pageHead(eyebrow, title, subtitle, action = "") {
  return `<header class="page-head"><div><span class="eyebrow">${eyebrow}</span><h1>${title}</h1><p class="sub">${subtitle}</p></div>${action}</header>`;
}

function pageContent() {
  if (!state.tenant) return `${pageHead("Panel", "Todavía no tenés un agente", "Cuando vinculemos tu negocio va a aparecer acá.")}<div class="card empty">No hay negocios asociados a esta cuenta.</div>`;
  const pages = { inicio: metricsPage, ensenar: teachPage, negocio: businessPage, conexiones: connectionsPage };
  return pages[state.page]();
}

function metricsPage() {
  const values = state.demo ? ["1.284", "94%", "38 s", "126"] : ["—", "—", "—", "—"];
  return `${pageHead("Resumen", "Así está trabajando tu agente", "Actividad unificada de todos tus canales.", `<button class="secondary">Últimos 30 días ▾</button>`)}
    ${demoBanner()}
    <section class="stats">
      ${[["Conversaciones", values[0], "+18% este mes"], ["Resueltas sin ayuda", values[1], "+4% este mes"], ["Primera respuesta", values[2], "12 s más rápido"], ["Nuevos contactos", values[3], "+22% este mes"]].map(([label, value, trend]) => `<article class="card stat"><span class="stat-label">${label}</span><strong class="stat-value">${value}</strong><span class="trend">${state.demo ? trend : "Esperando datos reales"}</span></article>`).join("")}
    </section>
    <section class="grid-2">
      <article class="card"><div class="card-head"><h2>Conversaciones</h2><span class="sub">por día</span></div><div class="chart">${[48,72,55,92,68,82,61,95,76,87,70,98].map((height, index) => `<div class="bar-group"><i class="bar" style="height:${state.demo ? height : 4}%"></i><i class="bar alt" style="height:${state.demo ? Math.max(20, height - 28) : 2}%"></i></div>`).join("")}</div></article>
      <article class="card"><div class="card-head"><h2>Canales</h2><span class="sub">actividad</span></div><div class="channel-list">${channelRows()}</div></article>
    </section>`;
}

function channelRows() {
  const rows = [["◉", "WhatsApp", "Próxima conexión", "Pendiente"], ["◎", "Web", "Agente en tu sitio", "Activo"], ["◇", "Instagram", "Próxima etapa", "Pendiente"], ["□", "Facebook", "Próxima etapa", "Pendiente"]];
  return rows.map(([icon, name, detail, status]) => `<div class="channel"><span class="channel-icon">${icon}</span><div><strong>${name}</strong><span>${detail}</span></div><span class="pill ${status === "Pendiente" ? "pending" : ""}">${status}</span></div>`).join("");
}

function memoriesPage() {
  return `${pageHead("Memoria", "Lo que tu agente recuerda", "Vas a poder aprobar, corregir u olvidar cada dato.")} ${demoBanner()}<div class="card empty"><h2>Memorias verificables</h2><p>Este módulo se activará cuando conectemos las sesiones y conversaciones reales. No vamos a inventar recuerdos ni guardarlos sin origen.</p></div>`;
}

function chatPage() {
  return `${pageHead("Modo privado", "Hablá con tu propio agente", "Consultale cómo está atendiendo o probá una respuesta antes de publicarla.")} ${demoBanner()}<section class="card chat-shell"><div class="messages"><div class="message">Hola. Soy el mismo agente que atiende tu negocio, pero acá estamos en privado. El chat interno se conectará en el próximo bloque.</div><div class="message me">¿Qué preguntas están haciendo más seguido?</div><div class="message">Cuando tengamos conversaciones reales, voy a responder con métricas y fuentes del negocio.</div></div><form class="composer" id="chat-form"><input placeholder="Escribile a tu agente…" disabled><button class="primary" disabled>Enviar</button></form></section>`;
}

function latestVersion(piece) {
  return piece.versiones?.[0] || null;
}

function teachPage() {
  const messages = state.trainingMessages.map((message) => `<div class="message ${message.from === "user" ? "me" : ""}">${escape(message.text)}</div>`).join("");
  const pending = state.pendingChanges.length
    ? state.pendingChanges.map((change, index) => `<div class="change-item"><span>${escape(change.text)}</span><button class="ghost remove-change" data-index="${index}" aria-label="Quitar cambio">×</button></div>`).join("")
    : `<div class="empty compact">Cuando le pidas una corrección, aparecerá acá antes de aplicarla.</div>`;
  const isTest = state.trainingMode === "probar";
  return `${pageHead("Tu agente", "Enseñale hablando", "Corregilo como corregirías a una persona de tu equipo.")}
    ${demoBanner()}
    <div class="mode-switch" role="tablist">
      <button class="mode-button ${!isTest ? "active" : ""}" data-mode="ensenar">✦ Enseñar</button>
      <button class="mode-button ${isTest ? "active" : ""}" data-mode="probar">▶ Probar como cliente</button>
    </div>
    <section class="coach-layout">
      <article class="card coach-chat">
        <div class="coach-head"><span class="agent-orb">Q</span><div><strong>${isTest ? "Modo cliente" : "Tu agente"}</strong><small>${isTest ? "Hacé una consulta como si fueras un cliente real" : "Explicale qué querés cambiar"}</small></div></div>
        <div class="messages" id="training-messages">${messages}</div>
        <form class="composer" id="training-chat-form"><input name="message" placeholder="${isTest ? "Ej: Hola, ¿cuánto cuesta el servicio?" : "Ej: No digas barato; decí accesible…"}" autocomplete="off" required><button class="primary">Enviar</button></form>
      </article>
      <aside class="card changes-panel">
        <div class="card-head"><div><span class="eyebrow">Cambios pendientes</span><h2>${state.pendingChanges.length} correcciones</h2></div></div>
        <div class="changes-list">${pending}</div>
        <div class="apply-area">
          <p class="form-message" id="apply-message"></p>
          <button class="secondary full" id="test-changes" ${state.pendingChanges.length ? "" : "disabled"}>▶ Probar cambios</button>
          <button class="primary full" id="apply-changes" ${state.pendingChanges.length ? "" : "disabled"}>Aplicar cambios</button>
          <small>Hasta tocar “Aplicar”, tu agente real no cambia.</small>
        </div>
      </aside>
    </section>`;
}

function businessPage() {
  const rows = state.catalog.map((row, index) => `<tr>
    <td><select data-row="${index}" data-field="type"><option ${row.type === "Servicio" ? "selected" : ""}>Servicio</option><option ${row.type === "Producto" ? "selected" : ""}>Producto</option></select></td>
    <td><input data-row="${index}" data-field="name" value="${escape(row.name)}" placeholder="Nombre"></td>
    <td><input data-row="${index}" data-field="category" value="${escape(row.category || "")}" placeholder="Categoría"></td>
    <td><input data-row="${index}" data-field="price" value="${escape(row.price)}" placeholder="0"></td>
    <td><input data-row="${index}" data-field="stock" value="${escape(row.stock || "")}" placeholder="Opcional"></td>
    <td><input data-row="${index}" data-field="detail" value="${escape(row.detail)}" placeholder="Detalle opcional"></td>
    <td><button class="ghost delete-row" data-index="${index}" aria-label="Eliminar">×</button></td>
  </tr>`).join("");
  return `${pageHead("Mi negocio", "Productos, servicios y precios", "Cargá todo tu catálogo de la forma que te resulte más cómoda.", `<button class="secondary" id="add-row">+ Agregar fila</button>`)}
    ${demoBanner()}
    <section class="catalog-import-grid">
      <article class="card import-card"><span class="import-icon">⇧</span><div><h2>Subir un catálogo</h2><p>Foto, PDF, CSV o planilla. Primero lo convertimos en borrador para que puedas revisarlo.</p></div><label class="secondary import-button">Elegir archivo<input id="catalog-file" type="file" accept="image/*,.pdf,.csv,.xlsx,.xls" hidden></label></article>
      <article class="card import-card"><span class="import-icon">≡</span><div><h2>Pegar una lista</h2><p>Copiá precios desde un mensaje, documento o planilla y separalos por línea.</p></div><button class="secondary" id="toggle-paste-catalog">Pegar productos</button></article>
      <article class="card import-card"><span class="import-icon">X</span><div><h2>Conectar una planilla</h2><p>Sincronizá Google Sheets o Excel para mantener precios y stock actualizados.</p></div><button class="secondary" id="connect-spreadsheet">Ver planillas</button></article>
    </section>
    ${state.showPasteCatalog ? `<form class="card paste-catalog" id="paste-catalog-form"><label class="field">Pegá una línea por producto o servicio<textarea name="catalogText" placeholder="Alisado Plex; 45.000; Servicios\nShampoo nutritivo; 12.500; Productos"></textarea></label><div class="button-row"><button class="ghost" type="button" id="cancel-paste-catalog">Cancelar</button><button class="primary" type="submit">Armar borrador</button></div></form>` : ""}
    ${state.catalogImportMessage ? `<div class="import-message">${escape(state.catalogImportMessage)}</div>` : ""}
    <article class="card table-card">
      <div class="table-title"><div><span class="eyebrow">Borrador editable</span><h2>${state.catalog.length} productos y servicios</h2></div><span class="pill pending">Revisar antes de publicar</span></div>
      <div class="table-scroll"><table class="catalog-table"><thead><tr><th>Tipo</th><th>Nombre</th><th>Categoría</th><th>Precio</th><th>Stock</th><th>Detalle</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="table-actions"><span class="sub">Nada llega al agente hasta que revises y guardes los cambios.</span><button class="primary" id="save-catalog">Guardar y publicar</button></div>
    </article>`;
}

function connectionsPage() {
  const categories = ["Todos", ...new Set(connectorCatalog.map((connector) => connector.category))];
  return `${pageHead("Conexiones", "Encontrá una herramienta para tu agente", "Las más usadas por pymes primero: ubicación, mensajes, planillas, ventas, cobros y agenda.", `<button class="secondary" id="custom-mcp-button">+ Agregar MCP</button>`)}
    ${demoBanner()}
    <section class="connector-search card">
      <span class="search-icon">⌕</span>
      <input id="connector-search" value="${escape(state.connectionQuery)}" placeholder="Buscar Maps, Excel, Mercado Pago, Tiendanube…" autocomplete="off">
      <kbd>⌘ K</kbd>
    </section>
    <nav class="category-chips" aria-label="Categorías">${categories.map((category) => `<button class="category-chip ${state.connectorCategory === category ? "active" : ""}" data-category="${escape(category)}">${escape(category)}</button>`).join("")}</nav>
    <div class="catalog-summary"><strong id="connector-count"></strong><button class="ghost" id="connected-filter">Ver conectadas (${state.connectedConnectors.length})</button></div>
    <section class="connections-grid" id="connector-grid">${connectorCards()}</section>
    ${state.showCustomMcp ? customMcpPanel() : ""}`;
}

function filteredConnectors() {
  const query = state.connectionQuery.trim().toLowerCase();
  return connectorCatalog.filter((connector) => {
    const inCategory = state.connectorCategory === "Todos" || connector.category === state.connectorCategory;
    const haystack = `${connector.name} ${connector.description} ${connector.category} ${connector.kind}`.toLowerCase();
    return inCategory && (!query || haystack.includes(query));
  });
}

function connectorCards() {
  const connectors = filteredConnectors();
  if (!connectors.length) return `<div class="empty catalog-empty"><h2>No encontramos esa herramienta</h2><p>Podés agregar un MCP personalizado o pedirnos que creemos el conector.</p><button class="secondary" id="empty-custom-mcp">Agregar MCP personalizado</button></div>`;
  return connectors.map((connector) => {
    const connected = state.connectedConnectors.includes(connector.id);
    return `<article class="card connection-card">
      <div class="connector-top"><span class="connection-logo">${connector.icon}</span><span class="connector-kind">${escape(connector.kind)}</span></div>
      <div><h2>${escape(connector.name)}</h2><span class="connector-category">${escape(connector.category)}</span><p>${escape(connector.description)}</p></div>
      <button class="${connected ? "connected-button" : "secondary"} connection-action" data-connector="${escape(connector.id)}">${connected ? "✓ Conectado" : "Conectar"}</button>
    </article>`;
  }).join("");
}

function customMcpPanel() {
  return `<article class="card custom-mcp-panel">
    <div><span class="eyebrow">MCP personalizado</span><h2>Agregar otra herramienta</h2><p class="sub">La conexión se revisa antes de habilitarla para proteger los datos y las acciones de tu negocio.</p></div>
    <form id="custom-mcp-form"><label class="field">Nombre de la herramienta<input name="name" placeholder="Ej: Agenda de Jaz" required></label><label class="field">Dirección del servidor MCP o documentación<input name="url" type="url" placeholder="https://…" required></label><div class="button-row"><button class="ghost" type="button" id="cancel-custom-mcp">Cancelar</button><button class="primary" type="submit">Enviar para revisión</button></div></form>
  </article>`;
}

function connectionSetupModal() {
  const connector = connectorCatalog.find((item) => item.id === state.connectionSetup);
  if (!connector) return "";
  const permissions = connectionPermissions(connector);
  const usesAccountLogin = ["OAuth", "Google", "Microsoft", "Pagos", "Canal", "API"].includes(connector.kind);
  return `<div class="modal-backdrop" id="close-connection-backdrop">
    <section class="card connection-modal" role="dialog" aria-modal="true" aria-label="Conectar ${escape(connector.name)}" onclick="event.stopPropagation()">
      <header class="connection-modal-head"><span class="connection-logo">${connector.icon}</span><div><span class="eyebrow">Conexión guiada</span><h2>Conectar ${escape(connector.name)}</h2></div><button class="ghost" id="close-connection" aria-label="Cerrar">×</button></header>
      <div class="connection-explainer">
        <strong>${usesAccountLogin ? `Vas a ingresar en ${escape(connector.name)} y autorizar únicamente lo que el agente necesita.` : "Te vamos a pedir los datos que entrega esta herramienta."}</strong>
        <p>${usesAccountLogin ? "QuantumHive no recibe tu contraseña. La plataforma confirma el permiso y después probamos la conexión." : "Si requiere una clave, URL o servidor MCP, la conexión queda en revisión antes de activarse."}</p>
      </div>
      <div class="permission-list"><span class="eyebrow">Permisos propuestos</span>${permissions.map((permission, index) => `<label><input type="checkbox" ${index < 3 ? "checked" : ""}> <span>${escape(permission)}</span></label>`).join("")}</div>
      <div class="modal-actions"><button class="ghost" id="cancel-connection">Cancelar</button><button class="primary" id="authorize-connection" data-connector="${escape(connector.id)}">${usesAccountLogin ? `Continuar en ${escape(connector.name)}` : "Revisar conexión"}</button></div>
      <small class="connection-note">Las acciones sensibles, como devolver dinero, cancelar ventas o cambiar precios, requieren confirmación.</small>
    </section>
  </div>`;
}

function connectionPermissions(connector) {
  if (connector.category === "Pagos y cobros") return ["Crear links u órdenes de cobro", "Consultar el estado de los pagos", "Confirmar una reserva cuando se acredita", "Preparar devoluciones con aprobación"];
  if (connector.id === "mercadolibre") return ["Leer publicaciones, precios y stock", "Responder preguntas autorizadas", "Consultar pedidos y envíos", "Proponer cambios de precio o stock"];
  if (connector.category === "Calendarios") return ["Consultar horarios disponibles", "Crear y reprogramar turnos", "Cancelar únicamente con confirmación"];
  if (connector.category === "Planillas") return ["Leer la planilla seleccionada", "Sincronizar precios y stock", "Escribir solamente en hojas autorizadas"];
  return ["Consultar información necesaria", "Realizar acciones autorizadas", "Guardar un registro de cada acción"];
}

function bindShell() {
  document.querySelectorAll("[data-page]").forEach((button) => button.addEventListener("click", () => {
    state.page = button.dataset.page;
    renderShell();
  }));
  document.querySelector("#logout")?.addEventListener("click", signOut);
  document.querySelector("#exit-demo")?.addEventListener("click", () => { state.demo = false; state.tenants = []; state.tenant = null; renderLogin(); });
  document.querySelector("#tenant-select")?.addEventListener("change", changeTenant);
  document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => switchTrainingMode(button.dataset.mode)));
  document.querySelector("#training-chat-form")?.addEventListener("submit", handleTrainingMessage);
  document.querySelector("#test-changes")?.addEventListener("click", () => switchTrainingMode("probar"));
  document.querySelector("#apply-changes")?.addEventListener("click", applyPendingChanges);
  document.querySelectorAll(".remove-change").forEach((button) => button.addEventListener("click", () => removePendingChange(Number(button.dataset.index))));
  document.querySelector("#add-row")?.addEventListener("click", addCatalogRow);
  document.querySelectorAll("[data-row][data-field]").forEach((input) => input.addEventListener("change", updateCatalogCell));
  document.querySelectorAll(".delete-row").forEach((button) => button.addEventListener("click", () => deleteCatalogRow(Number(button.dataset.index))));
  document.querySelector("#save-catalog")?.addEventListener("click", saveCatalog);
  document.querySelector("#catalog-file")?.addEventListener("change", importCatalogFile);
  document.querySelector("#toggle-paste-catalog")?.addEventListener("click", () => { state.showPasteCatalog = true; renderShell(); });
  document.querySelector("#cancel-paste-catalog")?.addEventListener("click", () => { state.showPasteCatalog = false; renderShell(); });
  document.querySelector("#paste-catalog-form")?.addEventListener("submit", importPastedCatalog);
  document.querySelector("#connect-spreadsheet")?.addEventListener("click", openSpreadsheetConnections);
  document.querySelectorAll(".connection-action:not([disabled])").forEach((button) => button.addEventListener("click", requestConnection));
  document.querySelector("#connector-search")?.addEventListener("input", filterConnectorCatalog);
  document.querySelectorAll(".category-chip").forEach((button) => button.addEventListener("click", () => selectConnectorCategory(button.dataset.category)));
  document.querySelector("#custom-mcp-button")?.addEventListener("click", showCustomMcp);
  document.querySelector("#empty-custom-mcp")?.addEventListener("click", showCustomMcp);
  document.querySelector("#cancel-custom-mcp")?.addEventListener("click", hideCustomMcp);
  document.querySelector("#custom-mcp-form")?.addEventListener("submit", submitCustomMcp);
  document.querySelector("#connected-filter")?.addEventListener("click", showConnectedConnectors);
  document.querySelector("#help")?.addEventListener("click", () => { state.helpOpen = true; renderShell(); });
  document.querySelector("#close-help")?.addEventListener("click", closeHelp);
  document.querySelector("#close-help-backdrop")?.addEventListener("click", closeHelp);
  document.querySelector("#help-form")?.addEventListener("submit", handleHelpMessage);
  document.querySelectorAll("[data-help-question]").forEach((button) => button.addEventListener("click", () => answerHelpQuestion(button.dataset.helpQuestion)));
  document.querySelector("#close-connection")?.addEventListener("click", closeConnectionSetup);
  document.querySelector("#cancel-connection")?.addEventListener("click", closeConnectionSetup);
  document.querySelector("#close-connection-backdrop")?.addEventListener("click", closeConnectionSetup);
  document.querySelector("#authorize-connection")?.addEventListener("click", authorizeConnection);
  updateConnectorCount();
  const install = document.querySelector("#install");
  if (state.installEvent && install) install.hidden = false;
  install?.addEventListener("click", installApp);
}

async function changeTenant(event) {
  state.tenant = state.tenants.find((tenant) => tenant.slug === event.target.value);
  await loadKnowledge();
  renderShell();
}

async function saveDraft(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const message = document.querySelector("#knowledge-message");
  const data = Object.fromEntries(new FormData(form));
  const payload = { categoria: data.categoria, clave: data.titulo.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 100), titulo: data.titulo, contenido: { texto: data.texto }, motivo: data.motivo };
  message.textContent = "Guardando…";
  try {
    if (state.demo) {
      state.conocimiento.unshift({ id: crypto.randomUUID(), ...payload, version_publicada_id: null, versiones: [{ id: crypto.randomUUID(), numero: 1, contenido: payload.contenido }] });
    } else {
      await api(`/api/panel/${encodeURIComponent(state.tenant.slug)}/conocimiento/borradores`, { method: "POST", body: JSON.stringify(payload) });
      await loadKnowledge();
    }
    form.reset();
    renderShell();
  } catch (error) {
    message.textContent = error.message;
  }
}

function switchTrainingMode(mode) {
  state.trainingMode = mode;
  state.trainingMessages.push({
    from: "agent",
    text: mode === "probar"
      ? "Listo. Hablame como si fueras un cliente y te contesta tu agente real, con la información de tu negocio."
      : "Volvimos a Enseñar. Decime qué querés que cambie de la respuesta que acabás de probar.",
  });
  renderShell();
}

async function handleTrainingMessage(event) {
  event.preventDefault();
  const input = new FormData(event.currentTarget).get("message").trim();
  if (!input) return;
  state.trainingMessages.push({ from: "user", text: input });

  if (state.trainingMode === "ensenar") {
    // Enseñar sigue siendo local hasta que toques Aplicar: una corrección es
    // un borrador, y un borrador no cambia al agente que está atendiendo.
    state.pendingChanges.push({ text: input, categoria: "tono" });
    state.trainingMessages.push({
      from: "agent",
      text: `Anotado: “${input}”. Queda pendiente — tocá Probar cambios para escucharlo, y recién Aplicar lo publica.`,
    });
    renderShell();
    return;
  }

  // Modo cliente: habla el agente de verdad, con el conocimiento del negocio.
  if (state.demo) {
    state.trainingMessages.push({ from: "agent", text: "Vista de diseño: no hay agente real conectado." });
    renderShell();
    return;
  }

  state.trainingMessages.push({ from: "agent", text: "…", pending: true });
  renderShell();

  // El historial que ya se dijo, para que no se presente de nuevo en cada turno.
  const historial = state.trainingMessages
    .filter((m) => !m.pending)
    .slice(-20)
    .map((m) => ({ rol: m.from === "user" ? "user" : "assistant", texto: m.text }));

  try {
    const data = await api(`/api/panel/${encodeURIComponent(state.tenant.slug)}/chat`, {
      method: "POST",
      body: JSON.stringify({ mensaje: input, historial: historial.slice(0, -1), modo: "cliente" }),
    });
    state.trainingMessages.pop();
    state.trainingMessages.push({ from: "agent", text: data.respuesta });
  } catch (error) {
    // Nunca un globo colgado: el "…" se reemplaza siempre, aunque falle.
    state.trainingMessages.pop();
    state.trainingMessages.push({
      from: "agent",
      text: `No pude responder: ${error.message}`,
    });
  }
  renderShell();
}

function removePendingChange(index) {
  state.pendingChanges.splice(index, 1);
  renderShell();
}

async function applyPendingChanges() {
  const message = document.querySelector("#apply-message");
  const changes = [...state.pendingChanges];
  if (!changes.length) return;
  message.textContent = "Aplicando…";
  try {
    if (!state.demo) {
      for (const [index, change] of changes.entries()) {
        const draft = await api(`/api/panel/${encodeURIComponent(state.tenant.slug)}/conocimiento/borradores`, {
          method: "POST",
          body: JSON.stringify({
            categoria: change.categoria,
            clave: `correccion-${Date.now()}-${index}`,
            titulo: "Corrección enseñada por el dueño",
            contenido: { instruccion: change.text },
            motivo: "Corrección conversada y probada en el panel",
          }),
        });
        await api(`/api/panel/${encodeURIComponent(state.tenant.slug)}/conocimiento/${encodeURIComponent(draft.borrador.version_id)}/publicar`, {
          method: "POST",
          body: JSON.stringify({ motivo: "Aplicada desde el modo Enseñar" }),
        });
      }
      await loadKnowledge();
    }
    state.pendingChanges = [];
    state.trainingMessages.push({ from: "agent", text: "Listo. Los cambios quedaron aplicados y guardados en el historial. Si algo no funciona como esperabas, podemos volver a la versión anterior." });
    renderShell();
  } catch (error) {
    message.textContent = error.message;
  }
}

function addCatalogRow() {
  state.catalog.push({ type: "Servicio", name: "", category: "", price: "", stock: "", detail: "" });
  renderShell();
}

async function importCatalogFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (extension === "csv") {
    const text = await file.text();
    const imported = catalogRowsFromText(text);
    if (imported.length) state.catalog.push(...imported);
    state.catalogImportMessage = imported.length
      ? `Importamos ${imported.length} filas de ${file.name}. Revisalas antes de publicar.`
      : `No encontramos filas válidas en ${file.name}. Podés pegarlas manualmente.`;
  } else {
    state.catalogImportMessage = `${file.name} quedó listo para extracción inteligente. La foto, PDF o Excel se convertirá en un borrador editable cuando conectemos el procesador de archivos.`;
  }
  renderShell();
}

function importPastedCatalog(event) {
  event.preventDefault();
  const text = new FormData(event.currentTarget).get("catalogText");
  const imported = catalogRowsFromText(text);
  if (imported.length) state.catalog.push(...imported);
  state.showPasteCatalog = false;
  state.catalogImportMessage = imported.length
    ? `Armamos ${imported.length} filas nuevas. Corregilas en la tabla y después publicalas.`
    : "No pudimos separar esa lista. Probá usando una línea por producto y separando nombre y precio con punto y coma.";
  renderShell();
}

function catalogRowsFromText(text = "") {
  return String(text).split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
    const cells = line.split(/[;\t,]/).map((cell) => cell.trim()).filter(Boolean);
    if (!cells.length) return null;
    const priceIndex = cells.findIndex((cell) => /(?:\$\s*)?\d[\d.\s]*(?:,\d{1,2})?/.test(cell));
    const name = cells[0];
    const price = priceIndex > 0 ? cells[priceIndex].replace(/^\$\s*/, "") : "";
    const category = cells.find((cell, index) => index !== 0 && index !== priceIndex && !/^\d+$/.test(cell)) || "";
    return name ? { type: /servicio|tratamiento|turno/i.test(category) ? "Servicio" : "Producto", name, category, price, stock: "", detail: "" } : null;
  }).filter(Boolean);
}

function openSpreadsheetConnections() {
  state.page = "conexiones";
  state.connectorCategory = "Planillas";
  state.connectionQuery = "";
  renderShell();
}

function updateCatalogCell(event) {
  state.catalog[Number(event.target.dataset.row)][event.target.dataset.field] = event.target.value;
}

function deleteCatalogRow(index) {
  state.catalog.splice(index, 1);
  renderShell();
}

async function saveCatalog(event) {
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "Guardando…";
  try {
    if (!state.demo) {
      for (const [index, row] of state.catalog.entries()) {
        if (!row.name.trim()) continue;
        const key = row.name.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 80) || `item-${index}`;
        const draft = await api(`/api/panel/${encodeURIComponent(state.tenant.slug)}/conocimiento/borradores`, {
          method: "POST",
          body: JSON.stringify({ categoria: "servicio", clave: key, titulo: row.name, contenido: { tipo: row.type, categoria: row.category, precio: row.price, stock: row.stock, detalle: row.detail }, motivo: "Actualización desde Mi negocio" }),
        });
        await api(`/api/panel/${encodeURIComponent(state.tenant.slug)}/conocimiento/${encodeURIComponent(draft.borrador.version_id)}/publicar`, { method: "POST", body: JSON.stringify({ motivo: "Lista de precios actualizada" }) });
      }
    }
    button.textContent = "✓ Guardado";
    setTimeout(() => { button.disabled = false; button.textContent = "Guardar cambios"; }, 1400);
  } catch (error) {
    button.disabled = false;
    button.textContent = error.message;
  }
}

function requestConnection(event) {
  const connectorId = event.currentTarget.dataset.connector;
  if (!connectorId) return;
  const connected = state.connectedConnectors.includes(connectorId);
  if (connected) {
    state.connectedConnectors = state.connectedConnectors.filter((id) => id !== connectorId);
    renderShell();
  } else {
    state.connectionSetup = connectorId;
    renderShell();
  }
}

function closeConnectionSetup() {
  state.connectionSetup = null;
  renderShell();
}

function authorizeConnection(event) {
  const connectorId = event.currentTarget.dataset.connector;
  if (state.demo && connectorId && !state.connectedConnectors.includes(connectorId)) {
    state.connectedConnectors.push(connectorId);
  }
  state.connectionSetup = null;
  renderShell();
}

function closeHelp() {
  state.helpOpen = false;
  renderShell();
}

function handleHelpMessage(event) {
  event.preventDefault();
  const input = event.currentTarget.elements.message;
  const question = input.value.trim();
  if (question) answerHelpQuestion(question);
}

function answerHelpQuestion(question) {
  const normalized = question.toLowerCase();
  let answer = "Puedo guiarte por Inicio, Enseñar, Mi negocio y Conexiones. Decime qué querés hacer y te indico dónde entrar y qué botón tocar.";
  if (/catálogo|catalogo|precio|producto|servicio|archivo|foto|pdf|excel/.test(normalized)) {
    answer = "Entrá en Mi negocio. Podés subir una foto, PDF, CSV o planilla; pegar una lista; o conectar Excel y Google Sheets. Siempre se arma un borrador para que revises los datos antes de publicarlos.";
  } else if (/mercado pago|conectar|conexión|conexion|mcp|calendar|calendario/.test(normalized)) {
    answer = "Entrá en Conexiones, buscá la herramienta y tocá Conectar. Te voy a mostrar qué permisos necesita; después iniciás sesión en la plataforma y autorizás. Las acciones sensibles quedan sujetas a confirmación.";
  } else if (/correg|enseñar|entren|pronuncia|tono|palabra/.test(normalized)) {
    answer = "Entrá en Enseñar y hablale al agente como a una persona. Después tocá Probar cambios. Si la respuesta quedó bien, recién ahí usá Aplicar cambios.";
  }
  state.helpMessages.push({ from: "user", text: question }, { from: "agent", text: answer });
  state.helpOpen = true;
  renderShell();
}

function filterConnectorCatalog(event) {
  state.connectionQuery = event.target.value;
  const grid = document.querySelector("#connector-grid");
  if (grid) grid.innerHTML = connectorCards();
  grid?.querySelectorAll(".connection-action").forEach((button) => button.addEventListener("click", requestConnection));
  grid?.querySelector("#empty-custom-mcp")?.addEventListener("click", showCustomMcp);
  updateConnectorCount();
}

function updateConnectorCount() {
  const count = document.querySelector("#connector-count");
  if (count) count.textContent = state.connectorCategory === "Todos" && !state.connectionQuery
    ? `${filteredConnectors().length} herramientas recomendadas para pymes`
    : `${filteredConnectors().length} conexiones encontradas`;
}

function selectConnectorCategory(category) {
  state.connectorCategory = category;
  renderShell();
}

function showConnectedConnectors() {
  state.connectionQuery = "";
  state.connectorCategory = "Todos";
  const connected = new Set(state.connectedConnectors);
  const grid = document.querySelector("#connector-grid");
  if (grid) grid.innerHTML = connectorCatalog.filter((connector) => connected.has(connector.id)).map((connector) => `<article class="card connection-card"><div class="connector-top"><span class="connection-logo">${connector.icon}</span><span class="connector-kind">${escape(connector.kind)}</span></div><div><h2>${escape(connector.name)}</h2><span class="connector-category">${escape(connector.category)}</span><p>${escape(connector.description)}</p></div><button class="connected-button connection-action" data-connector="${escape(connector.id)}">✓ Conectado</button></article>`).join("") || `<div class="empty catalog-empty">Todavía no hay conexiones activas.</div>`;
  grid?.querySelectorAll(".connection-action").forEach((button) => button.addEventListener("click", requestConnection));
  const count = document.querySelector("#connector-count");
  if (count) count.textContent = `${state.connectedConnectors.length} conexiones activas`;
}

function showCustomMcp() {
  state.showCustomMcp = true;
  renderShell();
  document.querySelector("#custom-mcp-form input")?.focus();
}

function hideCustomMcp() {
  state.showCustomMcp = false;
  renderShell();
}

function submitCustomMcp(event) {
  event.preventDefault();
  const data = new FormData(event.currentTarget);
  const button = event.currentTarget.querySelector("button[type='submit']");
  button.textContent = `✓ ${data.get("name")} enviado`;
  button.disabled = true;
}

async function publishVersion(event) {
  const versionId = event.currentTarget.dataset.version;
  if (!versionId) return;
  event.currentTarget.disabled = true;
  event.currentTarget.textContent = "Publicando…";
  try {
    if (state.demo) {
      const piece = state.conocimiento.find((item) => item.versiones?.some((version) => version.id === versionId));
      if (piece) piece.version_publicada_id = versionId;
    } else {
      await api(`/api/panel/${encodeURIComponent(state.tenant.slug)}/conocimiento/${encodeURIComponent(versionId)}/publicar`, { method: "POST", body: JSON.stringify({ motivo: "Publicado desde el panel" }) });
      await loadKnowledge();
    }
    renderShell();
  } catch (error) {
    event.currentTarget.disabled = false;
    event.currentTarget.textContent = error.message;
  }
}

async function signOut() {
  if (supabase && state.session) await supabase.auth.signOut();
  Object.assign(state, { demo: false, session: null, page: "inicio", tenants: [], tenant: null, conocimiento: [], pendingChanges: [] });
  renderLogin();
}

async function installApp() {
  if (!state.installEvent) return;
  await state.installEvent.prompt();
  state.installEvent = null;
  renderShell();
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  state.installEvent = event;
  const button = document.querySelector("#install");
  if (button) button.hidden = false;
});

function authFlowType() {
  const hash = new URLSearchParams(window.location.hash.slice(1));
  const query = new URLSearchParams(window.location.search);
  return hash.get("type") || query.get("type") || "";
}

async function start() {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`);
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    if (data.session) {
      state.session = data.session;
      if (["invite", "recovery"].includes(authFlowType())) {
        renderAccountActivation();
        return;
      }
      try {
        await loadTenants();
        renderShell();
        return;
      } catch {
        await supabase.auth.signOut();
      }
    }
  }
  renderLogin();
}

start();
