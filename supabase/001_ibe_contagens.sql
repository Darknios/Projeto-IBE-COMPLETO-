-- Execute este arquivo no SQL Editor do Supabase antes de publicar o formulário.
-- A chave service_role deve ficar somente nos Secrets do Streamlit.

create extension if not exists pgcrypto;

create table if not exists public.ibe_contagens (
    id uuid primary key default gen_random_uuid(),
    data date not null,
    grupo_recepcao text not null check (char_length(trim(grupo_recepcao)) > 0),
    horario_culto text not null check (char_length(trim(horario_culto)) > 0),
    quantidade_pulpito integer not null default 0 check (quantidade_pulpito >= 0),
    quantidade_cadeiras_a integer not null default 0 check (quantidade_cadeiras_a >= 0),
    quantidade_cadeiras_b integer not null default 0 check (quantidade_cadeiras_b >= 0),
    quantidade_cadeiras_c integer not null default 0 check (quantidade_cadeiras_c >= 0),
    quantidade_cadeiras_d integer not null default 0 check (quantidade_cadeiras_d >= 0),
    quantidade_galeria integer not null default 0 check (quantidade_galeria >= 0),
    quantidade_salas integer not null default 0 check (quantidade_salas >= 0),
    quantidade_externo integer not null default 0 check (quantidade_externo >= 0),
    quantidade_online integer not null default 0 check (quantidade_online >= 0),
    total_presencial integer generated always as (
        quantidade_pulpito + quantidade_cadeiras_a + quantidade_cadeiras_b +
        quantidade_cadeiras_c + quantidade_cadeiras_d + quantidade_galeria +
        quantidade_salas + quantidade_externo
    ) stored,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint ibe_contagens_data_grupo_horario_key unique (data, grupo_recepcao, horario_culto)
);

create or replace function public.set_ibe_contagens_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$;

drop trigger if exists set_ibe_contagens_updated_at on public.ibe_contagens;
create trigger set_ibe_contagens_updated_at
before update on public.ibe_contagens
for each row execute function public.set_ibe_contagens_updated_at();

alter table public.ibe_contagens enable row level security;

drop policy if exists "Leitura pública do dashboard IBE" on public.ibe_contagens;
create policy "Leitura pública do dashboard IBE"
on public.ibe_contagens for select to anon, authenticated using (true);

-- Não crie políticas de insert, update ou delete para anon/authenticated.
-- O Streamlit grava exclusivamente com service_role no servidor, que ignora RLS.
