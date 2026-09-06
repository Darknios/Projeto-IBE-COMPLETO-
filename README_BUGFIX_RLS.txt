BUGFIX RLS / LEITURA AO VIVO
============================

1. Rode supabase/007_fix_authenticated_rls.sql no SQL Editor do Supabase.
2. Feche a sessão do painel e entre novamente.
3. O dashboard continua sem fallback XLSX/local.
4. Login continua obrigatório e limitado à igreja configurada + perfis permitidos.
5. Se SUPABASE_SERVICE_ROLE_KEY já existir nos Secrets do servidor, o app também
   possui um fallback backend para não derrubar o painel; a chave não vai ao navegador.
