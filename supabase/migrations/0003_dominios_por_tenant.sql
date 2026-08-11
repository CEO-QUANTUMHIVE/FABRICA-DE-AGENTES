-- De donde sale el tenant de una sesion.
--
-- Hasta ahora salia del cuerpo del pedido a POST /api/token, o sea de lo que
-- dijera el navegador. Eso significaba que cualquiera, con un curl y el slug
-- de un negocio, se llevaba el agente REAL de ese negocio: su prompt, sus
-- servicios y su voz clonada.
--
-- Ahora sale del dominio donde esta embebido el widget. El navegador manda la
-- cabecera Origin y el codigo de la pagina no la puede falsear, asi que una
-- landing solo puede invocar al agente del negocio dueño de ese dominio.
--
-- No es una frontera criptografica: un cliente que no sea un navegador puede
-- mandar el Origin que quiera. Corta el caso real —que alguien se lleve el
-- agente de otro desde una pagina— y para el resto estan los limites por IP.
-- La proteccion fuerte necesita un secreto por tenant, y eso va cuando exista
-- el alta de clientes.

create table tenant_dominios (
    dominio text primary key,
    tenant_id uuid not null references tenants(id) on delete cascade,
    created_at timestamptz not null default now()
);
create index tenant_dominios_tenant_id_idx on tenant_dominios(tenant_id);

-- Los dominios donde hoy vive el widget de QuantumHive. Se guardan sin
-- protocolo y sin puerto: es lo que devuelve el hostname del Origin.
insert into tenant_dominios (tenant_id, dominio)
    select id, d from tenants, unnest(array[
        'www.quantumhive.com.ar',
        'quantumhive.com.ar',
        'voz.quantumhive.com.ar'
    ]) as d
    where slug = 'quantumhive';

-- demo_capilar no tiene dominio propio: existe solo para probar aislamiento.
-- Se lo invoca por el cuerpo del pedido, y eso ahora solo funciona fuera de
-- produccion. Cuando la barberia tenga landing, va una fila aca.
