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

  var params = new URLSearchParams({ api: origen, tenant: tenant });
  if (logo) params.set('logo', logo);
  if (acento) params.set('acento', acento);
  if (acento2) params.set('acento2', acento2);

  // Cerrado tiene que entrar el orbe (150px) + el halo que se sale del
  // borde + el cartel debajo. Abierto, el panel entero.
  var TAMANO_CERRADO = { ancho: 240, alto: 230 };

  var iframe = document.createElement('iframe');
  iframe.src = origen + '/widget.html?' + params.toString();
  iframe.title = 'Agente de ' + tenant;
  iframe.setAttribute('allow', 'microphone');
  iframe.style.cssText = [
    'position:fixed',
    'bottom:16px',
    'right:16px',
    'border:0',
    'z-index:2147483000',
    'background:transparent',
    'color-scheme:normal',
  ].join(';');

  function medir(t) {
    iframe.style.width = t.ancho + 'px';
    iframe.style.height = t.alto + 'px';
  }
  medir(TAMANO_CERRADO);

  // El iframe solo ocupa el tamano real del contenido — cerrado, la
  // esfera; abierto, el panel. Asi nunca tapa ni bloquea el resto de la
  // pagina del cliente, sin recurrir a trucos de pointer-events.
  window.addEventListener('message', function (ev) {
    if (ev.origin !== origen || !ev.data || ev.data.tipo !== 'qh-widget-tamano') return;
    medir(ev.data.abierto ? { ancho: 420, alto: 640 } : TAMANO_CERRADO);
  });

  document.body.appendChild(iframe);
})();
