-- La cola de salida, con el mismo criterio que la de entrada.
--
-- Espejo de `tomar_eventos_inbox`: `for update skip locked` para que dos
-- enviadores no manden el mismo mensaje. Aca el duplicado es peor que en la
-- entrada, porque le llega al cliente.

create or replace function public.tomar_eventos_outbox(
    p_limite integer default 10,
    p_bloqueo_segundos integer default 60
) returns setof public.eventos_outbox
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
    return query
    update public.eventos_outbox e
       set estado = 'procesando',
           bloqueado_hasta = now() + make_interval(secs => p_bloqueo_segundos),
           intentos = e.intentos + 1
     where e.id in (
         select o.id
           from public.eventos_outbox o
          where o.estado in ('pendiente', 'fallido')
            and o.disponible_en <= now()
            and (o.bloqueado_hasta is null or o.bloqueado_hasta < now())
          order by o.created_at
            for update skip locked
          limit p_limite
     )
    returning e.*;
end;
$$;

-- `p_reintentable` es la diferencia con la entrada. Un token revocado o una
-- ventana de 24 h vencida no se arreglan reintentando: reintentarlos es
-- gastar llamadas y demorar la cola detras de algo que nunca va a salir.
create or replace function public.cerrar_evento_outbox(
    p_id uuid,
    p_ok boolean,
    p_error text default '',
    p_reintentable boolean default true,
    p_backoff_segundos integer default 30,
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
      from public.eventos_outbox where id = p_id;
    if not found then
        return 'inexistente';
    end if;

    if p_ok then
        v_estado := 'enviado';
    elsif not p_reintentable then
        v_estado := 'descartado';
    elsif v_intentos >= p_max_intentos then
        v_estado := 'descartado';
    else
        v_estado := 'fallido';
    end if;

    update public.eventos_outbox
       set estado = v_estado,
           bloqueado_hasta = null,
           ultimo_error = coalesce(p_error, ''),
           sent_at = case when p_ok then now() else sent_at end,
           disponible_en = case
               when v_estado = 'fallido'
               then now() + make_interval(secs => p_backoff_segundos * v_intentos)
               else disponible_en
           end
     where id = p_id;

    return v_estado;
end;
$$;

create or replace function public.liberar_outbox_vencidos()
returns integer
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
    v_liberados integer;
begin
    update public.eventos_outbox
       set estado = 'pendiente', bloqueado_hasta = null
     where estado = 'procesando'
       and bloqueado_hasta is not null
       and bloqueado_hasta < now();
    get diagnostics v_liberados = row_count;
    return v_liberados;
end;
$$;

revoke all on function public.tomar_eventos_outbox(integer, integer)
    from public, anon, authenticated;
revoke all on function public.cerrar_evento_outbox(uuid, boolean, text, boolean, integer, integer)
    from public, anon, authenticated;
revoke all on function public.liberar_outbox_vencidos()
    from public, anon, authenticated;
grant execute on function public.tomar_eventos_outbox(integer, integer) to service_role;
grant execute on function public.cerrar_evento_outbox(uuid, boolean, text, boolean, integer, integer)
    to service_role;
grant execute on function public.liberar_outbox_vencidos() to service_role;
