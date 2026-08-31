# Desplegar el frontend de la Fábrica

**Cuándo:** cambió algo de `frontend/fabrica/` y hay que verlo en
`https://www.quantumhive.com.ar/fabrica/`.

Este documento existe porque el 2026-08-31 la Fábrica llevaba **tres días
commiteada y sin desplegar**, y el camino para desplegarla no estaba escrito en
ningún lado. Buscar cuál era la fuente correcta costó media sesión.

---

## Lo primero, porque es lo que rompe

`/fabrica/` **no se despliega sola**. Es una carpeta adentro de la landing, que
es un servicio de Cloud Run con su propio repositorio:

> **https://github.com/CEO-QUANTUMHIVE/pagina-web-landing-quantumhive**

Desplegar la Fábrica = desplegar **la landing entera**. Si la copia desde la que
desplegás está atrasada, te llevás puesto todo lo demás.

### 🔴 La carpeta de la bóveda de Obsidian NO es la landing

Hay una copia en `C:\Users\sergio\Desktop\boveda obsidian\landing` que **parece**
la landing y no lo es:

- Su único `git remote` apunta a un Space de **HuggingFace**
  (`quantumhive/la-escaloneta-3d`), no al repo de la landing.
- Está atrasada: el 2026-08-31 le faltaba el PR #5
  (`feature/boton-biblioteca-inteligente`) que sí estaba vivo.
- Su build de `fabrica/` era del **20-ago**, con el texto viejo del autoguiado.
- Vive adentro del repo de la bóveda, con ~1266 archivos de otros proyectos sin
  commitear.

**Desplegar desde ahí regresa la landing viva.** Es exactamente el accidente que
ya pasó una vez y borró una pestaña entera (ver la última sección de
[`desplegar.md`](desplegar.md)).

---

## El procedimiento

### 1. Clonar la fuente de verdad, siempre limpia

```bash
gh repo clone CEO-QUANTUMHIVE/pagina-web-landing-quantumhive landing -- --depth 1
```

Nunca reutilizar una copia vieja. Clonar cuesta segundos.

### 2. Verificar que el clon ES lo que está vivo

**Este paso no se saltea.** Es lo único que separa un deploy de un accidente.

En la consola del navegador, parado en `https://www.quantumhive.com.ar`:

```js
const h=async(r)=>{const b=await(await fetch(r,{cache:'no-store'})).arrayBuffer();
const d=await crypto.subtle.digest('SHA-256',b);
return [...new Uint8Array(d)].map(x=>x.toString(16).padStart(2,'0')).join('').slice(0,16);};
({'index.html':await h('/index.html'),'script.js':await h('/script.js'),'styles.css':await h('/styles.css')})
```

Y contra el clon:

```bash
for f in index.html script.js styles.css; do sha256sum "landing/$f" | cut -c1-16; done
```

**Los tres tienen que coincidir.** Si no coinciden, producción y el repo
divergieron: **parar y averiguar por qué** antes de desplegar nada.

> No compares tamaños entre el navegador y el disco: `fetch().text().length`
> cuenta caracteres y `wc -c` cuenta bytes. Con acentos nunca dan igual y vas a
> creer que hay diferencias que no existen. Comparar hashes del `arrayBuffer`.

### 3. Compilar la Fábrica

```bash
cd frontend/fabrica && npm.cmd test && npm.cmd run build
```

El build **exige** `VITE_API_URL` (HTTPS), `VITE_SUPABASE_URL` y
`VITE_SUPABASE_ANON_KEY`, que salen de `frontend/panel/`. Si faltan, falla con
el nombre de la que falta. Compila con `base: "/fabrica/"`, así que solo sirve
bajo esa ruta.

Las 18 muestras de voz entran solas: el `publicDir` apunta a
`../widget/public`, para no mantener una segunda copia.

### 4. Copiar el build al clon

Lo nuevo primero, lo viejo después — igual que con el widget. Los nombres
llevan hash y conviven sin pisarse; al revés hay un instante sin assets.

```bash
cp frontend/fabrica/dist/index.html landing/fabrica/index.html
cp frontend/fabrica/dist/assets/index-*.js frontend/fabrica/dist/assets/index-*.css landing/fabrica/assets/
cp -r frontend/fabrica/dist/assets/muestras/. landing/fabrica/assets/muestras/
cd landing/fabrica/assets && for f in *.js *.css; do
  [ -e "../../../frontend/fabrica/dist/assets/$f" ] || rm -f "$f"
done
```

Ese `for` importa: `fabrica/assets/` venía acumulando **tres builds viejos**
además del vivo. Sin la limpieza crecen para siempre.

### 5. Confirmar que el diff toca solo `fabrica/`

```bash
cd landing && git status --short
```

Si aparece cualquier cosa fuera de `fabrica/`, **algo salió mal**: no era el
build lo que cambiaste.

### 6. Rama, PR y deploy

No se toca `main` a mano:

```bash
git checkout -b fabrica/<lo-que-hiciste>
git add -A fabrica && git commit -m "..."
git push -u origin fabrica/<lo-que-hiciste>
```

El deploy a Cloud Run lo corre Sergio. **Nunca `gcloud run deploy --source .`
desde una carpeta que no verificaste con el paso 2.**

### 7. Verificar en vivo

```bash
curl -s https://www.quantumhive.com.ar/fabrica/ | grep -o 'assets/index-[A-Za-z0-9]*\.js'
```

Tiene que devolver el hash **nuevo**. Si devuelve el viejo, el deploy no entró
(o hay caché de CDN por delante).

---

## Qué se ve y qué no, según lo que esté desplegado

El frontend degrada solo, a propósito. Sirve para saber dónde estás parado:

| Situación | Qué ve el visitante |
|---|---|
| Frontend viejo | No existe el formulario de investigación |
| Frontend nuevo, API vieja | El formulario aparece y el botón queda **deshabilitado**: "El servidor todavía no publicó el módulo de investigación" |
| Frontend + API nuevos, sin Perfilador | Botón deshabilitado: "falta conectar la URL y el token en el servidor" |
| Todo desplegado | El botón anda y el visor muestra al investigador entrando a cada fuente |

O sea: **el frontend no se rompe si vas por partes.** Pero para que el módulo
funcione de verdad hacen falta los tres:

1. La API en la VM — ojo con la **regla dura 1** de [`desplegar.md`](desplegar.md):
   API y agente se reinician **juntos**, nunca uno solo.
2. Este frontend.
3. El Perfilador desplegado y sus dos variables:
   [`conectar-perfilador.md`](conectar-perfilador.md).
