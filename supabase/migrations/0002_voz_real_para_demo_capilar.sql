-- El voice_id que la migracion 0001 le puso a demo_capilar era un
-- placeholder que venia del plan, no una voz real del catalogo de Fish.
--
-- Eso rompia el gate de oido de la Fase 8 sin que se notara: en la base los
-- dos tenants tenian voice_id distintos, asi que el test pasaba, pero si la
-- voz no existe de verdad el motor cae a la voz por defecto y los dos suenan
-- igual. Distinto en la base no es distinto al oido.
--
-- Este es un voice_id real, elegido por Sergio el 2026-08-10.

update voice_profiles
set voice_id = '6857ce1a3d6349aebaeb6c12a2f7dac3'
where tenant_id = (select id from tenants where slug = 'demo_capilar');
