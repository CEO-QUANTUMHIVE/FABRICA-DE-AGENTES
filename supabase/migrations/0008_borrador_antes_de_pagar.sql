-- Un agente no existe de verdad hasta que el cliente paga.
--
-- El recorrido es: entra sin login, lo entrevista nuestro agente, se le arma
-- el prompt, ve la prueba, aprieta FABRICAR, paga, y RECIEN AHI el agente
-- entra en produccion y se le entrega el panel.
--
-- Todo lo que se crea antes del pago es un BORRADOR. Sin esta separacion
-- pasan tres cosas: cada entrevista cuesta plata y alguien puede darle sin
-- parar; si arrancan cien y pagan tres quedan noventa y siete agentes
-- muertos indistinguibles de los vivos; y un borrador con dominio podria
-- atender clientes sin haber pagado.
--
-- La mitad ya estaba hecha sin querer: `obtener_tenant` filtra
-- `estado = 'activo'`, asi que un borrador es INALCANZABLE por diseño. No hay
-- forma de hablarle. Lo unico que faltaba era permitir el valor.

alter table tenants drop constraint if exists tenants_estado_check;
alter table tenants add constraint tenants_estado_check
    check (estado in ('borrador', 'activo', 'pausado'));

comment on column tenants.estado is
    'borrador = entrevistado pero sin pagar, inalcanzable. activo = pago y en produccion. pausado = suspendido.';

-- Cuando se creo el borrador y cuando paso a produccion. Sirve para limpiar
-- los abandonados y para saber cuanto tarda alguien en decidirse.
alter table tenants add column if not exists borrador_desde timestamptz;
alter table tenants add column if not exists activo_desde timestamptz;

-- Los dos que ya existen son de produccion, no borradores.
update tenants set activo_desde = created_at where estado = 'activo' and activo_desde is null;
