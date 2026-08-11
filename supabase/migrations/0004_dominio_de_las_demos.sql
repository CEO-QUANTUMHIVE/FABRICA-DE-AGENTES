-- El sitio de plantillas de Webs Inteligentes usa el agente de la barberia
-- demo en todas sus paginas.
--
-- OJO con esto si el dia de mañana cada demo tiene que hablar distinto: el
-- navegador manda el Origin, que trae el SITIO y no la PAGINA. O sea que
-- websinteligentes.quantumhive.com.ar/.../barberia y /.../dentista llegan
-- iguales, y no se pueden separar por aca.
--
-- Hoy no importa porque todas las demos comparten contenido y agente. Cuando
-- deje de ser asi hay dos caminos: un subdominio por vertical, o marcar este
-- host como "de demos" y dejar que la pagina declare que tenant quiere. Ese
-- permiso no lo puede tener el dominio de un cliente real.

insert into tenant_dominios (tenant_id, dominio)
    select id, 'websinteligentes.quantumhive.com.ar'
    from tenants where slug = 'demo_capilar';
