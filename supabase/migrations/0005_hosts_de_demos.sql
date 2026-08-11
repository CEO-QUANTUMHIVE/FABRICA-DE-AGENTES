-- Un host puede hospedar varios rubros.
--
-- websinteligentes.quantumhive.com.ar tiene ocho plantillas de barberia, ocho
-- de gastronomia y asi: cincuenta variantes en ocho rubros, todas en el mismo
-- dominio. La idea es un agente por RUBRO, no uno por plantilla ni uno para
-- todas.
--
-- El Origin trae el sitio y no la pagina, asi que el dominio solo no alcanza
-- para elegir entre ocho agentes. Para esos hosts —que son NUESTROS, y
-- controlamos lo que se publica ahi— la pagina declara que agente quiere con
-- data-tenant, y el backend lo acepta.
--
-- El dominio de un cliente real NUNCA lleva esta marca: mapea a un solo
-- tenant y no puede pedir otro. Si pudiera, volveriamos al agujero que la
-- migracion 0003 cerro.

alter table tenant_dominios
    add column puede_declarar_tenant boolean not null default false;

comment on column tenant_dominios.puede_declarar_tenant is
    'Solo para hosts propios de demos, donde conviven varios rubros. Un dominio de cliente va siempre en false.';

update tenant_dominios
set puede_declarar_tenant = true
where dominio = 'websinteligentes.quantumhive.com.ar';
