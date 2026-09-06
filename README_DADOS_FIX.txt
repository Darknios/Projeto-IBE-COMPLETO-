FIX solicitado - login + Visitantes + On-line
===============================================

1. LOGIN
- texto digitado nos inputs agora fica BRANCO;
- fundo do input passou a ser azul-marinho, para o branco continuar legivel;
- placeholder continua em cinza/azul claro.

2. TOTAL DE VISITANTES
- fonte de verdade: public."Contagens";
- usa NomeSetor = Visitante/Visitantes (comparacao exata apos normalizar caixa/acentos);
- soma a coluna Quantidade;
- cada linha e vinculada ao respectivo RegistroId, entao o total respeita culto/data/grupo/filtros.
- nomes como "Visitantes VIP" NAO entram no total.

3. TOTAL ON-LINE
- tambem e lido das linhas de public."Contagens" ligadas por RegistroId;
- reconhece Online / On-line / Online Culto;
- o card Total on-line agora aparece em TODAS as abas (Domingo, Renove, Quarta e Cafofo).

4. DADOS QUE TINHAM SUMIDO
- o dashboard usa o access_token da conta que acabou de fazer login;
- nao depende de service_role para leitura;
- o aviso amarelo da consulta auxiliar de setores nao derruba mais a tela.

PASSO OBRIGATORIO NO SUPABASE
-----------------------------
Se voce rodou o SQL antigo que revogava SELECT de authenticated, rode agora:

  supabase/005_authenticated_dashboard_read.sql

Depois faca logout/login de novo para obter um JWT novo e atualize a pagina.
