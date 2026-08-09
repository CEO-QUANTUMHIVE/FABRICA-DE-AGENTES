# Guía para escribir la personalidad de un agente

Para quien tenga que armar el prompt de un agente nuevo — sea una persona o
un agente de IA. Todo lo que está acá se aprendió rompiéndolo en producción.

---

## 1. El prompt son tres capas que se componen

```
IDENTIDAD   quién es, qué sabe, qué puede, qué no inventa
   +
ENTREGA     cómo pronuncia        → depende del MOTOR
   +
CANAL       cómo se formatea      → depende de DÓNDE habla
```

**Nunca copies un prompt para adaptarlo.** Dos prompts duplicados derivan:
tocás uno, te olvidás del otro, y a los tres meses el agente de WhatsApp
dice cosas distintas que el de la web. Se componen, no se clonan.

El código está en `src/motor_voz/brain/prompt.py`.

---

## 2. La regla que más importa: activo, no reactivo

El error más caro que cometimos fue pedirle **brevedad** sin pedirle
**iniciativa**. Salió un agente que contestaba una frase y se callaba, y el
visitante tenía que sacarle la información a la fuerza.

Un agente pasivo suena así:

```
— Hola
— Hola. Bienvenido a QuantumHive. Podemos ayudarlo con su negocio.
— tengo una barbería
— Sí, ofrecemos ese servicio.
```

Nadie compra ahí. Las tres reglas que lo arreglan:

**1. Nunca terminar sin una pregunta o una propuesta.**
Dejar al visitante en silencio esperando es el peor error posible en voz.

**2. Reaccionar antes de informar.**
Si te cuenta que tiene una barbería, primero reaccionás a eso y después
informás. `¡Ah, una barbería!` antes que `nuestro servicio incluye…`.

**3. Ofrecer información que no pidieron.**
Si menciona que atiende por WhatsApp, contale que el agente puede hacerlo
solo, aunque no haya preguntado.

Y una cuarta que ayuda: **darle opiniones**. Un vendedor que dice que sí a
todo aburre. Si algo no le sirve al cliente, que lo diga.

---

## 3. La personalidad se define por conductas, no por adjetivos

Decirle *"sé amigable"* no le dice nada al modelo. Decirle *"arrancá frases
con Y, Pero, Así que"* sí.

| No sirve | Sirve |
|---|---|
| Sé cálido | Usá muletillas: Dale, Mirá, Che, Buenísimo |
| Sé natural | Rompé la gramática formal. Empezá con Y, Pero, Así que |
| Sé dinámico | Alterná una frase corta con una más larga |
| Sé profesional | Nunca inventes precios. Si no lo sabés, decilo y ofrecé un humano |

Y siempre, siempre, **poné ejemplos al final** — de cómo habla **y de cómo
no habla**. El modelo copia mejor de un ejemplo concreto que de una
descripción, y lo último que lee es lo que más le pesa.

---

## 4. Capa ENTREGA — cambia según el motor

Esta es la parte que más se equivoca quien no conoce la diferencia.

### Si el motor es `pipeline` (TTS)

El LLM escribe texto y **el TTS lo lee literal**. La puntuación es la
partitura: es lo único que le dice a la voz cuándo subir y cuándo bajar.

Lo que hay que pedirle:

- **Usar `¡!` y `¿?`.** Sin ellos la voz sale plana y muerta. Y ojo: si le
  decís "no uses símbolos", el modelo aplica esa regla también a los signos
  de entonación y te deja la voz apagada. Aclarale que esos SÍ van.
- **Alternar frases cortas y largas.** Todas iguales suenan a máquina.
- **Dos o tres oraciones por turno:** una reacción, un dato, una pregunta.
- **Escribir todo como se pronuncia.** El TTS lee lo que ve.

> **Caso real:** el agente decía *"veinticuatro séptimo"* porque el LLM
> escribió `24/7`. Nombrale los casos concretos —`24/7`, `%`, `$`, `hs`,
> `aprox`— con su forma hablada al lado. Una regla vaga como "escribí los
> números como se pronuncian" no alcanza.

**Igual no confíes solo en el prompt para esto.** La normalización de texto
está resuelta en código, en `brain/normalizar.py`. El prompt es la segunda
línea de defensa, no la única.

### Si el motor es `gemini` u `openai` (voz a voz)

