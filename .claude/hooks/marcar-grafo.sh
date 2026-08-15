#!/usr/bin/env bash
# Anota que el grafo ya se consulto en esta sesion, para que el recordatorio
# de `grafo-primero.sh` deje de aparecer.
#
# Corre despues de cada Bash. Solo marca si el comando fue realmente una
# consulta al grafo: si marcara con cualquier cosa, el recordatorio se
# apagaria solo en el primer `ls` y no serviria para nada.

ENTRADA=$(cat)
case "$ENTRADA" in
  *graphify*) ;;
  *) exit 0 ;;
esac

MARCA="${TMPDIR:-/tmp}/grafo-consultado-$(date +%Y%m%d)-${CLAUDE_SESSION_ID:-sin-sesion}"
touch "$MARCA"
exit 0
