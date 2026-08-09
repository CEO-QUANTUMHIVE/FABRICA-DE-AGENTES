// Widget embebible del orbe.
//
// Logica de conexion a LiveKit portada de frontend/demo/main.js (ya
// probada en produccion): Room, TrackSubscribed, TranscriptionReceived,
// ActiveSpeakersChanged. El layout — orbe colapsado / panel expandido,
// selector de motor, marca por tenant — es el aporte nuevo de este
// archivo, con el lenguaje visual portado de QUANTUM-ASISTENTE-
// (apps/desktop/src/orbe/Orbe.tsx, rama agent/navegador-integrado).
import { Room, RoomEvent, Track } from 'livekit-client';

const parametros = new URLSearchParams(location.search);
const API = parametros.get('api') || 'https://voz.quantumhive.com.ar';
const TENANT = parametros.get('tenant') || 'quantumhive';
const LOGO = parametros.get('logo') || '';
const ACENTO = parametros.get('acento') || '';
const ACENTO2 = parametros.get('acento2') || '';

if (ACENTO) document.documentElement.style.setProperty('--qh-acento', ACENTO);
if (ACENTO2) document.documentElement.style.setProperty('--qh-acento-2', ACENTO2);
if (LOGO) {
  const marca = document.getElementById('marca-texto');
  const img = document.createElement('img');
  img.src = LOGO;
  img.alt = TENANT;
  marca.replaceWith(img);
}

const $ = (id) => document.getElementById(id);
const widget = $('widget');

let sala = null;
let nivelElegido = 1;
let niveles = [];
let voces = [];
let vozElegida = '';
let vocesAbierto = false;
let temporizador = null;
let microfonoActivo = false;

// Nivel 3 (openai / "realismo extremo") existe en el catalogo pero
// todavia no tiene credenciales de Azure en produccion. En vez de
// intentar conectar y fallar, se muestra deshabilitado con una nota.
// El dia que este listo, se saca esta linea — no hace falta tocar nada
// mas del widget.
const NIVELES_LISTOS = new Set([1, 2]);

function estado(clave) {
  widget.dataset.estado = clave;
}

function aviso(texto) {
  const el = $('aviso');
  if (!texto) { el.hidden = true; return; }
  el.textContent = texto;
  el.hidden = false;
}

// ---------- abrir/cerrar ----------

function abrir(v) {
  widget.classList.toggle('widget--abierto', v);
  parent.postMessage({ tipo: 'qh-widget-tamano', abierto: v }, '*');
  if (v && !sala && estado.actual !== 'conectando') conectar();
}

$('esfera').onclick = () => abrir(!widget.classList.contains('widget--abierto'));
$('cerrar').onclick = () => abrir(false);

// ---------- selector de motor ----------

async function cargarNiveles() {
  try {
    const r = await fetch(`${API}/api/niveles`);
    niveles = (await r.json()).niveles;
  } catch {
    niveles = [
      { nivel: 1, titulo: 'Clonación', descripcion: 'Voz clonada', plan: 'basico' },
      { nivel: 2, titulo: 'Voz humana', descripcion: 'Voz a voz natural', plan: 'medio' },
      { nivel: 3, titulo: 'Realismo extremo', descripcion: 'Máxima expresividad', plan: 'premium' },
    ];
  }
  dibujarNiveles();
}

const ETIQUETAS = { 1: 'Clonación', 2: 'Voz humana', 3: 'Realismo extremo' };

function dibujarNiveles() {
  const cont = $('motores');
  cont.innerHTML = '';
  for (const n of niveles) {
    const listo = NIVELES_LISTOS.has(n.nivel);
    const b = document.createElement('button');
    b.className = 'widget__motor';
    b.setAttribute('role', 'radio');
    b.setAttribute('aria-checked', String(n.nivel === nivelElegido));
    b.disabled = !listo;
    b.innerHTML = `${ETIQUETAS[n.nivel] ?? n.titulo}${listo ? '' : '<small>Pronto</small>'}`;
    b.onclick = () => elegirNivel(n.nivel);
    cont.append(b);
  }
}

