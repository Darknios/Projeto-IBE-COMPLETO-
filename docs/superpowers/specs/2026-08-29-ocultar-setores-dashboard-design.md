# Ocultar setores no gráfico do dashboard

## Objetivo

Remover apenas do gráfico **Distribuição de público por setor** as barras dos
setores Cadeiras, Congregação, Equipe e Palco.

## Escopo

- Aplicar o filtro exclusivamente aos dados enviados para esse gráfico em
  `IBE.py`.
- Manter os registros no banco de dados e todos os demais gráficos, métricas e
  formulários inalterados.
- Preservar o comportamento atual quando não houver setores restantes: exibir a
  mensagem informativa já usada pelo dashboard.

## Implementação proposta

Antes de criar o gráfico, derivar uma cópia filtrada da distribuição de setores
e excluir nomes normalizados correspondentes a `Cadeiras`, `Congregação`,
`Equipe` e `Palco`. Usar essa cópia tanto para decidir se há dados exibíveis
quanto para montar o gráfico Plotly.

## Validação

- Confirmar que os quatro setores não aparecem no gráfico.
- Confirmar que setores não filtrados continuam aparecendo com os mesmos
  valores.
- Executar uma verificação de sintaxe do arquivo Python.
