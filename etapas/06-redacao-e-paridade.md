# Etapa 6 — Redação e paridade

**Objetivo:** escrever a International Edition, depois a Edição em português, e provar que as duas são equivalentes.

## 6.1 International Edition (`relatorio-en.md`)

- Siga `modelos/relatorio-en.md` e o formato de item de `modelos/item-de-noticia.md`.
- Inglês profissional, sem simplificar demais. Use terminologia padrão: *monetary policy, fiscal policy, inflation expectations, interest rate differential, yield curve, Treasury yields, risk appetite, risk-off environment, capital flows, emerging markets, commodity prices, economic outlook, market sentiment, corporate earnings, GDP*.
- Use apenas itens confirmados na etapa 5, com os dados de `fontes.json`.
- Análise e perspectivas são marcadas como análise do briefing.
- A análise (seções 8 e 9) só usa fatos que aparecem nos itens do relatório; não introduza datas, números ou acontecimentos novos ali.
- Agenda do dia (seção 7): inclua todas as divulgações dos calendários previstas para o dia nas regiões cobertas e informe o consenso quando uma fonte aberta o trouxer; se não encontrar o consenso, escreva "n/a" e não "not checked". O **horário** nunca fica "n/a" se alguma fonte aberta o informar (ver etapa 3.4); ordene a tabela por horário.
- Resumo executivo (seção 1): cada tópico repete só o que o item correspondente diz, com a mesma atribuição. Não junte fatos de itens diferentes numa relação de causa que nenhum item afirma (etapa 5, regra 12), e não atribua a um documento oficial o que veio da imprensa (regra 11).
- Antes de gravar, releia cada frase que começa com "a ata", "o Fed", "o BC", "o comunicado" ou equivalente e confirme que o que vem depois está no documento oficial citado.

- Seção 5 (Mercados): abra com o bloco "Daily dashboard" do modelo, com até cinco linhas tiradas de "Largest 7-day moves" do painel do dia e o link para `painel/AAAA/MM/AAAA-MM-DD/painel-en.md`. Copie os números do painel sem arredondar de novo. Sem painel do dia, omita o bloco e registre no log.

## 6.2 Edição em português (`relatorio-pt.md`)

- Siga `modelos/relatorio-pt.md`.
- Mesmos itens, na mesma ordem, com os mesmos números, datas, fontes, links, análises e conclusões. Não omita detalhes.
- Títulos originais permanecem no idioma original; a tradução do título pode vir entre parênteses.
- Números no padrão brasileiro (vírgula decimal), sem mudar o valor.

## 6.3 English Learning Corner

- Cinco expressões financeiras ou econômicas usadas no relatório do dia.
- Antes de escolher, consulte `glossario/termos-financeiros.yaml` e evite expressões usadas nos últimos 20 dias úteis.
- Este é o único arquivo fora de `relatorios/` e `estado/` que a execução pode alterar: acrescente a data de uso (`usado_em`) às expressões escolhidas e inclua as novas com definição e tradução.

## 6.4 Checagem de paridade (`paridade.md`)

Compare as duas edições e grave:

```markdown
# Paridade EN/PT — AAAA-MM-DD HHhMM

Resultado: APROVADA | REPROVADA

| Verificação | EN | PT | Resultado |
| --- | --- | --- | --- |
| Itens de notícia | 28 | 28 | ok |
| Links (URLs únicas) | 31 | 31 | ok |
| Números citados | 64 | 64 | ok |
| Datas citadas | 22 | 22 | ok |
| Seções | 10 | 10 | ok |
| Expressões do English Learning Corner | 5 | 5 | ok |

## Divergências
- (nenhuma) ou lista de cada diferença encontrada e como foi corrigida.
```

Como comparar:

1. Extraia as URLs das duas edições: devem ser o mesmo conjunto.
2. Extraia os números (considerando a troca de ponto por vírgula decimal): devem ser o mesmo conjunto de valores.
3. Conte itens e seções.
4. Confira se cada conclusão da análise em inglês tem correspondente em português.

Se a paridade for reprovada, corrija a edição em português e repita a checagem (até 3 vezes). Se continuar reprovada, grave o relatório com "INCOMPLETO" no topo das duas edições e registre a causa no log.
