# Resultado: autenticación y base multicanal

**Fecha:** 2026-08-13

## Cerrado

- Base real auditada: `quantumhive` está activo y es el primer tenant sembrado.
- Migración de `tenant_usuarios` aplicada; tabla vacía y RLS habilitado.
- La API valida el JWT con Supabase y exige pertenencia al tenant resuelto.
- Sin sesión, token inválido o sesión de otro negocio: `modo=publico`.
- El modo viaja firmado en el token y el worker falla cerrado al leerlo.
- CORS permite `Authorization`.
- Web, WhatsApp, Instagram y Facebook comparten contrato e identidad; no se
  creó ningún bot aislado.

## Verificación

- Suite previa: 252 tests.
- Integración previa: 5 tests contra Supabase real.
- Suite final con los cambios: 272 tests.
- Integración final contra Supabase: 5 tests.

## Gate todavía abierto

No se creó un usuario dueño porque no se proporcionaron email ni contraseña.
Por eso falta el E2E real: login del dueño de QuantumHive, acceso interno al
propio tenant y prueba cruzada contra otro tenant. El código y la tabla están
listos para ese alta, pero autenticación no se declara completamente cerrada
hasta ejecutar ese gate.
