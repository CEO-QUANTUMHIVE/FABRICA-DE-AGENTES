-- El alta de un negocio: lo que le faltaba a la fabrica para ser una fabrica.
--
-- Hasta hoy dar de alta un cliente era SQL a mano. Eso no escala y, peor, no
-- deja rastro de quien lo hizo.
--
-- La regla del 2026-08-11 sigue en pie: NADIE crea negocios hablando. Esto es
-- una operacion detras de login y de una lista explicita de operadores, no una
-- tool que un agente pueda alcanzar.

-- Quien puede dar de alta. Una tabla y no "el dueño de quantumhive": ser
-- cliente de la plataforma y ser el que la opera son dos cosas distintas, y
-- confundirlas hace que el dia que QuantumHive tenga un empleado con acceso al
-- panel, ese empleado pueda crear negocios.
create table if not exists public.plataforma_operadores (
    usuario_id uuid primary key references auth.users(id) on delete cascade,
    nota text not null default '',
    created_at timestamptz not null default now()
);

alter table public.plataforma_operadores enable row level security;
revoke all on public.plataforma_operadores from anon, authenticated;

comment on table public.plataforma_operadores is
    'Quien puede dar de alta negocios. No se expone a authenticated: solo el backend lo lee.';

-- El alta entera en una transaccion. Si falla a la mitad, no queda un tenant
-- sin config ni un dueño vinculado a un negocio que no existe.
create or replace function public.crear_negocio_borrador(
    p_operador_id uuid,
    p_slug text,
    p_nombre text,
    p_perfil_slug text,
    p_prompt_propio text default '',
    p_dominio text default '',
    p_email_dueno text default ''
) returns jsonb
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
    v_tenant_id uuid;
    v_dueno_id uuid;
begin
    perform 1 from public.plataforma_operadores where usuario_id = p_operador_id;
    if not found then
        raise exception 'no autorizado para dar de alta negocios';
    end if;

    if coalesce(trim(p_slug), '') = '' or coalesce(trim(p_nombre), '') = '' then
        raise exception 'slug y nombre son obligatorios';
    end if;
    -- El slug viaja en el nombre de sala, que el agente parsea por posicion.
    -- Un guion de mas ahi corre todos los campos.
    if p_slug !~ '^[a-z0-9_]+$' then
        raise exception 'el slug solo admite minusculas, numeros y guion bajo';
    end if;

    perform 1 from public.agent_profiles where slug = p_perfil_slug;
    if not found then
        raise exception 'no existe el perfil %', p_perfil_slug;
    end if;

    -- Nace en borrador SIEMPRE. `obtener_tenant` filtra estado='activo', asi
    -- que hasta que se pague el agente no existe para nadie.
    insert into public.tenants (slug, nombre, idioma, estado, perfil_slug)
    values (trim(p_slug), trim(p_nombre), 'es', 'borrador', p_perfil_slug)
    returning id into v_tenant_id;

    insert into public.tenant_configs (tenant_id, prompt_propio)
    values (v_tenant_id, coalesce(p_prompt_propio, ''));

    if coalesce(trim(p_dominio), '') <> '' then
        insert into public.tenant_dominios (dominio, tenant_id, puede_declarar_tenant)
        values (lower(trim(p_dominio)), v_tenant_id, false)
        on conflict (dominio) do nothing;
    end if;

    -- Si el dueño ya tiene cuenta, queda vinculado de una. Si no, se vincula
    -- cuando acepte la invitacion: el alta no depende de que exista antes.
    if coalesce(trim(p_email_dueno), '') <> '' then
        select id into v_dueno_id
          from auth.users where lower(email) = lower(trim(p_email_dueno));
        if v_dueno_id is not null then
            insert into public.tenant_usuarios (usuario_id, tenant_id, rol)
            values (v_dueno_id, v_tenant_id, 'dueño')
            on conflict do nothing;
        end if;
    end if;

    return jsonb_build_object(
        'tenant_id', v_tenant_id,
        'slug', trim(p_slug),
        'estado', 'borrador',
        'dueno_vinculado', v_dueno_id is not null
    );
end;
$$;

-- Activar es lo que pasa cuando se paga. Separado del alta a proposito: el
-- alta la hace quien vende, y esto lo dispara el cobro.
create or replace function public.activar_negocio(
    p_operador_id uuid,
    p_slug text
) returns jsonb
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
    v_estado text;
begin
    perform 1 from public.plataforma_operadores where usuario_id = p_operador_id;
    if not found then
        raise exception 'no autorizado para activar negocios';
    end if;

    update public.tenants set estado = 'activo'
     where slug = p_slug and estado = 'borrador'
    returning estado into v_estado;

    if v_estado is null then
        select estado into v_estado from public.tenants where slug = p_slug;
        if v_estado is null then
            raise exception 'no existe el negocio %', p_slug;
        end if;
        -- Ya estaba activo. No es un error: activar dos veces es lo mismo que
        -- activar una, y un cobro reintentado no tiene que romper.
        return jsonb_build_object('slug', p_slug, 'estado', v_estado, 'cambio', false);
    end if;

    return jsonb_build_object('slug', p_slug, 'estado', v_estado, 'cambio', true);
end;
$$;

revoke all on function public.crear_negocio_borrador(uuid, text, text, text, text, text, text)
    from public, anon, authenticated;
revoke all on function public.activar_negocio(uuid, text)
    from public, anon, authenticated;
grant execute on function public.crear_negocio_borrador(uuid, text, text, text, text, text, text)
    to service_role;
grant execute on function public.activar_negocio(uuid, text) to service_role;

-- Sergio opera la fabrica.
insert into public.plataforma_operadores (usuario_id, nota)
select id, 'fundador' from auth.users where lower(email) = 'ceo@quantumhive.com.ar'
on conflict (usuario_id) do nothing;
