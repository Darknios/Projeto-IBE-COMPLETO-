-- Execute este arquivo no SQL Editor do Supabase após 002_contagens_read_access.sql.
-- Agrega as contagens on-line por grupo de recepção.

create or replace view public.vw_online_por_grupo_recepcao as
select
    r."GrupoRecepcao" as grupo_recepcao,
    sum(c."Quantidade")::integer as quantidade_online
from public."Registros" as r
join public."Contagens" as c
    on r."Id" = c."RegistroId"
where regexp_replace(lower(c."NomeSetor"), '[^[:alnum:]]', '', 'g') in ('online', 'onlineculto')
group by r."GrupoRecepcao";

grant select on table public.vw_online_por_grupo_recepcao to anon, authenticated, service_role;
