-- IBE / Streamlity - leitura segura do dashboard com o usuário autenticado
-- Rode UMA VEZ no SQL Editor do Supabase.
--
-- O app usa o JWT criado no login. Somente contas cujo app_metadata contenha:
--   igreja_id = 34a358e0-eeb5-4975-83ca-a19f06ce687d
--   perfil    = EQUIPE | GERENTE | ANALISTA | LIDER | CO-LIDER | ADMIN
-- recebem SELECT nas tabelas do dashboard.
--
-- A role anon continua sem acesso aos dados.

DO $$
DECLARE
    tabela text;
    policy_name text := 'IBE leitura igreja autorizada';
BEGIN
    FOREACH tabela IN ARRAY ARRAY[
        'Contagens',
        'Cultos',
        'Registros',
        'Setores',
        'Igrejas',
        'ibe_contagens'
    ]
    LOOP
        IF to_regclass(format('public.%I', tabela)) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tabela);
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon', tabela);
            EXECUTE format('GRANT SELECT ON TABLE public.%I TO authenticated', tabela);
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', policy_name, tabela);
            EXECUTE format(
                'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated USING (
                    COALESCE(auth.jwt() -> ''app_metadata'' ->> ''igreja_id'', '''') = %L
                    AND upper(COALESCE(auth.jwt() -> ''app_metadata'' ->> ''perfil'', '''')) = ANY (%L::text[])
                )',
                policy_name,
                tabela,
                '34a358e0-eeb5-4975-83ca-a19f06ce687d',
                ARRAY['EQUIPE','GERENTE','ANALISTA','LIDER','CO-LIDER','ADMIN']::text[]
            );
        END IF;
    END LOOP;
END
$$ LANGUAGE plpgsql;

-- A view não é necessária para os principais gráficos no build atual.
-- Se existir, deixa anon sem acesso. A leitura do dashboard vem das tabelas com RLS.
DO $$
BEGIN
    IF to_regclass('public.vw_online_por_grupo_recepcao') IS NOT NULL THEN
        EXECUTE 'REVOKE ALL ON TABLE public.vw_online_por_grupo_recepcao FROM anon';
    END IF;
END
$$ LANGUAGE plpgsql;

-- Conferência rápida das policies criadas.
SELECT schemaname, tablename, policyname, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND policyname = 'IBE leitura igreja autorizada'
ORDER BY tablename;
