// Widget embebible del orbe.
//
// La interfaz es un port de QUANTUM-ASISTENTE-
// (apps/desktop/src/orbe/Orbe.tsx, rama agent/navegador-integrado): mismos
// nombres de clase, mismos estados visuales, mismo selector de voces que
// elige y prueba al toque. Lo unico que se saca es todo lo de vision y
// pantallas, que en una landing no aplica.
//
// Lo que cambia por debajo: alla el orbe hablaba con Electron por
// `window.qh`; aca habla con LiveKit. La logica de conexion viene de
// frontend/demo/main.js, que ya estaba probada en produccion.
import { Room, RoomEvent, Track } from 'livekit-client';

const parametros = new URLSearchParams(location.search);
const API = parametros.get('api') || 'https://voz.quantumhive.com.ar';
const TENANT = parametros.get('tenant') || 'quantumhive';
const LOGO = parametros.get('logo') || '';

const $ = (id) => document.getElementById(id);
const orbe = $('orbe');

if (LOGO) $('logo').src = LOGO;

let sala = null;
let nivelElegido = 1;
let niveles = [];
let voces = [];
let vozElegida = '';
let vocesAbierto = false;
let temporizador = null;
let microfonoActivo = false;

// Los tres niveles estan operativos. El 3 (openai / "realismo extremo")
// se habilito el 2026-08-10 al crear el recurso de Azure OpenAI con el
// deployment gpt-realtime-mini. Si alguno se cae, sacarlo de este Set lo
// muestra deshabilitado con una nota en vez de fallar al conectar.
const NIVELES_LISTOS = new Set([1, 2, 3]);
const ETIQUETAS = { 1: 'Clonación', 2: 'Voz humana', 3: 'Realismo extremo' };

function estado(clave) {
  orbe.dataset.estado = clave;
}

function aviso(texto) {
  const el = $('aviso');
  if (!texto) {
    el.hidden = true;
    return;
  }
  el.textContent = texto;
  el.hidden = false;
}
$('aviso').onclick = () => aviso('');

// ---------- abrir / cerrar ----------

function abrir(v) {
  orbe.classList.toggle('orbe--abierto', v);
  parent.postMessage({ tipo: 'qh-widget-tamano', abierto: v }, '*');
}

$('esfera').onclick = () => abrir(!orbe.classList.contains('orbe--abierto'));

// ---------- motores (los tres planes) ----------

async function cargarNiveles() {
  try {
    const r = await fetch(`${API}/api/niveles`);
    niveles = (await r.json()).niveles;
  } catch {
    niveles = [
      { nivel: 1, titulo: 'Clonación', plan: 'basico' },
      { nivel: 2, titulo: 'Voz humana', plan: 'medio' },
      { nivel: 3, titulo: 'Realismo extremo', plan: 'premium' },
    ];
  }
  dibujarNiveles();
  mostrarSelectorDeVoces(nivelElegido === 2);
}

function dibujarNiveles() {
  const cont = $('motores');
  cont.innerHTML = '';
  for (const n of niveles) {
    const listo = NIVELES_LISTOS.has(n.nivel);
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'orbe__motor';
    b.setAttribute('role', 'radio');
    b.setAttribute('aria-checked', String(n.nivel === nivelElegido));
    b.disabled = !listo;
    b.dataset.nivel = String(n.nivel);
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
    b.setAttribute('aria-checked', String(Number(b.dataset.nivel) === numero));
  }
  mostrarSelectorDeVoces(numero === 2);
  // Cambiar de motor fija uno nuevo al reconectar: no se mezclan motores
  // dentro de una misma sala.
  if (sala) conectar();
}

// ---------- voces (solo el motor gemini) ----------
// Mismo patron que `elegirYProbarVoz` en el original: tocar un nombre lo
// elige Y lo prueba en el acto — aca reconectando, porque el saludo que
// dispara Receptor.on_enter en el agente es la prueba.

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
  if (!mostrar) {
    vocesAbierto = false;
    $('voces').hidden = true;
  }
}

function dibujarVoces() {
  const nombre = voces.find((v) => v.voz === vozElegida)?.nombre ?? '';
  $('voces-resumen-texto').textContent = nombre
    ? `Elegí quién querés que te atienda: ${nombre}`
    : 'Elegí quién querés que te atienda';
  $('voces-resumen-flecha').textContent = vocesAbierto ? '▴' : '▾';

  const cont = $('voces');
  cont.innerHTML = '';
  for (const v of voces) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'orbe__voz-chip';
    b.setAttribute('role', 'radio');
    b.dataset.activa = String(v.voz === vozElegida);
    b.title = `Elegir y escuchar a ${v.nombre}`;
    b.textContent = v.nombre;
    b.onclick = () => elegirYProbarVoz(v.voz);
    cont.append(b);
  }
}

