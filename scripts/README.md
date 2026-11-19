# Scripts

Coletores determinísticos das APIs oficiais e gerador do painel diário (Fase 3). Rodam no GitHub Actions
(`.github/workflows/coleta-indicadores.yml`), todos os dias às 05h47, antes do briefing.

| Arquivo | O que faz |
| --- | --- |
| `coletar_series.py` | Lê `config/indicadores.yaml`, chama as APIs e grava `dados/series/<id>.csv` e `dados/curva/tesouro_direto.csv` |
| `gerar_painel.py` | Gera `painel/AAAA/MM/AAAA-MM-DD/painel-pt.md` e `painel-en.md`, com gráficos SVG, e atualiza `painel/ultimo-*.md` |
| `indicadores/fontes.py` | Um coletor por API (BCB SGS e Focus, Tesouro dos EUA, BCE, Eurostat, BCRA, datos.gob.ar, FRED, BLS, Banxico, BC do Chile) |
| `indicadores/curva.py` | Curva de juros do Tesouro Direto e vértices de prazo constante |
| `indicadores/derivados.py` | Diferencial de juros, inclinação da curva e inflação implícita |
| `indicadores/painel.py` | Variações em 7 e 30 dias, extremos e destaques |
| `indicadores/svg.py` | Gráficos em SVG puro, com tema claro e escuro |

## Rodar localmente

```bash
pip install -r requirements.txt
python scripts/coletar_series.py --backfill   # primeira vez: histórico desde config/indicadores.yaml → backfill_desde
python scripts/coletar_series.py              # dia a dia: rebusca os últimos 45 dias para captar revisões
python scripts/gerar_painel.py                # painel de hoje
python -m pytest -q tests
```

## Formato dos dados

`dados/series/<id>.csv`: `data` (AAAA-MM-DD), `valor`, `fonte_url` (consulta pública, sem credenciais), `coletado_em`.
Séries mensais usam o primeiro dia do mês de referência. Datas posteriores ao dia da coleta são descartadas.

`dados/curva/tesouro_direto.csv`: `data_base`, `curva` (`prefixado` ou `ipca`), `vencimento`, `taxa_compra`, `taxa_venda` (% a.a.).

`dados/ultima-coleta.json`: resultado da última coleta por indicador (`ok`, `falha` ou `sem_chave`).

## Adicionar um indicador

1. Acrescente uma entrada em `config/indicadores.yaml` (por pull request).
2. Se a API for nova, escreva um coletor em `indicadores/fontes.py` e registre-o em `COLETORES`.
3. Rode `coletar_series.py --ids <id>` para o histórico e `gerar_painel.py` para conferir.
