-- Que puede HACER un agente, no solo que sabe.
--
-- Tres tablas y no una porque hay tres niveles de decision:
--   tools          que capacidades existen en el motor
--   profile_tools  que puede un vertical (todas las barberias)
--   tenant_tools   que puede este negocio en particular
--
-- El orden importa: tenant_tools gana sobre profile_tools. Asi se le puede
-- dar o quitar una capacidad a un cliente sin tocar a los demas de su rubro.
--
-- NINGUNA tool crea negocios ni agentes. Dar de alta un negocio es una
-- operacion de la fabrica detras de login, no algo que un agente haga porque
-- alguien se lo pida bien. Regla de Sergio, 2026-08-11. Hay un test que se
-- rompe si alguien agrega una tool que cree.

create table tools (
    nombre text primary key,
    descripcion text not null,
    -- 'publico' es el visitante que llega a la landing; 'interno' es el dueño
    -- del negocio en su panel. El interno es un superconjunto: tambien
    -- atiende.
    registry text not null check (registry in ('publico', 'interno')),
    -- Ninguna escribe salvo capture_lead. Se deja declarado para que agregar
    -- una que escriba sea una decision visible y no un descuido.
    escribe boolean not null default false,
    created_at timestamptz not null default now()
);

create table profile_tools (
    perfil_slug text not null references agent_profiles(slug) on delete cascade,
    tool text not null references tools(nombre) on delete cascade,
    primary key (perfil_slug, tool)
);

create table tenant_tools (
    tenant_id uuid not null references tenants(id) on delete cascade,
    tool text not null references tools(nombre) on delete cascade,
    -- false quita una capacidad que el perfil si da. Es un override, no un
    -- borrado: si la fila no existe, manda el perfil.
    habilitada boolean not null default true,
    primary key (tenant_id, tool)
);

create table leads (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id) on delete cascade,
    nombre text not null default '',
    contacto text not null default '',
    interes text not null default '',
    -- De que sala salio. Sirve para reconstruir la conversacion cuando el
    -- lead no cierra y hay que entender por que.
    sala text not null default '',
    created_at timestamptz not null default now()
);
-- Ordenado por fecha descendente porque asi se pide siempre: nadie pregunta
-- primero por el contacto de hace tres meses.
create index leads_tenant_id_idx on leads(tenant_id, created_at desc);

-- ── Catalogo ───────────────────────────────────────────────────────────

insert into tools (nombre, descripcion, registry, escribe) values
    ('get_services',      'Los servicios reales del negocio', 'publico', false),
    ('get_business_info', 'Horarios, direccion y datos del negocio', 'publico', false),
    ('capture_lead',      'Guarda a un interesado con su contacto', 'publico', true),
    ('transfer_to_human', 'Deja constancia de que pidieron hablar con una persona', 'publico', false),
    ('get_mis_leads',     'Los interesados que dejaron contacto en este negocio', 'interno', false),
    ('get_mis_metricas',  'Cuantas conversaciones hubo y como salieron', 'interno', false),
    ('get_mis_conversaciones', 'El historial de charlas de este negocio', 'interno', false);

-- Todos los verticales arrancan con las publicas.
insert into profile_tools (perfil_slug, tool)
    select p.slug, t.nombre from agent_profiles p, tools t where t.registry = 'publico';

-- Las internas las tiene cualquier vertical: son de lectura sobre lo propio,
-- y el dueño de una barberia las necesita igual que el de una peluqueria. Lo
-- que decide si se alcanzan no es el vertical, es el MODO de la sesion.
insert into profile_tools (perfil_slug, tool)
    select p.slug, t.nombre from agent_profiles p, tools t where t.registry = 'interno';
