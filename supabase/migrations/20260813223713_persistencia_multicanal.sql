-- Persistencia compartida por Web, WhatsApp, Instagram y Facebook.
-- Los canales son adaptadores: tenant, conversaciones, mensajes y estados
-- viven una sola vez y alimentan tanto al agente como al panel.

create table public.tenant_canales (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    canal text not null check (canal in ('web', 'whatsapp', 'instagram', 'facebook')),
    cuenta_externa_id text not null,
    nombre text not null default '',
    estado text not null default 'pendiente'
        check (estado in ('pendiente', 'conectado', 'pausado', 'revocado', 'error')),
    secreto_ref text,
    configuracion jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (canal, cuenta_externa_id),
    unique (id, tenant_id)
);
create index tenant_canales_tenant_idx
    on public.tenant_canales(tenant_id, canal, estado);

comment on column public.tenant_canales.secreto_ref is
    'Referencia a un secreto cifrado externo. Nunca guardar access tokens en esta tabla.';

create table public.conversaciones (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    tenant_canal_id uuid not null,
    canal text not null check (canal in ('web', 'whatsapp', 'instagram', 'facebook')),
    conversacion_externa_id text not null,
    contacto_externo_id text not null,
    nombre_contacto text not null default '',
    modo_atencion text not null default 'automatico'
        check (modo_atencion in ('automatico', 'humano', 'cerrado')),
    metadata jsonb not null default '{}'::jsonb,
    ultimo_mensaje_en timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (tenant_canal_id, tenant_id)
        references public.tenant_canales(id, tenant_id) on delete cascade,
    unique (tenant_canal_id, conversacion_externa_id),
    unique (id, tenant_id)
);
create index conversaciones_tenant_ultimas_idx
    on public.conversaciones(tenant_id, ultimo_mensaje_en desc);
create index conversaciones_handoff_idx
    on public.conversaciones(tenant_id, modo_atencion, ultimo_mensaje_en desc);

create table public.mensajes (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    tenant_canal_id uuid not null,
    conversacion_id uuid not null,
    canal text not null check (canal in ('web', 'whatsapp', 'instagram', 'facebook')),
    mensaje_externo_id text not null,
    direccion text not null check (direccion in ('entrante', 'saliente', 'sistema')),
    texto text not null default '',
    contenido jsonb not null default '{}'::jsonb,
    estado text not null default 'recibido'
        check (estado in ('recibido', 'pendiente', 'enviado', 'entregado', 'leido', 'fallido')),
    ocurrido_en timestamptz not null,
    created_at timestamptz not null default now(),
    foreign key (tenant_canal_id, tenant_id)
        references public.tenant_canales(id, tenant_id) on delete cascade,
    foreign key (conversacion_id, tenant_id)
        references public.conversaciones(id, tenant_id) on delete cascade,
    unique (tenant_canal_id, mensaje_externo_id)
);
create index mensajes_conversacion_idx
    on public.mensajes(tenant_id, conversacion_id, ocurrido_en);
create index mensajes_metricas_idx
    on public.mensajes(tenant_id, canal, direccion, ocurrido_en desc);

-- Registro durable de webhooks recibidos. El proveedor puede reintentar un
-- mismo evento: la restriccion evita procesarlo y responder dos veces.
create table public.eventos_inbox (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    tenant_canal_id uuid not null,
    canal text not null check (canal in ('web', 'whatsapp', 'instagram', 'facebook')),
    evento_externo_id text not null,
    tipo text not null default 'mensaje',
    payload jsonb not null default '{}'::jsonb,
    estado text not null default 'pendiente'
        check (estado in ('pendiente', 'procesando', 'procesado', 'fallido', 'descartado')),
    intentos integer not null default 0 check (intentos >= 0),
    disponible_en timestamptz not null default now(),
    bloqueado_hasta timestamptz,
    ultimo_error text not null default '',
    created_at timestamptz not null default now(),
    processed_at timestamptz,
    foreign key (tenant_canal_id, tenant_id)
        references public.tenant_canales(id, tenant_id) on delete cascade,
    unique (tenant_canal_id, evento_externo_id)
);
create index eventos_inbox_pendientes_idx
    on public.eventos_inbox(estado, disponible_en)
    where estado in ('pendiente', 'fallido');
create index eventos_inbox_tenant_idx
    on public.eventos_inbox(tenant_id, created_at desc);

-- Salidas pendientes de enviar al proveedor. El id de idempotencia impide
-- duplicados aunque un worker muera despues de enviar y antes de confirmar.
create table public.eventos_outbox (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.tenants(id) on delete cascade,
    tenant_canal_id uuid not null,
    conversacion_id uuid not null,
    canal text not null check (canal in ('web', 'whatsapp', 'instagram', 'facebook')),
    clave_idempotencia text not null,
    payload jsonb not null,
    estado text not null default 'pendiente'
        check (estado in ('pendiente', 'procesando', 'enviado', 'fallido', 'descartado')),
    intentos integer not null default 0 check (intentos >= 0),
    disponible_en timestamptz not null default now(),
    bloqueado_hasta timestamptz,
    ultimo_error text not null default '',
    created_at timestamptz not null default now(),
    sent_at timestamptz,
    foreign key (tenant_canal_id, tenant_id)
        references public.tenant_canales(id, tenant_id) on delete cascade,
    foreign key (conversacion_id, tenant_id)
        references public.conversaciones(id, tenant_id) on delete cascade,
    unique (tenant_canal_id, clave_idempotencia)
);
create index eventos_outbox_pendientes_idx
    on public.eventos_outbox(estado, disponible_en)
    where estado in ('pendiente', 'fallido');
