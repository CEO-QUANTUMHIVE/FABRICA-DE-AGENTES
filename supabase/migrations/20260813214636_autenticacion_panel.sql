-- Vinculo entre usuarios autenticados por Supabase Auth y los negocios que
-- pueden administrar desde el panel. Es N:N: una cadena puede tener varios
-- tenants y un negocio puede tener dueño y empleados.
create table public.tenant_usuarios (
    usuario_id uuid not null references auth.users(id) on delete cascade,
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    rol text not null default 'dueño' check (rol in ('dueño', 'empleado')),
    created_at timestamptz not null default now(),
    primary key (usuario_id, tenant_id)
);

create index tenant_usuarios_tenant_idx
    on public.tenant_usuarios(tenant_id);

comment on table public.tenant_usuarios is
    'Usuarios de Supabase Auth autorizados a administrar cada tenant.';

-- La API usa la clave secreta del servidor. No se expone esta relacion a
-- anon ni authenticated: el panel presenta el JWT y el backend valida tanto
-- la sesion como la pertenencia al tenant antes de firmar modo=interno.
alter table public.tenant_usuarios enable row level security;
