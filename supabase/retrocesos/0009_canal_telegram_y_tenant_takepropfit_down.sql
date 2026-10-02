-- Retroceso de migración 0009: canal telegram y tenant takepropfit

delete from public.tenant_dominios where dominio = 'takepropfit.com';
delete from public.services where tenant_id in (select id from public.tenants where slug = 'takepropfit');
delete from public.tenant_configs where tenant_id in (select id from public.tenants where slug = 'takepropfit');
delete from public.tenants where slug = 'takepropfit';
delete from public.agent_profiles where slug = 'takeprop';

alter table public.tenant_canales drop constraint if exists tenant_canales_canal_check;
alter table public.tenant_canales add constraint tenant_canales_canal_check 
    check (canal in ('web', 'whatsapp', 'instagram', 'facebook'));

alter table public.conversaciones drop constraint if exists conversaciones_canal_check;
alter table public.conversaciones add constraint conversaciones_canal_check 
    check (canal in ('web', 'whatsapp', 'instagram', 'facebook'));

alter table public.mensajes drop constraint if exists mensajes_canal_check;
alter table public.mensajes add constraint mensajes_canal_check 
    check (canal in ('web', 'whatsapp', 'instagram', 'facebook'));

alter table public.eventos_inbox drop constraint if exists eventos_inbox_canal_check;
alter table public.eventos_inbox add constraint eventos_inbox_canal_check 
    check (canal in ('web', 'whatsapp', 'instagram', 'facebook'));

alter table public.eventos_outbox drop constraint if exists eventos_outbox_canal_check;
alter table public.eventos_outbox add constraint eventos_outbox_canal_check 
    check (canal in ('web', 'whatsapp', 'instagram', 'facebook'));
