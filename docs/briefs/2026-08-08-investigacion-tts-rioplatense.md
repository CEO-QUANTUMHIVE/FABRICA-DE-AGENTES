# BRIEF DE INVESTIGACIÓN — TTS self-hosteable, comercial, con acento rioplatense

**Para:** agente de investigación
**De:** QuantumHive
**Fecha:** 2026-08-08
**Tipo:** investigación exhaustiva con verificación de licencias

---

## 0. Qué se espera de vos

Una investigación **exhaustiva y verificada**, no una lista de nombres populares. Cada afirmación tiene que estar respaldada por una URL que hayas abierto. Si no verificaste algo, decilo explícitamente en vez de rellenar.

No hace falta que seas breve. Hace falta que seas exacto.

---

## 1. Contexto

QuantumHive construye un motor de voz multi-tenant que va a atender, desde una sola infraestructura:

- el sitio propio de la empresa;
- demos comerciales por rubro (barbería, inmobiliaria, yoga, gastronomía, ventas);
- agentes de clientes que pagan por el servicio;
- canales de mensajería (WhatsApp, Telegram);
- una aplicación descargable de escritorio para Windows.

El público es **argentino**. Los usuarios finales son clientes de pymes argentinas hablando con el agente de un negocio argentino.

Hoy el TTS es **Fish Audio vía API paga**, y tiene un límite de **5 solicitudes concurrentes** hasta acumular $100 de consumo. Ese techo no sirve para un motor central que alimenta todos los canales a la vez.

Se evaluó self-hostear el modelo abierto de Fish (`fishaudio/fish-speech`) y **quedó descartado por licencia**: la Fish Audio Research License prohíbe expresamente el uso comercial sin un acuerdo escrito aparte, e incluye en la prohibición el uso vía servicio hosteado o API y cualquier producto por el que se cobre.

Por eso necesitamos una alternativa que podamos hostear nosotros y usar comercialmente sin pedir permiso.

---

## 2. Objetivo

Encontrar y comparar **motores de TTS que podamos desplegar en nuestra propia infraestructura y usar comercialmente**, capaces de producir voz en **español rioplatense argentino**, **expresiva y natural**.

Calidad exigida: que suene a una persona argentina hablando.

**Se rechaza de plano** cualquier motor que suene robótico, monótono, con prosodia plana, con cortes artificiales entre frases, o con acento español peninsular o mexicano neutro aplicado a texto argentino. No importa cuán popular sea el proyecto ni cuántas estrellas tenga: si no suena bien en rioplatense, no sirve.

---

## 3. La clave que te va a ahorrar tiempo

**Casi ningún TTS del mundo trae una voz argentina de fábrica.** Buscar "TTS con voz argentina" te va a dar casi nada y vas a perder horas.

El camino real es otro: **un TTS multilingüe de alta calidad con clonación de voz zero-shot**, al que se le pasa una muestra de audio de una persona argentina y reproduce ese acento y esa prosodia.

Entonces la pregunta correcta no es "¿tiene voz argentina?" sino:

> ¿Qué tan bien clona el acento y la expresividad de una muestra rioplatense de referencia?

Priorizá los motores con **clonación zero-shot** (una muestra corta, sin reentrenar). En segundo lugar, los que permiten fine-tuning con un dataset propio. Igual reportá si encontrás algún modelo con voces `es-AR` nativas: sería un hallazgo valioso.

---

## 4. Requisitos duros

Un candidato que falle **cualquiera** de estos queda descartado. Decilo explícitamente cuando pase.

1. **Licencia que permita uso comercial**, incluyendo ofrecerlo como servicio hosteado a terceros que pagan, sin acuerdo comercial adicional.
2. **Self-hosteable**: los pesos del modelo se pueden descargar y correr en infraestructura propia.
3. **Español soportado** con calidad real, no como idioma marginal.
4. **Clonación de voz** zero-shot o fine-tuning viable, para lograr acento rioplatense.
5. **Calidad expresiva**, con entonación y ritmo naturales.
6. **Mantenido**: commits en los últimos 6 meses e issues con respuesta.

