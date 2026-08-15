-- Topes de gasto y kill-switch por negocio.
--
-- El limitador de `api/limites.py` es en memoria y para la demo web: se
-- reinicia con el proceso y no sabe de tenants. Un canal de texto necesita
-- lo contrario, porque lo que se limita acá es plata:
--
--   * cada respuesta paga un LLM y un mensaje de la Cloud API;
--   * dos negocios que hablan con el mismo agente tienen presupuestos
--     distintos y uno no puede quemarle el suyo al otro;
--   * un bucle entre dos bots automaticos factura toda la noche y nadie se
--     entera hasta la factura.

-- `if not exists` en todo lo que crea: estas migraciones se pueden llegar a
-- aplicar a mano desde el editor SQL, y en ese caso Supabase no las registra.
-- Si despues alguien corre `db push`, se vuelven a ejecutar. Que sean
-- re-ejecutables convierte ese susto en nada.
create table if not exists public.tenant_limites (
    tenant_id uuid primary key references public.tenants(id) on delete cascade,
    -- El kill-switch. En false el agente deja de contestar YA, sin
    -- desconectar el canal ni perder los mensajes: siguen entrando y
    -- quedan en la conversacion para que alguien los lea.
    respuestas_automaticas boolean not null default true,
    max_mensajes_dia integer not null default 500 check (max_mensajes_dia >= 0),
    -- El tope que ataja el bucle. Una persona no manda 30 mensajes por hora
    -- a un negocio; dos bots hablandose, si.
    max_por_conversacion_hora integer not null default 30
        check (max_por_conversacion_hora >= 0),
    motivo_pausa text not null default '',
    updated_at timestamptz not null default now()
);

comment on table public.tenant_limites is
    'Un negocio sin fila usa los defaults. Los defaults son los de la funcion, no los de esta tabla.';

alter table public.tenant_limites enable row level security;
revoke all on public.tenant_limites from anon, authenticated;
grant select on public.tenant_limites to authenticated;

drop policy if exists usuarios_ven_sus_limites on public.tenant_limites;
create policy usuarios_ven_sus_limites
    on public.tenant_limites for select
    to authenticated
    using (exists (
        select 1 from public.tenant_usuarios tu
        where tu.usuario_id = (select auth.uid())
          and tu.tenant_id = tenant_limites.tenant_id
    ));

-- Se cuenta contra `mensajes` y no contra un contador aparte a proposito: un
-- contador se desincroniza —un reinicio a mitad de camino, un mensaje que se
-- guardo y no se conto— y el dia que no coincide nadie sabe cual de los dos
-- tiene razon. La tabla de mensajes es la verdad.
create or replace function public.puede_responder(
    p_tenant_id uuid,
    p_conversacion_id uuid
) returns jsonb
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
    v_limites public.tenant_limites%rowtype;
    v_automaticas boolean := true;
    v_max_dia integer := 500;
    v_max_hora integer := 30;
    v_motivo text := '';
    v_del_dia integer;
    v_de_la_hora integer;
begin
    select * into v_limites
      from public.tenant_limites where tenant_id = p_tenant_id;
    if found then
        v_automaticas := v_limites.respuestas_automaticas;
        v_max_dia := v_limites.max_mensajes_dia;
        v_max_hora := v_limites.max_por_conversacion_hora;
        v_motivo := v_limites.motivo_pausa;
    end if;

    if not v_automaticas then
        return jsonb_build_object(
            'permitido', false,
            'motivo', coalesce(nullif(v_motivo, ''), 'respuestas automaticas pausadas')
        );
    end if;

    select count(*) into v_del_dia
      from public.mensajes
     where tenant_id = p_tenant_id
       and direccion = 'saliente'
       and ocurrido_en >= date_trunc('day', now());
    if v_del_dia >= v_max_dia then
        return jsonb_build_object(
            'permitido', false,
            'motivo', format('tope diario alcanzado (%s)', v_max_dia)
        );
    end if;

    select count(*) into v_de_la_hora
      from public.mensajes
     where tenant_id = p_tenant_id
       and conversacion_id = p_conversacion_id
       and direccion = 'saliente'
       and ocurrido_en >= now() - interval '1 hour';
    if v_de_la_hora >= v_max_hora then
        return jsonb_build_object(
            'permitido', false,
            'motivo', format('tope por conversacion alcanzado (%s/hora)', v_max_hora)
        );
    end if;

    return jsonb_build_object('permitido', true, 'motivo', '');
end;
$$;

revoke all on function public.puede_responder(uuid, uuid)
    from public, anon, authenticated;
grant execute on function public.puede_responder(uuid, uuid) to service_role;

-- QuantumHive arranca con topes bajos a proposito. Es el conejillo de indias
-- y todavia nadie miro una factura de esto.
insert into public.tenant_limites (tenant_id, max_mensajes_dia, max_por_conversacion_hora)
select id, 200, 20 from public.tenants where slug = 'quantumhive'
on conflict (tenant_id) do nothing;
