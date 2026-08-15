#!/usr/bin/env bash
# El grafo primero: recordatorio con dientes.
#
# La regla 1 del CLAUDE.md estaba escrita desde el primer dia y un agente la
# ignoro igual durante una sesion entera, leyendo archivos completos a mano.
# Un texto en un documento no cambia el comportamiento; un mensaje delante de
# cada busqueda, si.
#
# No bloquea: avisa. Bloquear haria imposible el caso legitimo —el grafo no
# conoce lo que no esta commiteado— y un hook que estorba se termina sacando.

MARCA="${TMPDIR:-/tmp}/grafo-consultado-$(date +%Y%m%d)-${CLAUDE_SESSION_ID:-sin-sesion}"

# graphify deja rastro cuando se lo consulta: si ya paso en esta sesion, callar.
if [ -f "$MARCA" ]; then
  exit 0
fi

cat <<'AVISO' >&2
[grafo-primero] Todavia no consultaste el grafo en esta sesion.

  graphify query "<lo que estas buscando>" --budget 700

Cuesta ~700 tokens y te dice archivo, linea y relaciones. Explorar a ciegas
cuesta cincuenta veces eso, y lo paga Sergio. Ver CLAUDE.md, regla 1.

Si el grafo no sabe (codigo sin commitear, otro repo), decilo y segui.
AVISO

exit 0
