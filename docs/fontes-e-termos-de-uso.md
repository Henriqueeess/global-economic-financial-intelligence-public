# Fontes e termos de uso

## Princípios

1. **Apenas fontes gratuitas** nesta fase: APIs públicas, RSS e mecanismos de busca. Qualquer serviço pago depende de aprovação do responsável do projeto.
2. **Respeito a paywalls e bloqueios:** não contornar paywall, login, `robots.txt` ou limites de acesso. Quando o texto não está acessível, usar só título e resumo públicos e confirmar fatos em fonte aberta.
3. **Direitos autorais:** os relatórios trazem títulos originais, links e resumos escritos pelo briefing. Citações literais são raras, curtas, entre aspas e com atribuição. Nenhum texto integral é arquivado.
4. **Atribuição:** cada item cita veículo, data e link da publicação original. Agregadores e reproduções não são citados como fonte.
5. **Uso moderado:** poucas requisições por fonte por execução, com tempo limite, para não sobrecarregar sites e APIs.

## Hierarquia de fontes

1. Comunicado oficial (banco central, órgão de estatística, governo, empresa)
2. Agência de notícias (Reuters, AP, Bloomberg)
3. Veículo de referência (FT, WSJ, Valor, Estadão etc.)
4. Análise (opinião, colunas, sínteses)

## Limitações conhecidas (teste de 18/11/2026)

- Bloomberg recusou leitura automática.
- Páginas de CNBC, US News, Quartz e Sharecast retornaram erro em pelo menos uma tentativa.
- Uma página ao vivo exibiu números de horários diferentes na mesma tela: cotações sempre com horário.

O status de cada fonte é mantido em `config/fontes.yaml` e atualizado por pull request depois das execuções de teste.

## Lições da execução manual 1 (18/11/2026)

Revisão humana e do agente apontou e virou regra:

| Problema observado | Regra adotada |
| --- | --- |
| Inflação final da zona do euro, divulgada no dia, não entrou | Etapa 3.3.2: divulgações oficiais do dia são buscadas primeiro |
| Nenhuma fonte em espanhol; América Latina, China e Japão sem itens | Etapa 3.3.1: busca mínima por região e aviso explícito quando não houver item |
| Matérias de agências citadas por sites parceiros | Etapa 5, regra 9: tentar o link original primeiro |
| Dado de ouro tirado de site de análise de trading | Etapa 5, regra 10 e `fontes_de_baixa_prioridade` |
| Detalhe sem fonte ("CEO change last week") na análise | Etapa 5, regra 13 e etapa 6.1 |
| Agenda sem dados de construção dos EUA e sem consenso | Etapa 6.1: agenda completa e "n/a" quando não houver consenso |
| APIs oficiais bloqueadas | Rodar no ambiente `global-economic-financial-intelligence` (ver `docs/operacao.md`) |

## Lições da auditoria de 19/11/2026

A auditoria do briefing agendado de 19/11 (nota 8/10) apontou e virou regra:

| Problema observado | Regra adotada |
| --- | --- |
| Ata do Fed com "dois cogitaram meio ponto" e taxa de "3,9%", que eram a leitura da AP; a ata diz "a couple of participants", "more than 25 basis points", e a faixa é 3,75% a 4% | Etapa 5, regra 11: citar o texto do documento oficial (ata `fomcminutes`) e separar o que é do Fed do que é leitura da imprensa; regra 6: juros como a instituição divulga |
| Resumo executivo disse que a queda do cobre "levou" o dólar no Chile a 1.007, ligação que a fonte não faz (e o 1.007 era de outro dia) | Etapa 5, regras 6 e 12: causa só com fonte, cada número com a sua data; etapa 6.1: resumo executivo sem ligações novas |
| Argentina: média de 1.583,38 sem dizer que excluía o Banco Nación; negócios pontuais a 1.560 descritos como nível do atacado | Etapa 5, regra 6: dizer exatamente o que o número é |
| Pedidos de seguro-desemprego dos EUA sem horário na agenda (é 10h30) | Etapa 3.4 e 6.1: todo evento tem horário, buscado no calendário oficial se faltar |
| Log com o mesmo horário em todas as linhas e contagem de buscas que não batia | Etapa 2: log gravado em tempo real, uma linha `busca` por consulta, contagens conferidas antes do `fim`; etapa 3.3 |
| Painel ausente porque a coleta das 06h47 não rodou | Coleta antecipada para 05h47; etapa 3.1: esperar e checar o painel de novo até 3 vezes antes de seguir sem ele |
