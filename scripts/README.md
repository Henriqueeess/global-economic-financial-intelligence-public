# Scripts

Coletores determinísticos das APIs oficiais e gerador do painel diário (Fase 3). Rodam no GitHub Actions
(`.github/workflows/coleta-indicadores.yml`), todos os dias às 05h47, antes do briefing.

| Arquivo | O que faz |
| --- | --- |
| `coletar_series.py` | Lê `config/indicadores.yaml`, chama as APIs e grava `dados/series/<id>.csv` e `dados/curva/tesouro_direto.csv` |
| `gerar_painel.py` | Gera `painel/AAAA/MM/AAAA-MM-DD/painel-pt.md` e `painel-en.md`, com gráficos SVG, e atualiza `painel/ultimo-*.md` |
| `indicadores/fontes.py` | Um coletor por API (BCB SGS e Focus, Tesouro dos EUA, BCE, Eurostat, BCRA, datos.gob.ar, FRED, BLS, Banxico, BC do Chile) |
| `indicadores/curva.py` | Curva de juros do Tesouro Direto e vértices de prazo constante |
| `gerar_dashboard.py` | Gera `painel/dashboard.html` (dashboard interativo da conjuntura, PT/EN) e `dados/conjuntura/*.csv` |
| `indicadores/derivados.py` | Diferencial de juros, inclinação da curva, inflação implícita e juro real ex-ante |
| `indicadores/conjuntura.py` | Termômetros (percentis desde 2016), índice de condições financeiras e contas mecânicas do IPCA, conforme `config/conjuntura.yaml` |
| `indicadores/projecoes.py` | Focus do ano corrente e dos dois seguintes, cenários pelo erro histórico do Focus e contas de mercado, conforme `config/projecoes.yaml` |
| `indicadores/dashboard_modelo.html` | Modelo do dashboard: página única, sem bibliotecas nem chamadas externas |
| `indicadores/painel.py` | Variações em 7 e 30 dias, extremos e destaques |
| `indicadores/svg.py` | Gráficos em SVG puro, com tema claro e escuro |

## Rodar localmente

```bash
pip install -r requirements.txt
python scripts/coletar_series.py --backfill   # primeira vez: histórico desde config/indicadores.yaml → backfill_desde
python scripts/coletar_series.py              # dia a dia: rebusca os últimos 45 dias para captar revisões
python scripts/gerar_painel.py                # painel de hoje (inclui a seção "Termômetros")
python scripts/gerar_dashboard.py             # dashboard da conjuntura, dados/conjuntura/ e dados/projecoes/
python -m pytest -q tests
```

## Formato dos dados

`dados/series/<id>.csv`: `data` (AAAA-MM-DD), `valor`, `fonte_url` (consulta pública, sem credenciais), `coletado_em`.
Séries mensais usam o primeiro dia do mês de referência. Datas posteriores ao dia da coleta são descartadas.

`dados/curva/tesouro_direto.csv`: `data_base`, `curva` (`prefixado` ou `ipca`), `vencimento`, `taxa_compra`, `taxa_venda` (% a.a.).

`dados/ultima-coleta.json`: resultado da última coleta por indicador (`ok`, `falha` ou `sem_chave`).

## Conjuntura (dados/conjuntura/)

Calculada só a partir de `dados/series/`, sem chamar APIs. Nada projeta câmbio, juros de mercado ou preço de ativos.

- `termometros.csv`: retrato do dia, um componente por linha, com o valor, o percentil no histórico desde 2016 e o percentil de um ano antes.
- `contas.csv`: histórico das contas que não existem em `dados/series/` (IPCA 3 meses anualizado, inclinação 5a − 1a).
- `condicoes_financeiras.csv`: índice semanal (0 a 100), média simples dos percentis de juro real ex-ante, IPCA+ 5 anos e prefixado 5 anos.
- `cenarios_ipca.csv`: trajetória do IPCA em 12 meses sob duas premissas fixas (repetir a média de 3 meses; rodar no centro da meta). É aritmética, não previsão.

Para o Power BI: **Obter dados → Texto/CSV** em cada arquivo (ou **Pasta** apontando para uma cópia local de `dados/series/`). Separador vírgula, decimal ponto, datas AAAA-MM-DD.

## Projeções (dados/projecoes/)

Calculadas só a partir de `dados/series/`, conforme `config/projecoes.yaml`. O projeto não emite previsão própria.

- `focus_cenarios.csv`: mediana do Focus para Selic, dólar, PIB e IPCA no ano corrente e nos dois seguintes, a revisão em 4 semanas e os cenários otimista e pessimista (mediana mais e menos o erro absoluto médio do próprio Focus no mesmo horizonte, desde 2016).
- `erro_historico_focus.csv`: cada ano usado no erro histórico, com o Focus no mesmo dia do ano, o realizado e o erro.
- `contas_mercado.csv`: Selic na curva (prefixado 1 ano contra a Selic efetiva), dólar a termo de 12 meses (paridade coberta de juros) e carregamento do IBC-Br. Aritmética com premissa declarada, não previsão.

## Adicionar um indicador

1. Acrescente uma entrada em `config/indicadores.yaml` (por pull request).
2. Se a API for nova, escreva um coletor em `indicadores/fontes.py` e registre-o em `COLETORES`.
3. Rode `coletar_series.py --ids <id>` para o histórico e `gerar_painel.py` para conferir.
