import { Room, RoomEvent, Track } from 'livekit-client';

const URL_LIVEKIT = 'ws://localhost:7880';

const $ = (id) => document.getElementById(id);
const estado = (texto) => { $('estado').textContent = texto; };

let sala = null;

$('conectar').onclick = async () => {
  const token = $('token').value.trim();
  if (!token) { estado('falta el token'); return; }

  sala = new Room();

  sala.on(RoomEvent.TrackSubscribed, (track) => {
    if (track.kind === Track.Kind.Audio) {
      track.attach().play();
      estado('conectado — hablá');
    }
  });
  sala.on(RoomEvent.Disconnected, () => estado('desconectado'));

  estado('conectando...');
  await sala.connect(URL_LIVEKIT, token);
  await sala.localParticipant.setMicrophoneEnabled(true);
  estado('conectado — hablá');

  $('silenciar').disabled = false;
  $('cortar').disabled = false;
};

$('silenciar').onclick = async () => {
  const activo = sala.localParticipant.isMicrophoneEnabled;
  await sala.localParticipant.setMicrophoneEnabled(!activo);
  $('silenciar').textContent = activo ? 'Activar micrófono' : 'Silenciar micrófono';
};

$('cortar').onclick = async () => {
  await sala.disconnect();
  $('silenciar').disabled = true;
  $('cortar').disabled = true;
};
