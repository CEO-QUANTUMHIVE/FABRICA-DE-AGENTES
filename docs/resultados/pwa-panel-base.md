# Base PWA del panel — 2026-08-13

## Resultado

Se creó `frontend/panel`, una única aplicación web instalable para Windows,
macOS, Android y iPhone. Incluye:

- login con Supabase Auth usando solamente la clave pública `anon`;
- selector de negocio obtenido desde la API autenticada;
- navegación simplificada: Inicio, Enseñar, Mi negocio y Conexiones;
- conversación para corregir palabras, tono y pronunciación;
- modo **Probar como cliente**, cambios pendientes y botón **Aplicar cambios**;
- planilla de productos, servicios y precios;
- catálogo buscable de conexiones/MCP, filtros por categoría, conectadas y
  opción de MCP personalizado con revisión;
- manifest, service worker y modo standalone;
- vista de diseño claramente identificada cuando todavía no hay datos reales.

Variables públicas requeridas:

```text
VITE_API_URL
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
```

La `service_role` no existe en el frontend y nunca debe agregarse allí.

## Verificación

- `npm run build`: correcto;
- dependencias: 0 vulnerabilidades reportadas;
- login y tablero renderizados en navegador;
- pestaña Entrenamiento y sus campos presentes;
- sin errores de navegador ni overlay de Vite;
- sin desborde horizontal en 390×844 ni 360×560;
- navegación inferior móvil visible.

## Próximo bloque

Crear/vincular el dueño real de QuantumHive para probar el login E2E y luego
conectar el chat interno al mismo agente. Memorias y métricas seguirán mostrando
estado vacío hasta existir sesiones y eventos reales; no se simulan como datos
de producción.
