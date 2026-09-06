CORREÇÃO LIVE DATA / DASHBOARD
=============================

O que foi corrigido:
- o dashboard agora usa o JWT da própria conta que fez login para consultar o Supabase;
- não depende mais de SERVICE_ROLE para LEITURA do painel;
- anon continua sem acesso;
- RLS libera leitura só para a igreja 34a358e0-eeb5-4975-83ca-a19f06ce687d e perfis permitidos;
- Total on-line agora vem das mesmas linhas filtradas do gráfico (não fica 0 enquanto o gráfico tem valores);
- distribuição por setor é derivada das linhas do dashboard e respeita os filtros;
- a falha da consulta auxiliar de setores não gera mais o aviso amarelo;
- fallback XLSX continua existindo, mas agora aparece uma legenda avisando quando ele está sendo usado.

ANTES DE PUBLICAR:
1) Rode supabase/004_authenticated_church_access.sql no SQL Editor.
2) Publique este projeto.
3) Entre normalmente com a conta autorizada.

A SERVICE_ROLE continua necessária somente se você reativar rotinas administrativas/gravação.
