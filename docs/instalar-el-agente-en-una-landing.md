# Instalar el agente de voz en una landing

El procedimiento repetible para poner el agente en la web de un cliente.

**Lo primero que hay que entender:** cada cliente **no** lleva su propio
servidor. Hay **una sola infraestructura** que atiende a todos, y a cada
cliente se le da un identificador y un fragmento de código para pegar.

```
UNA infraestructura (parte A, una sola vez)
        |
        +-- cliente 1  ->  tenant + snippet
        +-- cliente 2  ->  tenant + snippet
        +-- cliente N  ->  tenant + snippet
```

Instalar un servidor por cliente sería insostenible: N servidores que
mantener, actualizar y pagar. Con esta arquitectura, sumar un cliente es
una fila en la base y un `<script>` en su página.

---

# PARTE A — La infraestructura (una sola vez)

Ya está hecha para QuantumHive. Esto queda documentado para poder
reconstruirla, moverla de proveedor o levantar un segundo entorno.

## A.1 — El servidor de medios (LiveKit)

Es lo único que **no** puede ir en Cloud Run ni en un servicio serverless:
necesita **UDP**, y esos entornos solo hablan HTTP.

```bash
gcloud compute instances create livekit-quantumhive \
  --zone=us-east1-b --machine-type=e2-micro \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-standard \
  --tags=livekit
```

**Por qué así:**

- `e2-micro` en `us-east1`, `us-west1` o `us-central1` entra en el nivel
  gratuito de Google. De las tres, `us-east1` es la más cerca de Argentina
  y en voz la latencia se escucha.
- El nivel gratuito da **1 GB de salida de datos por mes**, que son unas 50
  a 100 horas de conversación. El excedente sale ~USD 0,12 el GB.
- Si la organización tiene la política `compute.vmExternalIpAccess` en DENY,
  hay que habilitarla **solo para esa instancia**, nunca para todas.

### Puertos

```bash
gcloud compute firewall-rules create livekit-tcp \
  --allow=tcp:80,tcp:443,tcp:7880,tcp:7881 --target-tags=livekit
gcloud compute firewall-rules create livekit-udp \
  --allow=udp:3478,udp:50000-60000 --target-tags=livekit
```

| Puerto | Para qué |
|---|---|
| UDP 50000-60000 | El audio. Sin esto no se escucha nada |
| UDP 3478 | TURN, para visitantes detrás de firewalls corporativos |
| TCP 7881 | WebRTC por TCP, cuando UDP está bloqueado |
| TCP 7880 | Señalización |
| TCP 80 / 443 | Certificado y WebSocket seguro |

### Instalación y servicio

```bash
curl -sSL https://get.livekit.io | sudo bash
```

Config en `/etc/livekit/livekit.yaml`, con claves generadas —
`openssl rand -hex 12` y `openssl rand -hex 32`— y `use_external_ip: true`.

Servicio systemd con `Restart=always` y `WantedBy=multi-user.target`, para
que sobreviva a un reinicio de la VM. Verificar con:

```bash
systemctl is-enabled livekit && systemctl is-active livekit
curl -s -o /dev/null -w "%{http_code}\n" http://IP:7880/
```

## A.2 — El dominio y el certificado

El navegador exige HTTPS para usar el micrófono, y una página `https://` no
puede conectarse a un `ws://`: lo bloquea por mezcla de contenido. Hace
falta `wss://`, o sea dominio con certificado.

**Registro DNS** (en el proveedor donde esté el dominio):

```
Tipo A    voz.<dominio>    ->    <IP de la VM>
```

> **Si el DNS está en Cloudflare, el registro va en "DNS only" — nube gris,
> no naranja.** El proxy de Cloudflare no pasa UDP, y WebRTC va por UDP.
> Proxeado, el sitio carga, el agente conecta, y no se escucha nada. Es de
> los errores más difíciles de diagnosticar porque todo *parece* andar.

**Certificado:** Caddy lo saca solo de Let's Encrypt y renueva sin
intervención. El `Caddyfile` entero son tres líneas:

```
voz.<dominio> {
	reverse_proxy localhost:7880
}
```

Caddy termina TLS y pasa **solo la señalización** a LiveKit. El audio no
pasa por ahí: va directo por UDP a la VM. Por eso el registro DNS no puede
estar proxeado.

**Si el DNS está en Cloudflare, esto se automatiza por API** y no hace falta
entrar al panel:

```bash
curl -X POST -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json"   "https://api.cloudflare.com/client/v4/zones/$ZONA/dns_records"   --data '{"type":"A","name":"voz","content":"<IP>","ttl":120,"proxied":false}'
```

El token tiene que ser de tipo **Editar zona DNS**, con alcance a esa zona
únicamente. Ojo: un token de R2 sirve para leer zonas pero **no** para
escribir registros, y el error que devuelve —"Authentication error"— no lo
aclara.

### Verificación

```bash
curl -s -o /dev/null -w "%{http_code}
" https://voz.<dominio>/
echo | openssl s_client -connect voz.<dominio>:443 2>/dev/null | openssl x509 -noout -dates
```

