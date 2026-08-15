-- Tomar trabajo de una cola sin que dos workers agarren lo mismo.
--
-- Esto no se puede hacer desde el cliente: un SELECT y despues un UPDATE
-- dejan una ventana en el medio, y en esa ventana otro worker lee la misma
-- fila. El resultado seria contestarle dos veces al mismo cliente, que es
-- exactamente lo que el inbox vino a evitar.
--
-- `for update skip locked` es lo que lo cierra: la fila queda tomada dentro
-- de la misma transaccion que la marca, y el que llega segundo la saltea en
-- vez de esperarla.

-- El evento apunta a lo que creo. Sin esto, el procesador tendria que sacar
-- la conversacion del payload crudo del proveedor, o sea meter logica de
-- WhatsApp adentro de algo que tiene que servir para los cuatro canales.
alter table public.eventos_inbox
    add column if not exists conversacion_id uuid;

do $$
begin
    alter table public.eventos_inbox
        add constraint eventos_inbox_conversacion_fk
        foreign key (conversacion_id, tenant_id)
        references public.conversaciones(id, tenant_id) on delete cascade;
exception
    when duplicate_object then null;
end;
$$;

-- Misma funcion que la migracion 20260813223713, con un solo cambio: deja
-- anotado en el evento a que conversacion pertenece.
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

    update public.eventos_inbox
       set conversacion_id = v_conversacion_id
     where id = v_inbox_id;

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

create or replace function public.tomar_eventos_inbox(
    p_limite integer default 10,
    p_bloqueo_segundos integer default 60
) returns setof public.eventos_inbox
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
    return query
    update public.eventos_inbox e
       set estado = 'procesando',
           bloqueado_hasta = now() + make_interval(secs => p_bloqueo_segundos),
           intentos = e.intentos + 1
     where e.id in (
         select i.id
           from public.eventos_inbox i
          where i.estado in ('pendiente', 'fallido')
            and i.disponible_en <= now()
            -- Un worker que murio dejo la fila en 'procesando' con un bloqueo
            -- vencido. Cuando vence, vuelve a estar disponible sola.
            and (i.bloqueado_hasta is null or i.bloqueado_hasta < now())
          order by i.created_at
            for update skip locked
          limit p_limite
     )
    returning e.*;
end;
$$;

-- Un bloqueo vencido devuelve la fila a la cola aunque haya quedado en
-- 'procesando': sin esto, un worker que muere se lleva el mensaje con el.
create or replace function public.liberar_eventos_vencidos()
returns integer
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
    v_liberados integer;
begin
    update public.eventos_inbox
       set estado = 'pendiente', bloqueado_hasta = null
     where estado = 'procesando'
       and bloqueado_hasta is not null
       and bloqueado_hasta < now();
    get diagnostics v_liberados = row_count;
    return v_liberados;
end;
$$;

create or replace function public.cerrar_evento_inbox(
    p_id uuid,
    p_ok boolean,
    p_error text default '',
    p_backoff_segundos integer default 60,
    p_max_intentos integer default 5
) returns text
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
    v_intentos integer;
    v_estado text;
begin
    select intentos into v_intentos
      from public.eventos_inbox where id = p_id;
    if not found then
        return 'inexistente';
    end if;

    if p_ok then
        v_estado := 'procesado';
    elsif v_intentos >= p_max_intentos then
        -- Se deja de reintentar. Un mensaje que falla siempre no puede
        -- ocupar la cola para siempre ni pagar un LLM en cada vuelta.
        v_estado := 'descartado';
    else
        v_estado := 'fallido';
    end if;

    update public.eventos_inbox
       set estado = v_estado,
           bloqueado_hasta = null,
           ultimo_error = coalesce(p_error, ''),
           processed_at = case when p_ok then now() else processed_at end,
           disponible_en = case
               when v_estado = 'fallido'
               then now() + make_interval(secs => p_backoff_segundos * v_intentos)
               else disponible_en
           end
     where id = p_id;

    return v_estado;
end;
$$;

revoke all on function public.tomar_eventos_inbox(integer, integer)
    from public, anon, authenticated;
revoke all on function public.liberar_eventos_vencidos()
    from public, anon, authenticated;
revoke all on function public.cerrar_evento_inbox(uuid, boolean, text, integer, integer)
    from public, anon, authenticated;
grant execute on function public.tomar_eventos_inbox(integer, integer) to service_role;
grant execute on function public.liberar_eventos_vencidos() to service_role;
grant execute on function public.cerrar_evento_inbox(uuid, boolean, text, integer, integer)
    to service_role;
