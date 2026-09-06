# Corrigir gráfico de público on-line por domingo

## Objetivo

Exibir, no gráfico **Quantidade de público on-line por domingo**, as contagens
reais dos setores `Online` e `Online Culto`, agrupadas por grupo de recepção.

## Fonte de dados

Reaproveitar `get_online_by_reception`, que consulta a view
`vw_online_por_grupo_recepcao`. A view relaciona `Registros.Id` com
`Contagens.RegistroId`, filtra os setores on-line e soma `Contagens.Quantidade`
por `Registros.GrupoRecepcao`.

## Escopo

- Importar a função no dashboard e usá-la somente no gráfico on-line por
  domingo.
- Manter o eixo X com os grupos de recepção (1º Domingo a 5º Domingo).
- Preservar totais e demais gráficos.
- Quando não houver dados on-line ou ocorrer falha de leitura, não exibir barras
  zeradas; mostrar uma mensagem informativa ou de aviso.

## Validação

- Confirmar que o gráfico recebe valores agregados dos setores on-line.
- Confirmar que grupos sem registros não resultam em barras artificiais com
  valor zero.
- Verificar a sintaxe do código Python quando houver interpretador disponível.
