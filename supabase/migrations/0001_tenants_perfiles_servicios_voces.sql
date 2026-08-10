-- Esquema minimo para las Fases 5-8: tenants, perfiles de vertical,
-- servicios y voces. Las tablas de tools, sesiones, leads y uso diario
-- (Fases 9-10) se agregan en sus propias migraciones cuando toque.

create extension if not exists "pgcrypto";

-- Perfil de vertical: la identidad base que comparten todos los tenants
-- de ese rubro. "receptor" es QuantumHive; "capilar" es la barberia de
-- prueba que existe solo para validar aislamiento (spec S5).
create table agent_profiles (
    slug text primary key,
    nombre text not null,
    prompt_base text not null,
    created_at timestamptz not null default now()
);

create table tenants (
    id uuid primary key default gen_random_uuid(),
    slug text unique not null,
    nombre text not null,
    perfil_slug text not null references agent_profiles(slug),
    idioma text not null default 'es',
    estado text not null default 'activo' check (estado in ('activo', 'pausado')),
    created_at timestamptz not null default now()
);

create table tenant_configs (
    tenant_id uuid primary key references tenants(id) on delete cascade,
    prompt_propio text not null default '',
    zona_horaria text not null default 'America/Argentina/Buenos_Aires',
    ajustes jsonb not null default '{}'::jsonb
);

create table services (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id) on delete cascade,
    nombre text not null,
    descripcion text not null default '',
    activo boolean not null default true,
    created_at timestamptz not null default now()
);
create index services_tenant_id_idx on services(tenant_id);

-- consentimiento_aprobado es obligatorio antes de usar una voz clonada:
-- spec S19 y S11. Sin fila en estado 'aprobado', el tenant no tiene voz
-- propia y el motor cae a la voz por defecto de Fish.
create table voice_profiles (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id) on delete cascade,
    proveedor text not null default 'fishaudio',
    voice_id text not null,
    consentimiento_aprobado boolean not null default false,
    consentimiento_registrado_en timestamptz,
    estado text not null default 'pendiente' check (estado in ('pendiente', 'aprobado', 'rechazado')),
    created_at timestamptz not null default now()
);
create index voice_profiles_tenant_id_idx on voice_profiles(tenant_id);

-- ── Datos semilla: los dos tenants del MVP (spec S5) ──────────────

insert into agent_profiles (slug, nombre, prompt_base) values
    ('receptor', 'Receptor QuantumHive',
     'Sos el asistente virtual de QuantumHive, una empresa argentina que le da vida digital a los negocios: les hace la web, les arma un empleado virtual que atiende clientes, les da voz, avatar y un catalogo que vende. Hablas espanol rioplatense, de vos.'),
    ('capilar', 'Barberia (demo)',
     'Sos el asistente de una barberia. Atendes consultas de turnos, precios de cortes y horarios. Sos calido, directo y hablas espanol rioplatense, de vos. Esta barberia es una demo: existe para probar que el motor aisla bien los datos entre negocios distintos.');

insert into tenants (slug, nombre, perfil_slug, idioma) values
    ('quantumhive', 'QuantumHive', 'receptor', 'es'),
    ('demo_capilar', 'Barberia Demo', 'capilar', 'es');

insert into tenant_configs (tenant_id, prompt_propio)
    select id, '' from tenants where slug = 'quantumhive';
insert into tenant_configs (tenant_id, prompt_propio)
    select id, 'Atendes en la barberia demo de QuantumHive, usada solo para probar aislamiento entre tenants. No es un negocio real.'
    from tenants where slug = 'demo_capilar';

insert into services (tenant_id, nombre, descripcion)
    select id, 'Web inteligente', 'Pagina que conversa con el visitante y responde por si sola' from tenants where slug = 'quantumhive';
insert into services (tenant_id, nombre, descripcion)
    select id, 'Empleado virtual', 'Agente que atiende clientes por voz, WhatsApp y Telegram' from tenants where slug = 'quantumhive';

insert into services (tenant_id, nombre, descripcion)
    select id, 'Corte clasico', 'Corte de cabello tradicional' from tenants where slug = 'demo_capilar';
insert into services (tenant_id, nombre, descripcion)
    select id, 'Afeitado a navaja', 'Afeitado tradicional con toalla caliente' from tenants where slug = 'demo_capilar';

-- Voz de QuantumHive: la clonada VOZ-003 que ya esta en produccion
-- (ver docs/CONTINUAR-ACA.md). demo_capilar usa un voice_id de catalogo
-- de Fish, sin clonar — no existe una persona real detras, asi que no
-- hay consentimiento que registrar. AJUSTAR el voice_id de demo_capilar
-- por uno real del catalogo de Fish antes del gate de oido de la Fase 8.
insert into voice_profiles (tenant_id, proveedor, voice_id, consentimiento_aprobado, consentimiento_registrado_en, estado)
    select id, 'fishaudio', '63f9f124b9401b8d8d9846c4b0d75f1a', true, now(), 'aprobado'
    from tenants where slug = 'quantumhive';
insert into voice_profiles (tenant_id, proveedor, voice_id, consentimiento_aprobado, consentimiento_registrado_en, estado)
    select id, 'fishaudio', 'e7e1049270f649f7bd48b7b48adb8898', true, now(), 'aprobado'
    from tenants where slug = 'demo_capilar';