function elegirNivel(numero) {
  if (!NIVELES_LISTOS.has(numero)) {
    aviso('Ese motor todavía no está disponible.');
    return;
  }
  nivelElegido = numero;
  for (const b of $('motores').children) {
    b.setAttribute('aria-checked', String(b.textContent.startsWith(ETIQUETAS[numero])));
  }
  mostrarSelectorDeVoces(numero === 2);
  // Cambiar de motor fija uno nuevo al reconectar: no se mezclan
  // motores dentro de una misma sala.
  if (sala) conectar();
}

// ---------- selector de voz (solo motor gemini) ----------
// Calcado del patron de QUANTUM-ASISTENTE- (Orbe.tsx: elegirYProbarVoz):
// tocar un nombre elige esa voz Y la prueba al toque, reconectando. El
// saludo que ya dispara Receptor.on_enter en el agente es la "prueba".

async function cargarVoces() {
  try {
    const r = await fetch(`${API}/api/voces-gemini`);
    voces = (await r.json()).voces;
  } catch {
    voces = [];
  }
  if (voces.length && !vozElegida) vozElegida = voces[0].voz;
  dibujarVoces();
}

function mostrarSelectorDeVoces(mostrar) {
  $('voces-resumen').hidden = !mostrar;
  $('voces').hidden = !mostrar || !vocesAbierto;
  if (!mostrar) { vocesAbierto = false; }
}

function dibujarVoces() {
  const nombreElegido = voces.find((v) => v.voz === vozElegida)?.nombre ?? '';
  $('voces-resumen-texto').textContent = nombreElegido
    ? `Elegí a tu asistente: ${nombreElegido}`
    : 'Elegí una voz';
  $('voces-resumen-flecha').textContent = vocesAbierto ? '▴' : '▾';

  const cont = $('voces');
  cont.innerHTML = '';
  for (const v of voces) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'widget__voz-chip';
    b.setAttribute('role', 'radio');
    b.dataset.activa = String(v.voz === vozElegida);
    b.title = `Elegir y escuchar a ${v.nombre}`;
    b.textContent = v.nombre;
    b.onclick = () => elegirYEscucharVoz(v.voz);
    cont.append(b);
  }
}

$('voces-resumen').onclick = () => {
  vocesAbierto = !vocesAbierto;
  $('voces').hidden = !vocesAbierto;
  $('voces-resumen-flecha').textContent = vocesAbierto ? '▴' : '▾';
};

function elegirYEscucharVoz(voz) {
  vozElegida = voz;
  vocesAbierto = false;
  $('voces').hidden = true;
  dibujarVoces();
  // Reconecta: sala nueva, Receptor.on_enter saluda de nuevo, y esta vez
  // con la voz elegida — asi se "prueba" con solo tocar el nombre.
  conectar();
}

// ---------- turnos ----------

// Los turnos que arma el usuario (texto escrito) llegan completos de una.
function agregarTurno(quien, texto) {
  if (!texto?.trim()) return;
  const registro = $('registro');
  const vacio = registro.querySelector('.widget__vacio');
  if (vacio) vacio.remove();
  const div = document.createElement('div');
  div.className = 'turno';
  div.dataset.quien = quien;
  div.textContent = texto;
  registro.append(div);
  registro.scrollTop = registro.scrollHeight;
}

// La transcripcion de LiveKit llega en fragmentos con el mismo id de
// segmento hasta que el ultimo trae final=true. Si esperamos al final
// para recien mostrar algo, el audio ya arranco hace rato y el texto se
// atrasa. Por eso el turno se crea con el primer fragmento y se va
// actualizando in-place, igual que ya se escucha el audio en vivo.
const turnosEnCurso = new Map(); // id de segmento -> elemento DOM

