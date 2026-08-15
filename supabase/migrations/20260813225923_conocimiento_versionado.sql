-- Conocimiento editable desde el panel, versionado y reversible.
-- Un borrador nunca alcanza al agente: produccion solo lee la version a la
-- que apunta `version_publicada_id`.

create table public.conocimiento_tenant (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    categoria text not null check (
        categoria in ('horario', 'precio', 'servicio', 'politica', 'faq', 'tono', 'otro')
    ),
    clave text not null,
    titulo text not null,
    estado text not null default 'activo' check (estado in ('activo', 'archivado')),
    version_publicada_id uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (tenant_id, categoria, clave),
    unique (id, tenant_id)
);
create index conocimiento_tenant_categoria_idx
    on public.conocimiento_tenant(tenant_id, categoria, estado);

create table public.versiones_conocimiento (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    conocimiento_id uuid not null,
    numero integer not null check (numero > 0),
    contenido jsonb not null check (octet_length(contenido::text) <= 16384),
    motivo text not null default '',
    creado_por uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now(),
    foreign key (conocimiento_id, tenant_id)
        references public.conocimiento_tenant(id, tenant_id) on delete cascade,
    unique (conocimiento_id, numero),
    unique (id, tenant_id)
);
create index versiones_conocimiento_historial_idx
    on public.versiones_conocimiento(tenant_id, conocimiento_id, numero desc);

alter table public.conocimiento_tenant
    add constraint conocimiento_version_publicada_fk
    foreign key (version_publicada_id, tenant_id)
    references public.versiones_conocimiento(id, tenant_id);

create table public.publicaciones_agente (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    conocimiento_id uuid not null,
    version_anterior_id uuid,
    version_publicada_id uuid not null,
    publicado_por uuid references auth.users(id) on delete set null,
    motivo text not null default '',
    created_at timestamptz not null default now(),
    foreign key (conocimiento_id, tenant_id)
        references public.conocimiento_tenant(id, tenant_id) on delete cascade,
    foreign key (version_anterior_id, tenant_id)
        references public.versiones_conocimiento(id, tenant_id),
    foreign key (version_publicada_id, tenant_id)
        references public.versiones_conocimiento(id, tenant_id)
);
create index publicaciones_agente_tenant_idx
    on public.publicaciones_agente(tenant_id, created_at desc);

-- Crea o actualiza una pieza como nueva version BORRADOR. La numeracion se
-- asigna dentro de la transaccion y se serializa por pieza para evitar que dos
-- ediciones concurrentes generen la misma version.
create or replace function public.crear_borrador_conocimiento(
    p_tenant_id uuid,
    p_categoria text,
    p_clave text,
    p_titulo text,
    p_contenido jsonb,
    p_creado_por uuid default null,
    p_motivo text default ''
) returns jsonb
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
    v_conocimiento_id uuid;
    v_version_id uuid;
    v_numero integer;
begin
    if p_categoria not in ('horario', 'precio', 'servicio', 'politica', 'faq', 'tono', 'otro') then
        raise exception 'categoria de conocimiento invalida';
    end if;
    if coalesce(trim(p_clave), '') = '' or coalesce(trim(p_titulo), '') = '' then
        raise exception 'clave y titulo son obligatorios';
    end if;
    if p_contenido is null or jsonb_typeof(p_contenido) <> 'object' then
        raise exception 'contenido debe ser un objeto JSON';
    end if;
    perform 1 from public.tenants where id = p_tenant_id and estado = 'activo';
    if not found then
        raise exception 'tenant no activo';
    end if;

    insert into public.conocimiento_tenant (tenant_id, categoria, clave, titulo)
    values (p_tenant_id, p_categoria, trim(p_clave), trim(p_titulo))
    on conflict (tenant_id, categoria, clave) do update
       set titulo = excluded.titulo,
           estado = 'activo',
           updated_at = now()
    returning id into v_conocimiento_id;

    perform 1 from public.conocimiento_tenant
     where id = v_conocimiento_id and tenant_id = p_tenant_id
     for update;

    select coalesce(max(numero), 0) + 1
      into v_numero
      from public.versiones_conocimiento
     where conocimiento_id = v_conocimiento_id
       and tenant_id = p_tenant_id;

    insert into public.versiones_conocimiento (
        tenant_id, conocimiento_id, numero, contenido, motivo, creado_por
    ) values (
        p_tenant_id, v_conocimiento_id, v_numero, p_contenido,
        coalesce(p_motivo, ''), p_creado_por
    ) returning id into v_version_id;

    return jsonb_build_object(
        'conocimiento_id', v_conocimiento_id,
        'version_id', v_version_id,
        'numero', v_numero,
        'publicada', false
    );
