# Grabar muestras de voz

Cada voz del catálogo tiene un saludo pregrabado. Existen para que tocar un
nombre en el selector **no cueste una síntesis**: antes cada toque reconectaba
la sesión entera, y el TTS es el 86% del costo variable.

## Cuándo hay que correr esto

Cuando se agrega una voz a `VOCES_GEMINI` o `VOCES_OPENAI` en
[`motores.py`](../../src/motor_voz/voice/motores.py), o cuando se cambia el
texto del saludo.

No hace falta acordarse: `tests/test_muestras.py` cruza el catálogo contra los
archivos y **rompe** si falta alguna.

## El comando

```bash
uv run python scripts/generar_muestras.py
```

Saltea lo que ya existe, así que correrlo de nuevo solo graba lo que falta.
Con `--forzar` regenera todo, y eso **cuesta plata de verdad**: las 10 de
OpenAI son 10 sesiones Realtime contra una suscripción con tope.

Otras formas: `--motor gemini` o `--motor openai` para uno solo, `--solo Puck`
para una voz puntual.

## Lo que ya nos rompió

**El TTS de Gemini no vive donde el modelo Live.** `GCP_LOCATION` apunta a
`us-east4`, que es donde está `gemini-live-2.5-flash-native-audio`. El TTS ahí
no existe: da un 404 diciendo que el modelo no se encontró, que se lee como
nombre mal escrito y en realidad es la región. La única que responde es
`us-central1`, con `gemini-2.5-flash-preview-tts`. El default del plugin
(`gemini-3.1-flash-tts-preview`) tampoco está habilitado en el proyecto.

**Pedir las 8 de Gemini de corrido agota la cuota en la séptima.** El modelo
preview tiene cuota corta. El script espera dos segundos entre voces; no lo
saques.

**Azure tiene dos claves y una puede estar muerta.** La `key1` daba 401 en
todas las superficies y la `key2` conectaba. El portal las muestra iguales.
Ver [credenciales-y-401.md](credenciales-y-401.md).

**Sin normalizar, las voces salen con hasta 15 dB de diferencia.** Medido:
`alloy` a −18,6 dB contra `sage` a −33,5 dB. En un selector que existe para
comparar voces, la que suena más bajo se juzga peor voz aunque no lo sea. El
script normaliza a −16 LUFS (`loudnorm=I=-16`) y quedan todas parejas.

## Dónde caen los archivos

`frontend/widget/public/assets/muestras/{motor}-{clave}.mp3`

Vite copia `public/` tal cual, sin hashear el nombre, así que terminan en
`dist/assets/muestras/` y el `handle` de assets del Caddyfile ya los sirve.
**No hay que tocar la VM.**

MP3 mono a 48 kbps, ~25 KB cada una. MP3 y no Opus porque es lo único que
reproduce todo iPhone, y el widget se usa sobre todo desde el celular.

## Por qué van al repo si es público

Son voces stock de Google y OpenAI diciendo un saludo de marketing, y ya
suenan públicamente en el widget: el repo no expone nada que no esté al aire.
Versionarlas hace que desplegar no dependa de tener las claves de Vertex y de
Azure. Hay una excepción explícita en `.gitignore`.

**La voz clonada del fundador (VOZ-003) y cualquier grabación de una persona
real siguen afuera, sin excepción.**
