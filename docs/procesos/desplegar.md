# Desplegar

Son dos despliegues distintos, con reglas distintas. **Leé las dos reglas
duras antes de tocar nada.**

## Regla dura 1: la API y el agente van juntos, siempre

El nombre de sala es `demo-<tenant>-<motor>-<voz>-<aleatorio>`. La API lo
arma y el agente lo parsea por posición.

Si desplegás uno solo, el otro lee mal y el motor cae al default:

| Combinación | Qué pasa |
|---|---|
| API nueva + agente viejo | El agente lee el tenant donde espera el motor |
| Agente nuevo + API vieja | El nombre tiene menos partes y cae al default |

Las dos están rotas. Los dos servicios viven en la misma VM
(`motor-voz-agente`), así que es reiniciar `motor-voz-api` y
`motor-voz-agente` juntos.

El widget viejo **sí** es compatible con la API nueva: nunca parsea el nombre
de sala, solo pasa el token.

## Regla dura 2: el widget no sale sin las 18 muestras

Tocar un nombre en el selector reproduce un MP3 y **a propósito no cae de
vuelta a conectar** — eso sería revivir el costo que las muestras vinieron a
matar. Si falta un archivo, el chip da 404 y no pasa nada audible.

Antes de desplegar el widget:

```bash
uv run pytest tests/test_muestras.py -v
```

Si saltea en vez de pasar, faltan muestras. Ver
[grabar-muestras-de-voz.md](grabar-muestras-de-voz.md).

## Antes de reiniciar el agente: revisá el `.env` de la VM

Desde las Fases 5-8, `POST /api/token` **consulta Supabase en cada pedido** y
el agente resuelve el tenant en cada sesión. Si al `.env` de la VM le faltan
`SUPABASE_URL` o `SUPABASE_SERVICE_ROLE_KEY`, o la red falla, la demo entera
devuelve 503.

Eso se verifica **en la VM y antes** de reiniciar, no después.

Y la trampa de siempre: **nunca copies el `.env` local a producción.** El de
desarrollo tiene las credenciales de `livekit-server --dev`
(`devkey`/`secret`, 6 bytes). Con esas el agente arranca bien y LiveKit lo
rechaza con 401 recién al registrarse.

## API y agente, paso a paso

```bash
gcloud compute ssh motor-voz-agente --zone us-east1-b --tunnel-through-iap
```

En la VM, en `/home/sergio/motor-voz`:

```bash
git pull origin arquitectura/spec-motor-voz && .venv/bin/pip install -q -e . && sudo systemctl restart motor-voz-api motor-voz-agente
```

**`git pull` no instala dependencias, y en la VM no hay `uv`.** Cuando entró
`supabase` como dependencia nueva, el código estaba pero el paquete no: el
agente habría arrancado y muerto al importar. Por eso va el `pip install -e .`
en el medio, siempre.

**La API tarda unos 8 segundos en levantar.** Si verificás a los 5 vas a creer
que se rompió. Esperá 10 antes de dar nada por muerto.

Verificación mínima después de reiniciar:

```bash
curl -s http://localhost:8080/api/salud
```

Y que el worker diga `registered worker` en `journalctl -u motor-voz-agente`.

**Para volver atrás:** `git checkout <commit-anterior>`, el mismo
`pip install -e .`, y reiniciar los dos servicios.

## Widget

```bash
npm run build
```

En `frontend/widget/`. Después copiar `dist/*` más `loader.js` (renombrado a
`widget.js`) a `/var/www/widget/` en la VM `livekit-quantumhive`.

`/var/www/widget/` es del usuario `sergio`, así que **no hace falta sudo**.

**`gcloud compute scp --recurse` quiere el directorio padre como destino**, no
la carpeta a crear: `vm:/tmp/`, no `vm:/tmp/widget-nuevo`. Con lo segundo
falla con un `unable to open` que no explica nada.

**El orden importa:** copiá lo nuevo primero y borrá los hasheados viejos
después. Los nombres llevan hash, así que conviven sin pisarse. Al revés hay
un segundo sin assets, y eso lo ve un visitante.

```bash
cd /var/www/widget/assets && for f in *.js *.css *.png; do [ -e "/tmp/widget-nuevo/assets/$f" ] || rm -f "$f"; done
```

Las muestras no llevan hash, así que esas se pisan solas.

Y antes de todo, un backup que hace la vuelta atrás trivial:

```bash
cp -r /var/www/widget /tmp/widget-backup-$(date +%H%M)
```

## Después de desplegar

```bash
curl -s https://voz.quantumhive.com.ar/api/salud
```

Y comprobar que una muestra responda 200, no 404:

```bash
curl -sI https://voz.quantumhive.com.ar/assets/muestras/gemini-Puck.mp3
```

## La que nos costó una landing

**`gcloud run deploy --source .` sin comparar antes.** La carpeta local estaba
atrasada y pisó la landing viva, borrando una pestaña entera. Comparar siempre
contra el zip de fuente del deploy anterior en GCS antes de desplegar algo que
ya está vivo.
