-- IBE / Streamlity - reativar leitura do dashboard para o usuario LOGADO
--
-- IMPORTANTE: este SQL substitui, para leitura, o bloqueio anterior que deixou
-- apenas service_role com SELECT. O navegador/Streamlit continua usando a chave
-- publica, mas as consultas carregam o JWT da conta autenticada.
--
-- Somente contas com app_metadata:
--   igreja_id = 34a358e0-eeb5-4975-83ca-a19f06ce687d
--   perfil = EQUIPE | GERENTE | ANALISTA | LIDER | CO-LIDER | ADMIN
-- recebem SELECT. anon continua sem acesso.

DO $$
DECLARE
    tabela text;
    policy_name text := 'IBE leitura autenticada da igreja';
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
                'CREATE POLICY %I ON public.%I
                 FOR SELECT TO authenticated
                 USING (
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

-- O build novo NAO depende desta view. Mantemos fechada para evitar uma rota
-- paralela que possa ignorar RLS dependendo de como a view foi criada.
DO $$
BEGIN
    IF to_regclass('public.vw_online_por_grupo_recepcao') IS NOT NULL THEN
        EXECUTE 'REVOKE ALL ON TABLE public.vw_online_por_grupo_recepcao FROM anon, authenticated';
    END IF;
END
$$ LANGUAGE plpgsql;

-- Conferencia das permissoes/policies.
SELECT schemaname, tablename, policyname, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND policyname = 'IBE leitura autenticada da igreja'
ORDER BY tablename;