end;
$$;

-- Publicar una version solo mueve el puntero activo y deja una auditoria. Para
-- rollback se publica una version anterior: no se borra ni reescribe historia.
create or replace function public.publicar_version_conocimiento(
    p_tenant_id uuid,
    p_version_id uuid,
    p_publicado_por uuid default null,
    p_motivo text default ''
) returns jsonb
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
    v_conocimiento_id uuid;
    v_version_anterior_id uuid;
    v_numero integer;
    v_publicacion_id uuid;
begin
    select vc.conocimiento_id, vc.numero
      into v_conocimiento_id, v_numero
      from public.versiones_conocimiento vc
      join public.conocimiento_tenant ct
        on ct.id = vc.conocimiento_id and ct.tenant_id = vc.tenant_id
     where vc.id = p_version_id
       and vc.tenant_id = p_tenant_id
       and ct.estado = 'activo';
    if not found then
        raise exception 'version no pertenece a un conocimiento activo del tenant';
    end if;

    select version_publicada_id
      into v_version_anterior_id
      from public.conocimiento_tenant
     where id = v_conocimiento_id and tenant_id = p_tenant_id
     for update;

    update public.conocimiento_tenant
       set version_publicada_id = p_version_id,
           updated_at = now()
     where id = v_conocimiento_id and tenant_id = p_tenant_id;

    insert into public.publicaciones_agente (
        tenant_id, conocimiento_id, version_anterior_id,
        version_publicada_id, publicado_por, motivo
    ) values (
        p_tenant_id, v_conocimiento_id, v_version_anterior_id,
        p_version_id, p_publicado_por, coalesce(p_motivo, '')
    ) returning id into v_publicacion_id;

    return jsonb_build_object(
        'publicacion_id', v_publicacion_id,
        'conocimiento_id', v_conocimiento_id,
        'version_id', p_version_id,
        'version_anterior_id', v_version_anterior_id,
        'numero', v_numero,
        'publicada', true
    );
end;
$$;

revoke all on function public.crear_borrador_conocimiento(
    uuid, text, text, text, jsonb, uuid, text
) from public, anon, authenticated;
grant execute on function public.crear_borrador_conocimiento(
    uuid, text, text, text, jsonb, uuid, text
) to service_role;

revoke all on function public.publicar_version_conocimiento(
    uuid, uuid, uuid, text
) from public, anon, authenticated;
grant execute on function public.publicar_version_conocimiento(
    uuid, uuid, uuid, text
) to service_role;

alter table public.conocimiento_tenant enable row level security;
alter table public.versiones_conocimiento enable row level security;
alter table public.publicaciones_agente enable row level security;

create policy usuarios_ven_su_conocimiento
    on public.conocimiento_tenant for select
    to authenticated
    using (exists (
        select 1 from public.tenant_usuarios tu
        where tu.usuario_id = (select auth.uid())
          and tu.tenant_id = conocimiento_tenant.tenant_id
    ));

create policy usuarios_ven_sus_versiones
    on public.versiones_conocimiento for select
    to authenticated
    using (exists (
        select 1 from public.tenant_usuarios tu
        where tu.usuario_id = (select auth.uid())
          and tu.tenant_id = versiones_conocimiento.tenant_id
    ));

create policy usuarios_ven_sus_publicaciones
    on public.publicaciones_agente for select
    to authenticated
    using (exists (
        select 1 from public.tenant_usuarios tu
        where tu.usuario_id = (select auth.uid())
          and tu.tenant_id = publicaciones_agente.tenant_id
    ));

revoke all on public.conocimiento_tenant, public.versiones_conocimiento,
    public.publicaciones_agente from anon, authenticated;
grant select on public.conocimiento_tenant, public.versiones_conocimiento,
    public.publicaciones_agente to authenticated;
