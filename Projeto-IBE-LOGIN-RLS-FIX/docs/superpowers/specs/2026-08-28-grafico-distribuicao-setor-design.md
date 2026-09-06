# Gráfico de distribuição de pessoas por setor

## Objetivo

Alterar o gráfico **Distribuição de pessoas por setor** para usar a tabela `Contagens` como fonte de dados, lendo as colunas `NomeSetor` e `Quantidade`.

## Fluxo de dados

1. Carregar as tabelas `Registros` e `Contagens` necessárias ao gráfico.
2. Relacionar cada linha de `Contagens` ao seu registro por `Contagens.RegistroId = Registros.Id`.
3. Converter `Quantidade` para valor numérico, tratando valores ausentes como zero.
4. Agrupar os registros unidos por `NomeSetor` e somar `Quantidade`.
5. Exibir o gráfico de barras com o nome do setor no eixo X e a soma no eixo Y.

## Comportamento

- O gráfico deixa de depender do conjunto fixo de colunas por setor atualmente presente no dataframe do dashboard.
- A consulta deve aproveitar os filtros de período já aplicados pela tela quando a tabela disponibilizar data ou vínculo de data compatível.
- Setores sem nome ou com quantidade inválida não devem interromper a renderização; valores inválidos serão normalizados e nomes ausentes poderão ser exibidos como `Não informado`.
- Se não houver dados, a interface deve manter um estado informativo em vez de apresentar erro.
- A leitura deve tentar todas as credenciais de consulta disponíveis. Um resultado vazio obtido com uma credencial não encerra as tentativas, pois pode ser causado por uma política RLS.
- Se todas as credenciais falharem, a interface deve informar que os dados de setores não puderam ser consultados; essa condição não deve ser apresentada como quantidade zero.
- A união não substitui a permissão de leitura: as tabelas envolvidas precisam estar acessíveis à credencial usada pelo Streamlit.
- A migração de acesso de `Contagens` deve conceder apenas `SELECT` a `anon`, `authenticated` e `service_role`; a política RLS deve permitir somente leitura e ser idempotente.
- Os KPIs `Total on-line` e `Total visitantes` devem usar a soma de `Quantidade` do resultado unido, filtrada respectivamente pelos valores normalizados de `NomeSetor` para on-line e visitantes.
- O gráfico `Pessoas on-line por domingo` deve consultar uma view SQL que une `Registros.Id` a `Contagens.RegistroId`, filtra os setores on-line e soma `Quantidade` por `Registros.GrupoRecepcao`.

## Verificação

- Confirmar que as barras e rótulos correspondem às somas por `NomeSetor`.
- Confirmar que não há referência ao mapeamento estático de setores no gráfico alterado.
- Confirmar que uma consulta vazia com uma credencial permite tentar a próxima credencial configurada.
- Confirmar que somente contagens cujo `RegistroId` corresponde a `Registros.Id` entram na agregação.
- Confirmar que a migração não concede `INSERT`, `UPDATE` ou `DELETE` às roles públicas.
- Confirmar que os KPIs reconhecem as variações de escrita `Online`/`On-line` e `Visitante`/`Visitantes`.
- Confirmar que a view retorna uma linha por grupo de recepção e que o gráfico usa a coluna agregada dessa view.
- Executar a verificação disponível do projeto e validar a sintaxe do módulo alterado.
