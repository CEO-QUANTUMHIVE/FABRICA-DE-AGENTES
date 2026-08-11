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

## Widget

```bash
npm run build
```

En `frontend/widget/`. Después copiar `dist/*` más `loader.js` (renombrado a
`widget.js`) a `/var/www/widget/` en la VM `livekit-quantumhive`, por `scp`.

**Borrá los assets viejos:** los nombres llevan hash y se acumulan. Las
muestras no llevan hash, así que esas se pisan solas.

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