## 5. Requisitos deseables

Ordenados por importancia:

1. **Streaming con baja latencia** (< 300 ms al primer byte de audio). Lo necesitamos para conversación en tiempo real con interrupción.
2. **Alta concurrencia por GPU**: cuántos streams simultáneos aguanta una GPU concreta.
3. **Que corra en CPU** con calidad aceptable, aunque sea para el modo asíncrono no conversacional.
4. Control de emoción, énfasis, velocidad o estilo.
5. Servidor de inferencia listo para producción, o integración con vLLM / Triton / TorchServe.
6. **Plugin o compatibilidad con LiveKit Agents** (framework `livekit/agents`), o al menos API tipo OpenAI que permita adaptarlo fácil.
7. Comunidad activa con gente que lo haya puesto en producción de verdad.

---

## 6. LA TRAMPA DE LAS LICENCIAS — leé esto dos veces

**Este es el punto donde más agentes fallan. No confíes en:**

- el badge de licencia de GitHub;
- el campo "license" de la API de GitHub;
- lo que diga el README;
- que alguien en un blog o en Reddit diga "es open source";
- que aparezca en una lista de "mejores TTS open source".

**Abrí y leé el archivo `LICENSE` o `LICENSE.md` completo, en el repositorio, y citá el texto exacto.**

### Caso real que motivó esta advertencia

`fishaudio/fish-speech` figura como "SOTA Open Source TTS", tiene 32.000 estrellas, y GitHub le muestra licencia "Other". El texto real dice:

> "Any use of the Fish Audio Materials or Derivative Works for a Commercial Purpose requires a separate written license agreement from Fish Audio. No commercial rights are granted under this Agreement."

Y define "Commercial Purpose" incluyendo *crear o distribuir tu producto o servicio, incluso vía servicio hosteado o API*, y *cualquier uso relacionado con un producto por el que cobrás*. Es decir: inservible para nosotros, pese a aparecer en todas las listas de "TTS open source".

### La segunda trampa: código y pesos tienen licencias distintas

Es habitual que el **código** sea MIT o Apache-2.0 y los **pesos del modelo** tengan una licencia restrictiva aparte (CC-BY-NC, research-only, licencia propietaria, o una cláusula de uso aceptable).

**Verificá las dos por separado** y reportalas por separado. Mirá también:

- la model card en Hugging Face (suele tener la licencia real de los pesos);
- archivos como `WEIGHTS_LICENSE`, `MODEL_LICENSE`, `NOTICE`, `ACCEPTABLE_USE`;
- si el modelo se entrenó sobre otro modelo con licencia heredada (la restricción se propaga);
- cláusulas de límite de usuarios, de facturación anual, o de atribución obligatoria.

### Clasificación exigida

Clasificá cada candidato en:

- **APTO** — uso comercial y hosteo para terceros permitido sin acuerdo adicional. Citá la cláusula.
- **APTO CON CONDICIONES** — permitido pero con requisitos (atribución, tope de facturación, share-alike). Citá la condición exacta.
- **NO APTO** — requiere licencia comercial o prohíbe el uso. Citá la cláusula que lo prohíbe.
- **AMBIGUO** — el texto no es claro. Explicá por qué y qué habría que preguntarle al autor.

**Ante la duda, es NO APTO.** Preferimos descartar un candidato bueno antes que meternos en un problema legal.

---

## 7. Dónde buscar

Buscá en todos lados, no solo en los dos o tres lugares obvios.

**Repositorios**
GitHub y GitLab: buscá por `text-to-speech`, `TTS`, `voice cloning`, `speech synthesis`, `zero-shot TTS`, `streaming TTS`. Ordená por estrellas y también por actividad reciente. Revisá los "awesome-tts" y listas curadas, pero **verificá cada entrada** en vez de copiarla.

