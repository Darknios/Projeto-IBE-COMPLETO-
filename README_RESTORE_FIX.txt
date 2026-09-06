FIX solicitado

1. Campo de senha: corrigida a borda dupla/caixa extra do botão de visualizar.
2. Visitantes: usa somente Contagens.NomeSetor = Visitantes (comparação normalizada exata) e soma Contagens.Quantidade.
3. Removido o aviso e o fallback de histórico local. O painel agora exige dados ao vivo.
4. Renove, Quarta-feira e Cafofo: leitura ao vivo restaurada com JWT enviado diretamente ao PostgREST e classificação por nome do culto/data.

Se o Supabase ainda bloquear SELECT para authenticated, execute supabase/006_restore_live_dashboard_access.sql uma vez.
