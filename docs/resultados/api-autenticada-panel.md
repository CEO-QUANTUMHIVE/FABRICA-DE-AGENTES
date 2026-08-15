# API autenticada del panel — 2026-08-13

## Resultado

El backend ya expone el primer contrato seguro del panel:

- `GET /api/panel/tenants`: lista solo los negocios activos vinculados al usuario;
- `GET /api/panel/{tenant_slug}/conocimiento`: devuelve piezas y versiones del tenant autorizado;
- `POST /api/panel/{tenant_slug}/conocimiento/borradores`: crea una version sin afectar produccion;
- `POST /api/panel/{tenant_slug}/conocimiento/{version_id}/publicar`: publica o restaura una version.

Todos exigen `Authorization: Bearer <Supabase JWT>`. La API valida el JWT con
Supabase Auth y despues exige una fila en `tenant_usuarios` para el tenant de la
ruta. El `tenant_id` del cuerpo se ignora: la escritura siempre usa el tenant
resuelto por el servidor.

La `service_role` vive solamente en el backend. El navegador nunca la recibe.

## Pruebas

- sin sesion: `401`;
- sesion valida pero de otro tenant: `403`;
- tenant inexistente: `404`;
- borrador invalido: `400`;
- lectura, borrador y publicacion usan el tenant autorizado;
- intento de mandar otro `tenant_id` en el JSON no cambia el destino;
- suite completa: **286 passed, 15 deselected**.

## Pendiente operativo

Falta crear o vincular el primer usuario real de Supabase Auth con
`tenant_001` QuantumHive para ejecutar la prueba E2E desde un navegador. El
contrato y sus pruebas aisladas ya estan listos para la PWA.
