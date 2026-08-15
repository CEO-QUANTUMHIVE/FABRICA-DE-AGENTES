# Panel de control de cada agente

**Objetivo:** que cada cliente administre y mejore su propio agente sin poder
ver ni modificar otro tenant.

## Principio

El panel no crea un segundo agente. Abre el mismo `brain/` en `modo=interno`,
con el tenant fijado por la sesión autenticada. Las conversaciones y mensajes
de todos los canales viven en las tablas multicanal y alimentan métricas, chat,
memoria y entrenamiento.

## Navegación

### 1. Métricas

- conversaciones y mensajes por día, canal y franja horaria;
- tiempo hasta primera respuesta;
- consultas resueltas, derivaciones a humano y conversaciones abandonadas;
- temas, servicios y preguntas más frecuentes;
- leads capturados y conversión cuando exista el evento comercial;
- consumo y costo por canal/modelo, con límites y kill-switch.

Las métricas salen de eventos reales. Nunca se presentan números simulados
como producción.

### 2. Memorias

- hechos recordados del negocio y de sus clientes;
- origen de cada memoria (conversación, carga manual o corrección);
- alcance, fecha, vigencia y última actualización;
- aprobar, archivar u olvidar;
- historial y restauración de versiones.

Una memoria sugerida por el modelo no entra al contexto permanente hasta
pasar las reglas de aprobación definidas para ese tipo de dato.

### 3. Chat con mi agente

- conversación privada en `modo=interno` con el mismo agente;
- consultar métricas, conversaciones y configuración mediante tools internas;
- probar cómo respondería antes de publicar entrenamiento;
- pedir explicaciones de qué fuente usó;
- derivar una conversación real a humano o devolverla a automático.

El modo interno solo se firma después de validar JWT + vínculo usuario/tenant.

### 4. Enseñar y probar al agente

El cliente no edita un prompt ni completa un formulario técnico. Conversa con
su propio agente como con una persona de su equipo:

- le marca palabras que no debe usar;
- corrige pronunciación, tono y expresiones;
- señala una respuesta que no le gustó;
- pide una forma preferida de explicar algo;
- entra en **Probar como cliente** y simula una conversación real;
- revisa la lista de cambios pendientes;
- usa **Probar cambios** y recién después **Aplicar cambios**.

Por debajo, esas indicaciones se convierten en piezas estructuradas y
versionadas:

- horarios y excepciones por fecha;
- precios y vigencia;
- servicios, disponibilidad y condiciones;
- políticas de reserva, seña, cancelación y devolución;
- preguntas frecuentes y respuestas aprobadas;
- tono, expresiones preferidas y expresiones prohibidas;
- correcciones sobre respuestas reales del agente.

Flujo de publicación:

```text
borrador -> vista previa -> pruebas -> publicar -> medir -> revertir si falla
```

Cada cambio guarda autor, fecha, valor anterior, valor nuevo y motivo. Los
cambios sensibles no se aplican silenciosamente a conversaciones activas.

### 5. Mi negocio

Planilla simple y editable para productos, servicios, precios y detalles. El
cliente ve filas, no JSON ni prompts. Guardar crea/publica versiones con
historial y posibilidad de restauración.

### 6. Conexiones

No es una lista fija. Es un catálogo buscable similar al selector de
conectores/MCP de los asistentes modernos:

- buscador por nombre, función o categoría;
- portada priorizada para pymes: Google Maps/reseñas, mensajería, planillas,
  ventas y cobros antes que los calendarios;
- filtros para Presencia online, Planillas, Pagos y cobros, Calendarios,
  Ventas, Mensajería, Productividad y CRM/datos;
- catálogo ampliable sin rediseñar el panel;
- conexiones activas separadas de las disponibles;
- MCP personalizado enviado a revisión;
- adaptación al sistema que el cliente ya utiliza.

Cada integración es un adaptador. El agente y su cerebro siguen siendo los
mismos; cambia la herramienta autorizada para consultar disponibilidad,
reservar, ver productos, stock o pedidos.

La conexión se instala por tenant. Credenciales y permisos no se comparten
entre clientes. Un MCP personalizado no se ejecuta automáticamente: se valida
su origen, herramientas y permisos antes de habilitarlo.

Pagos y cobros es una categoría propia. Incluye inicialmente Mercado Pago,
Payway, Ualá Bis, MODO, Stripe y adaptadores para links/QR de cobro. Conectar
una pasarela habilita herramientas acotadas —crear o compartir un cobro y
consultar su estado—; nunca entrega al modelo credenciales ni capacidad de
mover fondos libremente.

## Modelo de datos siguiente

1. ✅ `conocimiento_tenant`: categoría, clave, contenido y versión publicada.
2. ✅ `versiones_conocimiento`: historial inmutable y autor.
3. `correcciones_agente`: respuesta original, corrección y conversación fuente.
4. `memorias`: alcance, fuente, estado, confianza y vencimiento.
5. `evaluaciones_entrenamiento`: casos de prueba antes/después de publicar.
6. ✅ `publicaciones_agente`: versión activa, historial y rollback.

Todos llevan `tenant_id` obligatorio, RLS por `tenant_usuarios` y filtros
explícitos en `brain/tenants/repositorio.py`.

## Orden de construcción

1. ✅ Conocimiento versionado: horarios, precios, servicios, políticas y FAQ.
2. ✅ API autenticada del panel, sin exponer `service_role` al navegador.
3. Chat interno sobre el mismo agente.
4. Pestaña Entrenamiento con preview, pruebas, publicación y rollback.
5. Memorias con aprobación y olvido.
6. Métricas reales y límites de gasto.
7. 🟡 Interfaz base responsive e instalable lista; faltan los módulos con datos reales.

## Gates

- usuario de un tenant no puede leer ni escribir otro;
- cambios de precios/horarios son versionados y reversibles;
- entrenamiento en borrador no afecta producción;
- publicación falla si las evaluaciones bloqueantes empeoran;
- chat interno no puede cambiar de tenant desde el navegador;
- ninguna credencial de Meta o `service_role` llega al frontend;
- auditoría registra quién cambió qué y cuándo.