create index eventos_outbox_tenant_idx
    on public.eventos_outbox(tenant_id, created_at desc);

-- El alta del webhook es una sola transaccion. Si el proceso cae, el inbox
-- queda pendiente para reanudar; si Meta reintenta, devuelve duplicado sin
-- crear otra conversacion ni otro mensaje.
create or replace function public.registrar_mensaje_entrante(
    p_tenant_canal_id uuid,
    p_tenant_id uuid,
    p_canal text,
    p_conversacion_externa_id text,
    p_remitente_externo_id text,
    p_evento_externo_id text,
    p_mensaje_externo_id text,
    p_texto text,
    p_recibido_en timestamptz,
    p_payload jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
    v_inbox_id uuid;
    v_conversacion_id uuid;
    v_mensaje_id uuid;
begin
    if coalesce(trim(p_conversacion_externa_id), '') = ''
       or coalesce(trim(p_remitente_externo_id), '') = ''
       or coalesce(trim(p_evento_externo_id), '') = ''
       or coalesce(trim(p_mensaje_externo_id), '') = '' then
        raise exception 'identificadores externos obligatorios';
    end if;

    perform 1
      from public.tenant_canales tc
      join public.tenants t on t.id = tc.tenant_id
     where tc.id = p_tenant_canal_id
       and tc.tenant_id = p_tenant_id
       and tc.canal = p_canal
       and tc.estado = 'conectado'
       and t.estado = 'activo';
    if not found then
        raise exception 'canal no conectado o no pertenece al tenant';
    end if;

    insert into public.eventos_inbox (
        tenant_id, tenant_canal_id, canal, evento_externo_id, payload
    ) values (
        p_tenant_id, p_tenant_canal_id, p_canal, p_evento_externo_id,
        coalesce(p_payload, '{}'::jsonb)
    )
    on conflict (tenant_canal_id, evento_externo_id) do nothing
    returning id into v_inbox_id;

    if v_inbox_id is null then
        return jsonb_build_object('duplicado', true);
    end if;

    insert into public.conversaciones (
        tenant_id, tenant_canal_id, canal, conversacion_externa_id,
        contacto_externo_id, ultimo_mensaje_en
    ) values (
        p_tenant_id, p_tenant_canal_id, p_canal,
        p_conversacion_externa_id, p_remitente_externo_id, p_recibido_en
    )
    on conflict (tenant_canal_id, conversacion_externa_id) do update
       set contacto_externo_id = excluded.contacto_externo_id,
           ultimo_mensaje_en = greatest(
               coalesce(public.conversaciones.ultimo_mensaje_en, excluded.ultimo_mensaje_en),
               excluded.ultimo_mensaje_en
           ),
           updated_at = now()
    returning id into v_conversacion_id;

    insert into public.mensajes (
        tenant_id, tenant_canal_id, conversacion_id, canal,
        mensaje_externo_id, direccion, texto, contenido, estado, ocurrido_en
    ) values (
        p_tenant_id, p_tenant_canal_id, v_conversacion_id, p_canal,
        p_mensaje_externo_id, 'entrante', coalesce(p_texto, ''),
        coalesce(p_payload, '{}'::jsonb), 'recibido', p_recibido_en
    )
    on conflict (tenant_canal_id, mensaje_externo_id) do nothing
    returning id into v_mensaje_id;

    return jsonb_build_object(
        'duplicado', false,
        'inbox_id', v_inbox_id,
        'conversacion_id', v_conversacion_id,
        'mensaje_id', v_mensaje_id
    );
end;
$$;

revoke all on function public.registrar_mensaje_entrante(
    uuid, uuid, text, text, text, text, text, text, timestamptz, jsonb
) from public, anon, authenticated;
grant execute on function public.registrar_mensaje_entrante(
    uuid, uuid, text, text, text, text, text, text, timestamptz, jsonb
) to service_role;

-- Defensa adicional para cualquier acceso futuro desde el panel.
alter table public.tenant_canales enable row level security;
alter table public.conversaciones enable row level security;
alter table public.mensajes enable row level security;
alter table public.eventos_inbox enable row level security;
alter table public.eventos_outbox enable row level security;

create policy tenant_usuarios_ve_sus_vinculos
    on public.tenant_usuarios for select
    to authenticated
    using ((select auth.uid()) = usuario_id);

create policy usuarios_ven_sus_canales
    on public.tenant_canales for select
    to authenticated
    using (exists (
        select 1 from public.tenant_usuarios tu
        where tu.usuario_id = (select auth.uid())
          and tu.tenant_id = tenant_canales.tenant_id
    ));

create policy usuarios_ven_sus_conversaciones
    on public.conversaciones for select
    to authenticated
    using (exists (
        select 1 from public.tenant_usuarios tu
        where tu.usuario_id = (select auth.uid())
          and tu.tenant_id = conversaciones.tenant_id
    ));

create policy usuarios_ven_sus_mensajes
    on public.mensajes for select
    to authenticated
    using (exists (
        select 1 from public.tenant_usuarios tu
        where tu.usuario_id = (select auth.uid())
          and tu.tenant_id = mensajes.tenant_id
    ));

revoke all on public.tenant_canales, public.conversaciones, public.mensajes,
    public.eventos_inbox, public.eventos_outbox from anon, authenticated;
grant select on public.tenant_usuarios, public.tenant_canales,
    public.conversaciones, public.mensajes to authenticated;