**Hugging Face**
Explorá los modelos de `text-to-speech`. Filtrá por español. Leé las model cards y las licencias. Mirá los Spaces con demos para escuchar antes de recomendar.

**Foros y comunidades**
Reddit: `r/LocalLLaMA`, `r/MachineLearning`, `r/speechtech`, `r/artificial`, y subreddits en español. Buscá comparativas y quejas reales de gente que los usó, no anuncios. Hacker News. Discord y foros de los proyectos. Stack Overflow para problemas de producción.

**Benchmarks y arenas**
Arenas de comparación de TTS con votación ciega, papers recientes con MOS, y cualquier evaluación independiente. Ojo: los benchmarks suelen medir inglés. **Buscá específicamente evaluaciones en español.**

**Comunidad hispanohablante y argentina**
Es donde más probablemente encuentres a alguien que ya peleó el acento rioplatense: foros argentinos de desarrollo, grupos de IA en español, blogs técnicos en español, YouTube en español con demos audibles. Buscá términos como "TTS español argentino", "voz rioplatense", "clonar voz argentina", "síntesis de voz español latino".

---

## 8. Qué probar antes de recomendar

Si podés ejecutar o escuchar demos, hacelo. Una recomendación sin haber escuchado el modelo vale poco.

Frase de prueba sugerida, porque concentra los rasgos rioplatenses:

> "Che, ¿cómo andás? Mirá, para el sábado tenemos lugar a las cuatro y media, ¿te sirve? Si querés te lo reservo ahora y listo."

Escuchá específicamente:

- el **voseo** (*andás*, *querés*, *mirá*) — que no lo lea como tuteo;
- la **"ll" y la "y"** — el rioplatense las hace /ʃ/ (*shuvia*, no *lluvia* a la española);
- la **entonación ascendente** típica de la pregunta argentina;
- que **no aspire ni cecee** como el español peninsular;
- que **no suene a español neutro de doblaje**;
- ritmo natural, sin pausas mecánicas entre frases.

---

## 9. Formato de entrega

### Parte 1 — Tabla comparativa

Una fila por candidato, con: nombre, repo, licencia del código, licencia de los pesos, veredicto de licencia (APTO / APTO CON CONDICIONES / NO APTO / AMBIGUO), calidad en español, clonación de voz, streaming, latencia, requisito de hardware, actividad del proyecto.

### Parte 2 — Ficha detallada de los 5 mejores

Para cada uno:

- qué es y quién lo mantiene;
- **la cláusula de licencia citada textualmente**, con la URL exacta del archivo;
- calidad en español rioplatense, con evidencia de lo que escuchaste o de evaluaciones que encontraste;
- cómo se hace la clonación de voz y qué necesita de muestra;
- requisitos de hardware y concurrencia estimada por GPU;
- latencia y si soporta streaming;
- cómo se despliega en producción;
- integración con LiveKit Agents, si existe;
- problemas conocidos, reportados por usuarios reales;
- costo estimado de hostearlo.

### Parte 3 — Recomendación

- El mejor candidato y por qué.
- Un segundo como respaldo, preferentemente con perfil distinto (por ejemplo uno que corra en CPU).
- Qué candidatos populares descartaste **y con qué cláusula exacta**.
- Qué quedó sin verificar y qué haría falta para cerrarlo.

### Parte 4 — Riesgos

Licencias ambiguas, proyectos con riesgo de abandono, dependencias problemáticas, y cualquier cosa que pueda convertirse en un problema legal o técnico más adelante.

---

## 10. Reglas de honestidad

- Si no escuchaste el modelo, decí "no lo escuché".
- Si la licencia no la leíste completa, decí "no la leí completa".
- Si un dato viene de un blog y no de la fuente primaria, marcalo.
- No inventes números de latencia ni de concurrencia. Si no hay dato publicado, decilo.
- No recomiendes por popularidad. Fish tiene 32.000 estrellas y no nos sirve.

**Un "no encontré nada que cumpla todo" bien fundamentado vale más que una recomendación floja.**