Un `401` al pedir upgrade a WebSocket en `/rtc` **es la respuesta correcta**:
significa que LiveKit está recibiendo la conexión y pidiendo credenciales.
Un `502` sí sería un problema.

## A.3 — La API de tokens y el agente

Las dos son HTTP puro y **sí** pueden ir en Cloud Run con
`min-instances=1`, o en la misma VM si el volumen es bajo.

- **API de tokens** (`motor_voz.api.servidor`): emite tokens firmados,
  valida el tenant y aplica los límites de abuso.
- **Agente** (`motor_voz.voice.agente`): se conecta al servidor de medios y
  atiende las sesiones.

---

# PARTE B — Por cada cliente

Esto es lo que se repite. Cinco a diez minutos por cliente.

## B.1 — Crear el tenant

Una fila con: identificador, nombre del negocio, perfil de rubro, plan
—que define el motor—, voz, y los datos del negocio que el agente va a usar.

Hasta la Fase 5 es configuración; después, una fila en Supabase.

## B.2 — Elegir el plan

| Plan | Motor | Voz | Canales |
|---|---|---|---|
| **Básico** | pipeline | **clonada o propia del cliente** | web, WhatsApp, Telegram |
| **Medio** | Gemini Live | voces de Google | solo web en vivo |
| **Premium** | OpenAI Realtime | voces de OpenAI | solo web en vivo |

**No es una escalera de calidad, son tres propuestas distintas.** El básico
es el único que puede hablar con **la voz del cliente** y el único que
funciona en WhatsApp. Una barbería que quiere que el agente hable con la voz
del dueño va a preferir el básico aunque el premium sea más expresivo.

Si el cliente quiere su voz clonada, ver
`docs/voces/registro-de-consentimiento.md`: **sin consentimiento registrado
no se clona.**

## B.3 — Escribir la personalidad

La guía completa está en `docs/guia-de-prompts.md`. Lo que hay que sacarle
al cliente:

- Qué vende y a quién
- Qué le preguntan siempre
- Qué **no** debe decir el agente (precios, plazos, promesas)
- Cuándo derivar a un humano
- Tono: ¿vendedor y arriba, o tranquilo y profesional?

**Ojo con esto:** el prompt calibrado para un motor no se comporta igual en
otro. Si el cliente cambia de plan, hay que revalidar la personalidad.

## B.4 — El fragmento para su página

El cliente pega esto antes de cerrar el `</body>`:

```html
<script
  src="https://voz.quantumhive.com.ar/widget.js"
  data-tenant="barberia-style"
  defer></script>
```

Un solo `<script>` con su identificador. **No hay que tocar su servidor, ni
su hosting, ni su CMS.** Funciona igual en WordPress, en Wix o en una página
hecha a mano.

## B.5 — Verificar antes de entregar

Sin excepción, con el cliente presente:

1. El widget aparece en su página, en desktop **y en celular**
2. Pide permiso de micrófono y conecta
3. El agente saluda solo, sin que le hablen primero
4. Entiende lo que se le dice en español
5. **Se lo puede interrumpir y frena** ← el que separa una conversación de
   un contestador
6. Responde con los datos **de ese** negocio, no de otro
7. La sesión se corta sola al llegar al tope

## B.6 — Aislamiento: la regla que no se rompe

**Un cliente nunca puede ver los datos de otro.** El agente de la Barbería
Style no puede nombrar un servicio de Beauty Hair ni acceder a sus clientes,
aunque se lo pidan de frente.

Hay un test automático que lo verifica y **bloquea el merge** si falla. No
se entrega un cliente nuevo sin que ese test pase.

---

# Costos por cliente

| Concepto | Costo |
|---|---|
| Servidor de medios | **compartido**, no escala por cliente |
| API y agente | **compartidos** |
| Conversación de 4 min, plan básico | ~USD 0,05 |
| Conversación de 4 min, plan medio | ~USD 0,05 |
| Conversación de 4 min, plan premium | ~USD 0,06 (mini) |

Un cliente concurrido —cien conversaciones por día— cuesta del orden de
**USD 30 a 60 por mes** en consumo, y baja bastante con los tramos
cacheados. Cualquier abono mensual razonable lo cubre con margen.

Los planes medio y premium pueden facturarse contra **créditos** en vez de
tarjeta: Gemini por Vertex AI consume créditos de Google Cloud, y OpenAI por
Azure OpenAI consume créditos de Azure.

---

# Qué puede salir mal

| Síntoma | Causa casi segura |
|---|---|
| Conecta pero no se escucha nada | UDP bloqueado. Revisar firewall y **el proxy de Cloudflare en naranja** |
| El navegador no deja usar el micrófono | La página no está en HTTPS, o falta el `wss://` |
| El agente no entiende español | El STT quedó en el idioma por defecto, que es inglés |
| Pronuncia mal números o símbolos | Falta el normalizador de texto en el pipeline |
| Contesta una frase y se calla | El prompt pide brevedad sin pedir iniciativa |
| Habla plano y sin ánimo | Al LLM se le prohibieron los signos de entonación |
| Corta a mitad de conversación | Se alcanzó el tope de sesión, o el diario |