$('voces-resumen').onclick = () => {
  vocesAbierto = !vocesAbierto;
  $('voces').hidden = !vocesAbierto;
  $('voces-resumen-flecha').textContent = vocesAbierto ? '▴' : '▾';
};

function elegirYProbarVoz(voz) {
  vozElegida = voz;
  // Se esconde al elegir, como en el original: el menu no ocupa el chat
  // todo el tiempo.
  vocesAbierto = false;
  $('voces').hidden = true;
  dibujarVoces();
  conectar();
}

// ---------- turnos ----------

function registro() {
  return $('registro');
}

function limpiarVacio() {
  const vacio = registro().querySelector('.orbe__vacio');
  if (vacio) vacio.remove();
}

// Lo que escribe el usuario llega completo de una.
function agregarTurno(quien, texto) {
  if (!texto?.trim()) return;
  limpiarVacio();
  const div = document.createElement('div');
  div.className = 'turno';
  div.dataset.quien = quien;
  div.textContent = texto;
  registro().append(div);
  registro().scrollTop = registro().scrollHeight;
}

// La transcripcion llega en fragmentos con el mismo id de segmento hasta
// que el ultimo trae final=true. Si se espera al final para recien mostrar
// algo, el audio ya arranco hace rato y el texto va atrasado. Por eso el
// turno se crea con el primer fragmento y se actualiza in-place — igual
// que el original, que iba pegando fragmentos al ultimo turno abierto.
const turnosEnCurso = new Map();

function actualizarTurno(quien, segmento) {
  if (!segmento.text?.trim()) return;
  let el = turnosEnCurso.get(segmento.id);
  if (!el) {
    limpiarVacio();
    el = document.createElement('div');
    el.className = 'turno';
    el.dataset.quien = quien;
    registro().append(el);
    turnosEnCurso.set(segmento.id, el);
  }
  el.textContent = segmento.text;
  registro().scrollTop = registro().scrollHeight;
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
    marcarMicrofono(false);
  });
  sala.on(RoomEvent.TranscriptionReceived, (segmentos, participante) => {
    const esAgente = participante?.identity !== sala.localParticipant.identity;
    for (const s of segmentos) actualizarTurno(esAgente ? 'copiloto' : 'yo', s);
  });
  sala.on(RoomEvent.ActiveSpeakersChanged, (activos) => {
    const agenteHabla = activos.some((p) => p.identity !== sala.localParticipant.identity);
    estado(agenteHabla ? 'hablando' : microfonoActivo ? 'escuchando' : 'lista');
  });

  try {
    await sala.connect(datos.url, datos.token);
    await sala.localParticipant.setMicrophoneEnabled(true);
    marcarMicrofono(true);
  } catch (e) {
    estado('error');
    aviso(`No se pudo conectar: ${e.message}`);
    return;
  }

  estado('escuchando');

  // Corte automatico: coincide con el limite del lado del servidor
  // (Config.max_session_seconds), asi el widget no queda esperando una
  // sala que el agente ya cerro.
  clearTimeout(temporizador);
  temporizador = setTimeout(() => {
    desconectar();
    aviso('La sesión llegó a su límite de tiempo. Prendé el micrófono para empezar otra.');
  }, (datos.duracion_maxima_seg ?? 240) * 1000);
}

async function desconectar({ silencioso = false } = {}) {
  clearTimeout(temporizador);
  if (sala) {
    await sala.disconnect();
    sala = null;
  }
  marcarMicrofono(false);
  if (!silencioso) estado('dormido');
}

// ---------- controles ----------

function marcarMicrofono(activo) {
  microfonoActivo = activo;
  $('mic').dataset.on = String(activo);
  $('mic-texto').textContent = `Micrófono ${activo ? 'ON' : 'OFF'}`;
  $('mic').title = activo ? 'Apagar micrófono' : 'Prender micrófono';
}

$('mic').onclick = async () => {
  // Igual que en el original: prender el microfono es lo que dispara el
  // saludo del agente, cada vez.
  if (!sala) {
    await conectar();
    return;
  }
  const proximo = !microfonoActivo;
  await sala.localParticipant.setMicrophoneEnabled(proximo);
  marcarMicrofono(proximo);
  estado(proximo ? 'escuchando' : 'lista');
};

$('freno').onclick = () => desconectar();

async function enviarTexto() {
  const input = $('borrador');
  const texto = input.value.trim();
  if (!texto) return;
  if (!sala) await conectar();
  if (!sala) return;
  agregarTurno('yo', texto);
  input.value = '';
  // El canal de datos de LiveKit lleva el texto al agente; el mismo Agent
  // que ya atiende voz lo procesa igual, via generate_reply.
  await sala.localParticipant.sendText(texto, { topic: 'lk.chat' });
}

$('enviar').onclick = enviarTexto;
$('borrador').onkeydown = (e) => {
  if (e.key === 'Enter') enviarTexto();
};

cargarNiveles();
cargarVoces();
