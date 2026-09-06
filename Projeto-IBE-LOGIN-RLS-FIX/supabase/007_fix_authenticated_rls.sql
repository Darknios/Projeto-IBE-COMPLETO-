-- IBE / Streamlity - FIX definitivo da leitura autenticada do dashboard
--
-- Motivo do bug:
-- as policies anteriores dependiam de app_metadata dentro do JWT. Em algumas
-- sessões o token autenticava o usuário, mas o PostgREST não enxergava os
-- metadados esperados e todas as tabelas retornavam vazias/bloqueadas.
--
-- Este script valida o usuário diretamente em auth.users pelo auth.uid(),
-- usando uma função SECURITY DEFINER. A chave service_role NÃO é necessária
-- no navegador nem para a leitura normal do dashboard.
--
-- Rode UMA VEZ no SQL Editor do Supabase.

BEGIN;

CREATE OR REPLACE FUNCTION public.ibe_dashboard_access_allowed()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, auth
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM auth.users AS u
        WHERE u.id = auth.uid()
          AND COALESCE(u.raw_app_meta_data ->> 'igreja_id', '') = '34a358e0-eeb5-4975-83ca-a19f06ce687d'
          AND upper(
                replace(
                    replace(COALESCE(u.raw_app_meta_data ->> 'perfil', ''), '_', '-'),
                    ' ', '-'
                )
              ) = ANY (ARRAY['EQUIPE','GERENTE','ANALISTA','LIDER','CO-LIDER','ADMIN']::text[])
    );
$$;

REVOKE ALL ON FUNCTION public.ibe_dashboard_access_allowed() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.ibe_dashboard_access_allowed() TO authenticated;
GRANT USAGE ON SCHEMA public TO authenticated;

DO $$
DECLARE
    tabela text;
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

            -- Remove somente as policies criadas pelas versões anteriores deste painel.
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', 'IBE leitura igreja autorizada', tabela);
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', 'IBE leitura autenticada da igreja', tabela);
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', 'IBE dashboard igreja autenticada', tabela);
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', 'IBE dashboard acesso validado', tabela);

            EXECUTE format(
                'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated USING (public.ibe_dashboard_access_allowed())',
                'IBE dashboard acesso validado',
                tabela
            );
        END IF;
    END LOOP;
END
$$ LANGUAGE plpgsql;

COMMIT;

-- Diagnóstico: deve retornar true quando executado pelo painel com a conta logada.
-- No SQL Editor, auth.uid() normalmente é NULL, então a função pode aparecer false.
SELECT schemaname, tablename, policyname, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND policyname = 'IBE dashboard acesso validado'
ORDER BY tablename;
