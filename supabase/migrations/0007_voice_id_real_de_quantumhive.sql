-- El voice_id de quantumhive que sembro la migracion 0001 NO EXISTE en Fish.
--
--   sembrado   63f9f124b9401b8d8d9846c4b0d75f1a   -> HTTP 404
--   real       63f9f124b94045669c90ab37feeee4ed   -> "Sergio - QuantumHive grave"
--
-- Los primeros doce caracteres coinciden, y por eso paso todos los controles:
-- el log del agente trunca el voice_id a doce (`voz=63f9f124b940`), asi que en
-- pantalla se veia identico al del .env. El valor salio del plan de las Fases
-- 5-8, donde estaba mal, y se copio sin verificarlo contra Fish.
--
-- Roto desde que la Fase 8 cableo el agente para usar la voz del tenant en vez
-- de FISH_VOICE_ID: el .env tenia el bueno y Supabase el falso. Fish recibia
-- una voz inexistente y no sintetizaba NADA, sin log de error. El LLM
-- contestaba y no se escuchaba nada.
--
-- Verificado contra la API de Fish antes de escribir esta migracion.

update voice_profiles
set voice_id = '63f9f124b94045669c90ab37feeee4ed'
where tenant_id = (select id from tenants where slug = 'quantumhive');
