-- Execute este arquivo no SQL Editor do Supabase.
-- Libera somente a leitura necessária ao gráfico de distribuição por setor.

grant select on table public."Contagens" to anon, authenticated, service_role;

alter table public."Contagens" enable row level security;

drop policy if exists "Permitir leitura pública" on public."Contagens";
create policy "Permitir leitura pública"
on public."Contagens"
for select
to anon, authenticated
using (true);
