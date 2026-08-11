# Diagnosticar un 401

Escrito el 2026-08-10, después de perder media tarde en un 401 de Azure que
no era lo que parecía. **El orden importa: cada paso descarta una causa
entera, y el más común es el primero.**

## 1. ¿La app está leyendo el `.env`, o algo se lo tapa?

**Esta fue la causa real, y es la que nadie mira.**

`python-dotenv` **no pisa variables que ya existen en el entorno**. Si hay una
variable de entorno de usuario de Windows con el mismo nombre, el `.env` no se
lee nunca para esa clave — podés editarlo mil veces y no cambia nada.

```powershell
foreach($a in 'Process','User','Machine'){
  $v = [Environment]::GetEnvironmentVariable('NOMBRE_DE_LA_CLAVE', $a)
  "{0,-8} {1}" -f $a, $(if($v){"DEFINIDA ($($v.Length) chars)"}else{"no definida"})
}
```

Comparalo con lo que la app carga de verdad. Nunca imprimas la clave: compará
largos y hashes.

```powershell
# hash corto para comparar sin exponer el valor
$h = { param($s) (Get-FileHash -InputStream ([IO.MemoryStream]::new(
      [Text.Encoding]::UTF8.GetBytes($s))) -Algorithm SHA256).Hash.Substring(0,12) }
```

Si borrás la variable de usuario, **la copia heredada sigue viva en los
procesos ya abiertos**. Hay que reiniciar la terminal.

## 2. ¿Es la clave que creés, o la otra?

Azure emite **dos claves por recurso** y las dos parecen válidas en el portal.
Una puede estar muerta.

```bash
az cognitiveservices account keys list --name RECURSO --resource-group GRUPO --query key1 -o tsv
```

Probá las dos antes de dar la credencial por mala. En nuestro caso `key1`
daba 401 en la API de administración, en la de datos y en el WebSocket, y
`key2` conectaba a la primera.

## 3. ¿El recurso está sano?

```bash
az account show --query "{estado:state, nombre:name}" -o json
az cognitiveservices account show --name RECURSO --resource-group GRUPO --query "{authLocalDeshabilitada:properties.disableLocalAuth, red:properties.publicNetworkAccess}" -o json
az cognitiveservices account deployment list --name RECURSO --resource-group GRUPO -o table
```

`disableLocalAuth` en `true` significa que **las claves no sirven** y solo
entra Entra ID. Un deployment que no esté en `Succeeded` o con capacidad 0
también da errores que parecen de auth.

## 4. ¿Estás llamando a la URL correcta?

Un 401 y un 404 dicen cosas distintas: **404 significa que la autenticación
pasó** y lo que no se encontró fue la ruta. Si probás varias versiones de API
y una da 404 mientras las otras dan 401, la que da 404 es la que autentica
bien.

Azure OpenAI Realtime tiene dos superficies:

```
legacy : wss://HOST/openai/realtime?api-version=VERSION&deployment=DEPLOYMENT
nueva  : wss://HOST/openai/v1/realtime?model=DEPLOYMENT
```

Las dos con header `api-key`. Sin `api_version` se usa la nueva. Si hay una
implementación que ya funciona en producción, **leé cómo arma ella la URL**
en vez de adivinar: la del plugin de livekit está en
`livekit/plugins/openai/realtime/realtime_model.py`, función `process_base_url`.

## 5. Recién ahí, sospechá del código

Si la URL, los headers y el cliente HTTP son los mismos que usa algo que
funciona, y sigue dando 401, el problema es la credencial. Volvé al paso 1.

## Regla general

Un 401 que aparece en **todas** las superficies de una API a la vez casi nunca
es un problema de código. Es la credencial, o es qué credencial se está
leyendo realmente.
