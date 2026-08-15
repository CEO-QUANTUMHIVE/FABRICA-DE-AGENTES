# Resultado: conocimiento versionado del agente

**Fecha:** 2026-08-13

## Implementado

- piezas estructuradas por categoría: horario, precio, servicio, política,
  preguntas frecuentes, tono y otros datos;
- versiones inmutables con autor, motivo y número secuencial;
- borradores que no afectan producción;
- publicación explícita de una versión;
- rollback publicando una versión histórica;
- auditoría de cada publicación y de la versión reemplazada;
- RLS de lectura por `tenant_usuarios`;
- escritura restringida al backend con `service_role`;
- conocimiento publicado incorporado al contexto del mismo agente;
- límite por pieza y límite total de contexto para proteger el gasto.

Migración aplicada: `20260813225923_conocimiento_versionado.sql`.

## Verificación real

Contra Supabase se comprobó el ciclo completo:

1. crear versión 1 como borrador: el agente no la ve;
2. publicar versión 1: el agente la carga;
3. crear versión 2: producción continúa usando versión 1;
4. publicar versión 2: el agente cambia;
5. restaurar versión 1: el agente vuelve a la información anterior;
6. el segundo tenant nunca ve la pieza;
7. el segundo tenant no puede publicar una versión ajena;
8. `supabase db lint`: sin errores de esquema.

## Siguiente incremento

API autenticada del panel. Recibirá el JWT de Supabase, resolverá los tenants
del usuario y expondrá borradores, historial, publicación y rollback sin
entregar `service_role` al navegador.
