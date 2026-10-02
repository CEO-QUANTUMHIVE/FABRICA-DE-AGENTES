-- Extensión de multicanal a Telegram y alta del tenant Take Prop (takepropfit).
-- Permite que el bot de Telegram atienda leads y consultas de pruebas de fondeo.

-- 1. Actualizar constraints para incluir 'telegram' en todos los canales
alter table public.tenant_canales drop constraint if exists tenant_canales_canal_check;
alter table public.tenant_canales add constraint tenant_canales_canal_check 
    check (canal in ('web', 'whatsapp', 'instagram', 'facebook', 'telegram'));

alter table public.conversaciones drop constraint if exists conversaciones_canal_check;
alter table public.conversaciones add constraint conversaciones_canal_check 
    check (canal in ('web', 'whatsapp', 'instagram', 'facebook', 'telegram'));

alter table public.mensajes drop constraint if exists mensajes_canal_check;
alter table public.mensajes add constraint mensajes_canal_check 
    check (canal in ('web', 'whatsapp', 'instagram', 'facebook', 'telegram'));

alter table public.eventos_inbox drop constraint if exists eventos_inbox_canal_check;
alter table public.eventos_inbox add constraint eventos_inbox_canal_check 
    check (canal in ('web', 'whatsapp', 'instagram', 'facebook', 'telegram'));

alter table public.eventos_outbox drop constraint if exists eventos_outbox_canal_check;
alter table public.eventos_outbox add constraint eventos_outbox_canal_check 
    check (canal in ('web', 'whatsapp', 'instagram', 'facebook', 'telegram'));

-- 2. Alta de Perfil de Agente para pruebas de fondeo (Take Prop)
insert into public.agent_profiles (slug, nombre, prompt_base) values
    ('takeprop', 'Take Prop — Pruebas de Fondeo',
     'Sos el asistente virtual y calificador oficial de Take Prop (@takepropfit).
Ayudás a traders a superar pruebas de fondeo y a gestionar cuentas live.
Tu tono es profesional, enfocado en números, disciplina operativa y gestión de riesgo. Hablás en español rioplatense/latino natural, de vos.
Pilares del modelo de Take Prop:
1. Sin costo inicial por el servicio: no cobramos honorarios por adelantado para operar la evaluación.
2. Modelo 50/50: cuando hay un retiro aprobado en la cuenta fondeada, la utilidad se divide 50% para el trader y 50% para Take Prop. Si no hay retiro, Take Prop no cobra nada por el servicio.
3. Gestión de cuentas live: para cuentas fondeadas activas, Take Prop administra con reglas estrictas de drawdown diario y total.
4. Transparencia y riesgo: no garantizamos resultados ni rentabilidades fijas; el mercado y las reglas de cada firma (FTMO, Apex, The5ers, Topstep, etc.) determinan el resultado.
5. Calificación: cuando alguien consulta, averiguá qué servicio busca (pasar prueba o cuenta live), en qué firma opera, qué tamaño de cuenta (10K a 200K+) y en qué etapa está. Si está listo para avanzar o requiere un acuerdo formal, derivalo cordial y puntualmente con el equipo humano.')
on conflict (slug) do update
set nombre = excluded.nombre, prompt_base = excluded.prompt_base;

-- 3. Alta del Tenant takepropfit
insert into public.tenants (slug, nombre, perfil_slug, idioma, estado) values
    ('takepropfit', 'Take Prop', 'takeprop', 'es', 'activo')
on conflict (slug) do update
set nombre = excluded.nombre, perfil_slug = excluded.perfil_slug, estado = 'activo';

-- 4. Configuración del Tenant
insert into public.tenant_configs (tenant_id, prompt_propio)
select id, 'Recordatorio específico: nunca pidas contraseñas, claves privadas ni datos de pago directos por chat. La evaluación de compatibilidad de la firma de fondeo se hace antes de aceptar cualquier cuenta.'
from public.tenants where slug = 'takepropfit'
on conflict (tenant_id) do update
set prompt_propio = excluded.prompt_propio;

-- 5. Servicios ofrecidos
delete from public.services where tenant_id in (select id from public.tenants where slug = 'takepropfit');

insert into public.services (tenant_id, nombre, descripcion, activo)
select id, 'Superación de pruebas de fondeo', 'Acompañamiento y operativa para superar evaluaciones de retos de fondeo sin cobro anticipado, con modelo 50/50 sobre retiros aprobados.', true
from public.tenants where slug = 'takepropfit';

insert into public.services (tenant_id, nombre, descripcion, activo)
select id, 'Administración de cuentas live', 'Gestión profesional de cuentas ya fondeadas con límites estrictos de drawdown y reparto 50/50 sobre retiros.', true
from public.tenants where slug = 'takepropfit';

-- 6. Dominio del tenant
insert into public.tenant_dominios (dominio, tenant_id, puede_declarar_tenant)
select 'takepropfit.com', id, false
from public.tenants where slug = 'takepropfit'
on conflict (dominio) do nothing;

-- 7. Registro del canal de Telegram para Take Prop (sin guardar tokens)
-- El secreto_ref es una referencia al token real, que se resuelve en tiempo de ejecución
-- desde variables de entorno o almacenamiento seguro, no se guarda en la base
insert into public.tenant_canales (tenant_id, canal, cuenta_externa_id, nombre, estado, secreto_ref, configuracion)
select 
    id as tenant_id,
    'telegram' as canal,
    'takeprop_bot' as cuenta_externa_id,  -- Identificador simbólico del bot
    'Take Prop Telegram Bot' as nombre,
    'pendiente' as estado,  -- Cambiar a 'conectado' cuando esté listo para recibir mensajes
    'telegram_takepropfit' as secreto_ref,  -- Referencia al secreto, no el token real
    '{}'::jsonb as configuracion
from public.tenants 
where slug = 'takepropfit'
on conflict (canal, cuenta_externa_id) do nothing;
