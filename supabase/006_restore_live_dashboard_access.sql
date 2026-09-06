-- IBE / Streamlity - restaurar leitura AO VIVO do dashboard para usuários autenticados
-- Rode uma vez no SQL Editor do Supabase.

GRANT USAGE ON SCHEMA public TO authenticated;

DO $$
DECLARE
    tabela text;
    policy_name text := 'IBE dashboard igreja autenticada';
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
                    auth.uid() IS NOT NULL
                    AND COALESCE(auth.jwt() -> ''app_metadata'' ->> ''igreja_id'', '''') = %L
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

SELECT schemaname, tablename, policyname, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND policyname = 'IBE dashboard igreja autenticada'
ORDER BY tablename;