El modelo **genera el habla directamente**. No hay texto en el medio, así
que la puntuación no le dice nada. Pedirle que use signos de exclamación es
inútil y le gasta atención al pedo.

Lo que hay que pedirle es **actitud**:

- Cómo suena: con ganas, como alguien al que le gusta lo que hace.
- Que pueda dudar, arrancar de nuevo, pensar en voz alta. Suena humano.
- Que suba la energía cuando algo lo entusiasma y la baje cuando escucha.
- Que si lo interrumpen, pare y escuche.

### La tabla corta

| | pipeline | voz a voz |
|---|---|---|
| Puntuación | **crítica** | irrelevante |
| Normalizar números | **sí** | no hace falta |
| Describir la actitud | poco útil | **crítico** |
| Voz clonada | **sí** | no, voces del proveedor |
| Sirve en WhatsApp | **sí** | no |

---

## 5. Capa CANAL — cambia según dónde habla

**Web en vivo:** lo pueden interrumpir en cualquier momento. Es la primera
vez que lo escuchan: en el primer turno se presenta y pregunta.

**WhatsApp y Telegram:** no hay interrupción, el mensaje se escucha entero.
Puede extenderse un poco más. Y algo que se olvida siempre: **puede pasar
tiempo entre mensajes**, así que no puede dar por sentado que el otro se
acuerda de lo último que dijo.

---

## 6. El mismo prompt no da la misma personalidad en los tres motores

Esto hay que presupuestarlo como trabajo real.

El prompt de hoy está calibrado para `gpt-oss-20b` de Groq. Gemini y GPT
interpretan las mismas instrucciones distinto: uno se pasa de entusiasta,
otro ignora las muletillas, otro se vuelve verborrágico.

**Validá motor por motor.** No asumas que porque anda en uno anda en los
tres. Y si hace falta, escribí variantes de la capa ENTREGA por motor — la
IDENTIDAD no se toca.

---

## 7. Cómo probar un prompt sin levantar nada

Tres turnos encadenados contra el LLM real alcanzan para saber si el agente
está vivo o muerto:

```bash
uv run python -c "
import asyncio
from livekit.agents.llm import ChatContext
from motor_voz.config import cargar
from motor_voz.brain.prompt import construir
from motor_voz.brain.normalizar import normalizar
from motor_voz.voice.providers import llm

async def main():
    m = llm.crear(cargar())
    ctx = ChatContext()
    ctx.add_message(role='system', content=construir(motor='pipeline', canal='web'))
    for msg in ['Hola', 'una barberia', 'se me pasan mensajes']:
        ctx.add_message(role='user', content=msg)
        p=[]
        async with m.chat(chat_ctx=ctx) as s:
            async for f in s:
                if f.delta and f.delta.content: p.append(f.delta.content)
        r=''.join(p).strip(); ctx.add_message(role='assistant', content=r)
        print(f'VOS: {msg}'); print(f'AGENTE: {normalizar(r)}\n')

asyncio.run(main())
"
```

**Qué mirar:**

1. ¿Cada turno termina en pregunta o propuesta?
2. ¿Reacciona antes de informar?
3. ¿Ofrece algo que no le pidieron?
4. ¿Las frases son de largo variado?
5. Si es pipeline: ¿hay `¡!` y `¿?`? ¿quedó algún número sin normalizar?

Si falla el punto 1, el agente va a sonar muerto por más que la voz sea
espectacular. **La voz no salva a un prompt pasivo.**

---

## 8. Errores que ya cometimos, para no repetirlos

| Error | Consecuencia | Arreglo |
|---|---|---|
| "No uses símbolos" | El modelo dejó de usar `¡!` y la voz salió plana | Aclarar que los signos de entonación SÍ van |
| "Respondé breve" sin pedir iniciativa | Contestaba una frase y dejaba colgado al visitante | Nunca terminar sin pregunta |
| "Escribí los números como se pronuncian" | Escribió `24/7` igual, y sonó "veinticuatro séptimo" | Nombrar los casos concretos + normalizar en código |
| Reglas de puntuación en un motor de voz a voz | Atención gastada en algo que ese modelo ignora | Capa ENTREGA separada por motor |
| Duplicar el prompt por canal | Derivan y terminan diciendo cosas distintas | Componer las tres capas |
