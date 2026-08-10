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
// A donde lleva "Cloná tu propia voz". Todavia no existe la fabrica de
// voces, asi que por defecto cae a la landing; cuando exista, se cambia
// con data-clonar en el <script> del cliente sin tocar el widget.
const URL_CLONAR =
  parametros.get('clonar') || 'https://www.quantumhive.com.ar/#contacto';

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
  mostrarSelectorDeVoces(nivelElegido !== 1);
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
  // El pipeline (nivel 1) no tiene catalogo: su voz es la clonada del
  // tenant, no se elige de una lista.
  mostrarSelectorDeVoces(numero !== 1);
  cargarVoces().then(() => {
    // Cambiar de motor fija uno nuevo al reconectar: no se mezclan motores
    // dentro de una misma sala. Se reconecta despues de cargar el catalogo
    // para no pedir el token con una voz del motor anterior.
    if (sala) conectar();
  });
}

// ---------- voces (solo el motor gemini) ----------
// Tocar un nombre lo elige Y lo prueba en el acto, como en el original.
// Antes la prueba era reconectar, y eso costaba una sintesis por toque: con
// 10 voces, un curioso quemaba 10 saludos en medio minuto, y el TTS es el
// 86% del costo variable. Ahora suena un saludo pregrabado y cuesta cero.

// Cada motor tiene su propio catalogo: las voces de Gemini no existen en
// OpenAI y viceversa. El backend rechaza cruzarlas, asi que el catalogo se
// recarga cada vez que se cambia de motor.
const MOTOR_DE_NIVEL = { 1: 'pipeline', 2: 'gemini', 3: 'openai' };

async function cargarVoces() {
  const motor = MOTOR_DE_NIVEL[nivelElegido] ?? 'gemini';
  try {
    const r = await fetch(`${API}/api/voces?motor=${motor}`);
    voces = (await r.json()).voces;
  } catch {
    voces = [];
  }
  // Al cambiar de motor la voz anterior ya no existe en el catalogo nuevo.
  if (!voces.some((v) => v.voz === vozElegida)) {
    vozElegida = voces.length ? voces[0].voz : '';
  }
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
    ? `Elegí quién te atiende · ${nombre}`
    : 'Elegí quién querés que te atienda';
  $('voces-resumen-flecha').textContent = vocesAbierto ? '▴' : '▾';

  const cont = $('voces');
  cont.innerHTML = '';

  // Agrupadas por genero, con su titulo: la variedad de voces es parte de
  // lo que se vende, y en una grilla sin separar no se lee como variedad.
  for (const [genero, titulo] of [
    ['f', 'Mujeres'],
    ['m', 'Varones'],
  ]) {
    const delGrupo = voces.filter((v) => v.genero === genero);
    if (!delGrupo.length) continue;

    const cabecera = document.createElement('p');
    cabecera.className = 'orbe__voces-grupo';
    cabecera.textContent = titulo;
    cont.append(cabecera);

    const grilla = document.createElement('div');
    grilla.className = 'orbe__voces-grilla';
    for (const v of delGrupo) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'orbe__voz-chip';
      b.setAttribute('role', 'radio');
      b.dataset.activa = String(v.voz === vozElegida);
      b.title = `Elegir y escuchar a ${v.nombre}`;
      b.textContent = v.nombre;
      b.onclick = () => elegirYProbarVoz(v.voz);
      grilla.append(b);
    }
    cont.append(grilla);
  }

  // La clonacion es el paso siguiente del embudo: el visitante que llega
  // hasta aca eligiendo voces es justo el que puede querer la suya.
  const clonar = document.createElement('a');
  clonar.className = 'orbe__clonar';
  clonar.href = URL_CLONAR;
  clonar.target = '_blank';
  clonar.rel = 'noopener';
  clonar.textContent = '✨ Cloná tu propia voz';
  cont.append(clonar);
}

$('voces-resumen').onclick = () => {
  vocesAbierto = !vocesAbierto;
  $('voces').hidden = !vocesAbierto;
  $('voces-resumen-flecha').textContent = vocesAbierto ? '▴' : '▾';
  // El CSS apaga el latido de "mirame" una vez que lo abrieron.
  $('voces-resumen').setAttribute('aria-expanded', String(vocesAbierto));
};

// Un solo <audio> para todas las preescuchas. Si se creara uno por toque,
// tocar cinco nombres rapido superpondria cinco saludos.
const preescucha = new Audio();

function elegirYProbarVoz(voz) {
  vozElegida = voz;
  // Se esconde al elegir, como en el original: el menu no ocupa el chat
  // todo el tiempo.
  vocesAbierto = false;
  $('voces').hidden = true;
  dibujarVoces();

  // Ya conversando, la unica forma de cambiar de voz es rehacer la sala: el
  // saludo del agente con la voz nueva es la prueba de verdad.
  if (sala) {
    conectar();
    return;
  }

  // Sin sala no se conecta nada: suena el pregrabado. Este es el caso que
  // sangraba, el visitante que recorre el catalogo antes de hablar.
  const muestra = voces.find((v) => v.voz === voz)?.muestra;
  if (!muestra) return;
  preescucha.pause();
  preescucha.currentTime = 0;
  preescucha.src = muestra;
  // Si el archivo no esta, la voz queda elegida igual. A proposito no se cae
  // a conectar(): seria resucitar en silencio el costo que vinimos a matar.
  preescucha.play().catch(() => aviso('No se pudo reproducir la muestra.'));
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
