import { Room, RoomEvent, Track } from 'livekit-client';

const API = import.meta.env.VITE_API ?? 'http://localhost:8080';

// El tenant se puede fijar por la URL para probar el aislamiento a oido:
//   http://localhost:5173/            -> quantumhive (el default del backend)
//   http://localhost:5173/?tenant=demo_capilar
//
// Solo en esta pagina de demo. El widget que embeben los clientes NO manda
// tenant: el suyo sale del dominio donde esta instalado.
//
// La voz del tenant solo se escucha en el NIVEL 1. Gemini y OpenAI hablan
// con una voz de su propio catalogo, no con la voz clonada del negocio.
const TENANT = new URLSearchParams(location.search).get('tenant') ?? '';

const $ = (id) => document.getElementById(id);
let sala = null;
let nivelElegido = 1;
let niveles = [];
let temporizador = null;

// ---------- estado visual ----------

const ESTADOS = {
  desconectado: 'Elegí un nivel y tocá Hablar',
  conectando: 'Conectando…',
  escuchando: 'Te escucho, hablá',
  pensando: 'Pensando…',
  hablando: 'Hablando',
};

function estado(clave, textoExtra) {
  $('orbe').dataset.estado = clave;
  $('estado').textContent = textoExtra ?? ESTADOS[clave] ?? clave;
}

function aviso(texto) {
  const el = $('aviso');
  if (!texto) { el.hidden = true; return; }
  el.textContent = texto;
  el.hidden = false;
}

// ---------- panel desplegable ----------

function abrirPanel(abrir) {
  $('panel').dataset.abierto = abrir ? 'si' : 'no';
  $('alternar-panel').setAttribute('aria-expanded', String(abrir));
  $('lengueta-texto').textContent = abrir ? 'Ocultar conversación' : 'Ver conversación';
}

$('alternar-panel').onclick = () =>
  abrirPanel($('panel').dataset.abierto !== 'si');
$('cerrar-panel').onclick = () => abrirPanel(false);

function agregarTurno(quien, texto) {
  if (!texto?.trim()) return;
  const div = document.createElement('div');
  div.className = `turno turno--${quien === 'Vos' ? 'vos' : 'agente'}`;
  div.innerHTML = `<span class="turno__quien"></span><span class="turno__texto"></span>`;
  div.querySelector('.turno__quien').textContent = quien;
  div.querySelector('.turno__texto').textContent = texto;
  $('transcripcion').append(div);
  $('transcripcion').scrollTop = $('transcripcion').scrollHeight;
}

// ---------- selector de niveles ----------

async function cargarNiveles() {
  try {
    const r = await fetch(`${API}/api/niveles`);
    niveles = (await r.json()).niveles;
  } catch {
    // Si la API no responde, la demo igual dibuja algo en vez de quedar vacia.
    niveles = [
      { nivel: 1, titulo: 'Básico', descripcion: 'Voz sintetizada sobre texto.', plan: 'basico' },
      { nivel: 2, titulo: 'Natural', descripcion: 'Voz a voz.', plan: 'medio' },
      { nivel: 3, titulo: 'Humano', descripcion: 'Voz a voz de máxima expresividad.', plan: 'premium' },
    ];
    aviso('No se pudo contactar la API. ¿Está corriendo el servidor de tokens?');
  }
  dibujarNiveles();
  elegirNivel(1);
}

function dibujarNiveles() {
  $('selector').innerHTML = '';
  for (const n of niveles) {
    const b = document.createElement('button');
    b.className = 'nivel';
    b.dataset.nivel = n.nivel;
    b.setAttribute('role', 'radio');
    b.setAttribute('aria-checked', 'false');
    // Las barras crecen con el nivel: es el "volumen" de humanidad.
    const barras = Array.from({ length: 3 }, (_, i) =>
      `<span class="nivel__barra" style="height:${(i + 1) * 33}%;visibility:${i < n.nivel ? 'visible' : 'hidden'}"></span>`
    ).join('');
    b.innerHTML = `${n.titulo}<span class="nivel__barras">${barras}</span>`;
    b.onclick = () => elegirNivel(n.nivel);
    $('selector').append(b);
  }
}

function elegirNivel(numero) {
  nivelElegido = numero;
  const n = niveles.find((x) => x.nivel === numero);
  for (const b of $('selector').children) {
    b.setAttribute('aria-checked', String(Number(b.dataset.nivel) === numero));
  }
  $('nivel-descripcion').textContent = n?.descripcion ?? '';
  $('nivel-plan').textContent = n ? `plan ${n.plan}` : '';

  // Cambiar de nivel es cambiar de motor, y el motor se fija al abrir la
  // sesion. Por eso se reconecta: no se puede cambiar a mitad de camino.
  if (sala) {
    estado('conectando', 'Cambiando de nivel…');
    conectar();
  }
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
      body: JSON.stringify({ nivel: nivelElegido, ...(TENANT && { tenant: TENANT }) }),
    });
    datos = await r.json();
    if (!r.ok) throw new Error(datos.error ?? 'No se pudo iniciar la sesión');
  } catch (e) {
    estado('desconectado');
    aviso(e.message);
    return;
  }

  sala = new Room();

  sala.on(RoomEvent.TrackSubscribed, (track) => {
    if (track.kind === Track.Kind.Audio) track.attach().play();
  });
  sala.on(RoomEvent.Disconnected, () => {
    estado('desconectado');
    botones(false);
  });
  // Las transcripciones alimentan el panel de arriba.
  sala.on(RoomEvent.TranscriptionReceived, (segmentos, participante) => {
    const esAgente = participante?.identity !== sala.localParticipant.identity;
    for (const s of segmentos) {
      if (s.final) agregarTurno(esAgente ? 'Agente' : 'Vos', s.text);
    }
  });
  sala.on(RoomEvent.ActiveSpeakersChanged, (activos) => {
    const agenteHabla = activos.some((p) => p.identity !== sala.localParticipant.identity);
    estado(agenteHabla ? 'hablando' : 'escuchando');
  });

  try {
    await sala.connect(datos.url, datos.token);
    await sala.localParticipant.setMicrophoneEnabled(true);
  } catch (e) {
    estado('desconectado');
    aviso(`No se pudo conectar: ${e.message}`);
    return;
  }

  estado('escuchando');
  botones(true);

  // Corte automatico: la demo es publica y cada minuto cuesta plata.
  clearTimeout(temporizador);
  temporizador = setTimeout(() => {
    desconectar();
    aviso('La demo se corta a los pocos minutos. Volvé a tocar Hablar para seguir.');
  }, (datos.duracion_maxima_seg ?? 240) * 1000);
}

async function desconectar({ silencioso = false } = {}) {
  clearTimeout(temporizador);
  if (sala) {
    await sala.disconnect();
    sala = null;
  }
  if (!silencioso) {
    estado('desconectado');
    botones(false);
  }
}

function botones(conectado) {
  $('hablar').textContent = conectado ? 'Reconectar' : 'Hablar';
  $('silenciar').disabled = !conectado;
  $('cortar').disabled = !conectado;
}

// ---------- acciones ----------

$('hablar').onclick = conectar;
$('cortar').onclick = () => desconectar();
$('silenciar').onclick = async () => {
  const activo = sala.localParticipant.isMicrophoneEnabled;
  await sala.localParticipant.setMicrophoneEnabled(!activo);
  $('silenciar').textContent = activo ? 'Activar micrófono' : 'Silenciar';
};

cargarNiveles();