function actualizarTurno(quien, segmento) {
  if (!segmento.text?.trim()) return;
  const registro = $('registro');
  let el = turnosEnCurso.get(segmento.id);
  if (!el) {
    const vacio = registro.querySelector('.widget__vacio');
    if (vacio) vacio.remove();
    el = document.createElement('div');
    el.className = 'turno';
    el.dataset.quien = quien;
    registro.append(el);
    turnosEnCurso.set(segmento.id, el);
  }
  el.textContent = segmento.text;
  registro.scrollTop = registro.scrollHeight;
  if (segmento.final) turnosEnCurso.delete(segmento.id);
}

// ---------- conexion ----------

async function conectar() {
  aviso('');
  estado('conectando');
  await desconectar({ silencioso: true });

  let datos;
  try {
    const r = await fetch(`${API}/api/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nivel: nivelElegido, tenant: TENANT, voz: vozElegida || undefined }),
    });
    datos = await r.json();
    if (!r.ok) throw new Error(datos.error ?? 'No se pudo iniciar la sesión');
  } catch (e) {
    estado('error');
    aviso(e.message || 'No se pudo conectar. Reintentá en un momento.');
    return;
  }

  sala = new Room();

  sala.on(RoomEvent.TrackSubscribed, (track) => {
    if (track.kind === Track.Kind.Audio) track.attach().play();
  });
  sala.on(RoomEvent.Disconnected, () => {
    estado('dormido');
    $('cortar').disabled = true;
  });
  sala.on(RoomEvent.TranscriptionReceived, (segmentos, participante) => {
    const esAgente = participante?.identity !== sala.localParticipant.identity;
    for (const s of segmentos) {
      actualizarTurno(esAgente ? 'agente' : 'yo', s);
    }
  });
  sala.on(RoomEvent.ActiveSpeakersChanged, (activos) => {
    const agenteHabla = activos.some((p) => p.identity !== sala.localParticipant.identity);
    estado(agenteHabla ? 'hablando' : 'escuchando');
  });

  try {
    await sala.connect(datos.url, datos.token);
    await sala.localParticipant.setMicrophoneEnabled(true);
    microfonoActivo = true;
    $('mic').dataset.on = 'true';
  } catch (e) {
    estado('error');
    aviso(`No se pudo conectar: ${e.message}`);
    return;
  }

  estado('escuchando');
  $('cortar').disabled = false;

  // Corte automatico: coincide con el limite del lado del servidor
  // (Config.max_session_seconds), asi el widget no queda esperando una
  // sala que el agente ya cerro.
  clearTimeout(temporizador);
  temporizador = setTimeout(() => {
    desconectar();
    aviso('La sesión llegó a su límite de tiempo. Tocá el micrófono para empezar otra.');
  }, (datos.duracion_maxima_seg ?? 240) * 1000);
}

async function desconectar({ silencioso = false } = {}) {
  clearTimeout(temporizador);
  if (sala) {
    await sala.disconnect();
    sala = null;
  }
  microfonoActivo = false;
  $('mic').dataset.on = 'false';
  if (!silencioso) estado('dormido');
}

// ---------- controles ----------

$('mic').onclick = async () => {
  if (!sala) { await conectar(); return; }
  microfonoActivo = !microfonoActivo;
  await sala.localParticipant.setMicrophoneEnabled(microfonoActivo);
  $('mic').dataset.on = String(microfonoActivo);
};

$('cortar').onclick = () => desconectar();

async function enviarTexto() {
  const input = $('borrador');
  const texto = input.value.trim();
  if (!texto) return;
  if (!sala) await conectar();
  agregarTurno('yo', texto);
  input.value = '';
  // El canal de datos de LiveKit lleva el texto al agente; el mismo
  // Agent que ya atiende voz lo procesa igual, via generate_reply.
  await sala.localParticipant.sendText(texto, { topic: 'lk.chat' });
}

$('enviar').onclick = enviarTexto;
$('borrador').onkeydown = (e) => { if (e.key === 'Enter') enviarTexto(); };

cargarNiveles();
cargarVoces();
