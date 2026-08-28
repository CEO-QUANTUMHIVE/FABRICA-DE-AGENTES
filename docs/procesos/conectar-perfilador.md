# Conectar el Perfilador de Clientes

El Perfilador vive en `CEO-QUANTUMHIVE/INTELIGENCIA-COMERCIAL-SCRAP` y la
Fábrica lo consume como un servicio separado. No se copia código entre repos:
cada uno conserva su despliegue, su base y sus credenciales.

## Circuito

1. El cliente escribe el nombre, la web y las redes en la Fábrica.
2. El navegador llama `POST /api/fabrica/investigar`, sin token interno.
3. El backend agrega `Authorization: Bearer <TOKEN_INTERNO>` y llama al
   Perfilador en `POST /clientes/investigar`.
4. La Fábrica limita y normaliza la respuesta antes de devolverla al panel.
5. El panel completa la ficha, transforma logo y colores en el orbe y deja los
   datos listos para publicarlos como conocimiento del tenant.

Si el Perfilador no está configurado o se cae, esta función devuelve un error
claro, pero el brain, la voz, el entrenamiento manual y los canales siguen
funcionando.

## Configuración del backend de la Fábrica

```dotenv
CENTRO_INTELIGENCIA_URL=https://perfilador.ejemplo.com
CENTRO_INTELIGENCIA_TOKEN=un-token-largo-y-aleatorio
```

El mismo valor del token debe estar configurado como `TOKEN_INTERNO` en el
servicio Perfilador. Estas variables son exclusivas del backend: nunca usar
prefijo `VITE_`, nunca ponerlas en el frontend y nunca pegarlas en el chat.

## Comprobación

`GET /api/fabrica/perfilador` debe responder:

```json
{"disponible": true}
```

Después, desde la Fábrica, se pulsa **Investigar mi negocio**. El resultado
correcto completa al menos los datos encontrados, sin inventar los campos que
requieren decisión del dueño, como promesa, objetivo y límites.

Antes del despliegue final deben pasar:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend\fabrica
npm.cmd test
npm.cmd run build
```

## Regla de datos

Los competidores quedan disponibles para análisis interno, pero no se publican
en el conocimiento conversacional del agente. Así se evita que el bot revele
inteligencia comercial a un cliente durante una conversación.
