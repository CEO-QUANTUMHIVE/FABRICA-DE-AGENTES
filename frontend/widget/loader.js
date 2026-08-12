// El unico fragmento que pega un cliente en su pagina:
//
//   <script src="https://voz.quantumhive.com.ar/widget.js"
//           data-tenant="quantumhive"
//           data-logo="https://.../logo.png"
//           defer></script>
//
// No hace nada mas que crear un iframe aislado y posicionarlo. Todo el
// peso real (livekit-client, la logica de conexion, el CSS) vive en
// widget.html, servido desde la misma infraestructura para todos los
// clientes: actualizar el widget no requiere que ningun cliente
// vuelva a pegar nada.
(function () {
  var actual = document.currentScript;
  if (!actual) return;

  var origen = new URL(actual.src).origin;
  var tenant = actual.getAttribute('data-tenant') || 'quantumhive';
  var logo = actual.getAttribute('data-logo') || '';
  var acento = actual.getAttribute('data-acento') || '';
  var acento2 = actual.getAttribute('data-acento-2') || '';
  var clonar = actual.getAttribute('data-clonar') || '';
  // La conversacion es siempre la misma. Esto solo elige su presencia
  // visual: el orbe original o un avatar de video configurado por tenant.
  var modo = actual.getAttribute('data-modo') === 'avatar' ? 'avatar' : 'orbe';
  var avatarBase = actual.getAttribute('data-avatar-base') || '';

  var params = new URLSearchParams({ api: origen, tenant: tenant });
  if (logo) params.set('logo', logo);
  if (acento) params.set('acento', acento);
  if (acento2) params.set('acento2', acento2);
  if (clonar) params.set('clonar', clonar);
  params.set('modo', modo);
  if (avatarBase) params.set('avatarBase', avatarBase);

  // En un celular el panel de 420x640 no entra, y el orbe de 240 tapa
  // media pantalla. Los tamanos se calculan contra el viewport real del
  // sitio del cliente — el iframe no puede consultarlo por su cuenta.
  var ESTRECHO = 520;

  function esCelular() {
    return window.innerWidth < ESTRECHO;
  }

  // Cerrado, el iframe tiene que dar para la onda mas grande del halo, que
  // se expande a 1.35 sobre el orbe mas su margen. Si queda mas chico, la
  // onda se recorta contra el borde y se ve un circulo cortado.
  //   escritorio  orbe 150 + margen 36 = 186 -> x1.35 = 251
  //   celular     orbe  88 + margen 24 = 112 -> x1.35 = 151
  // Al alto se le suma el cartel de abajo y el aire que la onda necesita
  // por arriba del orbe.
  function tamanoCerrado() {
    if (modo === 'avatar') {
      return esCelular() ? { ancho: 180, alto: 260 } : { ancho: 260, alto: 390 };
    }
    return esCelular() ? { ancho: 190, alto: 175 } : { ancho: 262, alto: 250 };
  }

  function tamanoAbierto() {
    if (!esCelular()) return { ancho: 420, alto: 640 };
    // Casi toda la pantalla, dejando los margenes de 12px de cada lado y
    // lugar arriba para que se siga viendo algo de la pagina.
    return {
      ancho: Math.min(420, window.innerWidth - 24),
      alto: Math.min(640, window.innerHeight - 90),
    };
  }

  var iframe = document.createElement('iframe');
  iframe.src = origen + '/widget.html?' + params.toString();
  iframe.title = 'Agente de ' + tenant;
  iframe.setAttribute('allow', 'microphone');
  iframe.style.cssText = [
    'position:fixed',
    'bottom:12px',
    'right:12px',
    'border:0',
    'z-index:2147483000',
    'background:transparent',
    'color-scheme:normal',
  ].join(';');

  var abierto = false;

  function medir() {
    var t = abierto ? tamanoAbierto() : tamanoCerrado();
    iframe.style.width = t.ancho + 'px';
    iframe.style.height = t.alto + 'px';
  }
  medir();

  // El iframe solo ocupa el tamano real del contenido — cerrado, la
  // esfera; abierto, el panel. Asi nunca tapa ni bloquea el resto de la
  // pagina del cliente, sin recurrir a trucos de pointer-events.
  window.addEventListener('message', function (ev) {
    if (ev.origin !== origen || !ev.data || ev.data.tipo !== 'qh-widget-tamano') return;
    abierto = !!ev.data.abierto;
    medir();
  });

  // Rotar el telefono cambia cual de los dos tamanos corresponde, y el
  // panel abierto se calcula contra el viewport: sin esto queda cortado
  // hasta que se cierre y se vuelva a abrir.
  window.addEventListener('resize', medir);

  document.body.appendChild(iframe);
})();
