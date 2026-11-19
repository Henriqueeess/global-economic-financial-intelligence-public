# Arquitetura

Arquitetura aprovada em 18/11/2026: um pipeline de sete etapas executado por um agente (Claude), guiado por arquivos de configuração versionados neste repositório.

```
Gatilho agendado (todos os dias, 07h30 America/Sao_Paulo) ──► 1. Configuração (este repositório)
                                                            │
                                                            ▼
                                              2. Orquestração (pasta + log + janela)
                                                            │
                                                            ▼
                     3. Coleta: APIs oficiais · RSS · busca na web · calendários
                                                            │
                                                            ▼
                                  4. Triagem (duplicidade, eventos, relevância)
                                                            │
                                                            ▼
                                  5. Verificação (cada página aberta e conferida)
                                                            │
                                                            ▼
                     6. Redação EN ──► Edição PT ──► Paridade ok? ──não──► corrige PT
                                                            │ sim
                                                            ▼
                     7. Entrega e arquivo (Markdown no GitHub, commit e push)
```

## Painel diário de indicadores (aprovado em 18/11/2026)

```
05h47  GitHub Actions: coleta-indicadores.yml
       scripts/coletar_series.py ──► dados/series/*.csv  (APIs oficiais, 10 anos de histórico)
                                 ──► dados/curva/tesouro_direto.csv
       scripts/gerar_painel.py   ──► painel/AAAA/MM/AAAA-MM-DD/painel-pt.md e painel-en.md
07h30  Agente do briefing: lê o painel do dia (etapa 3) e abre a seção 5 com os destaques (etapa 6)
```

- A coleta de números é feita por código determinístico, sem IA, e roda mesmo que o briefing falhe.
- Catálogo em `config/indicadores.yaml`; cada linha dos CSV guarda a URL da API de origem.
- Só dados oficiais abertos são gravados no repositório (BCB, Tesouro, BCE, Eurostat, Tesouro dos EUA, BCRA, INDEC e, com chave gratuita, FRED, BLS, Banxico e BC do Chile). Bolsas ficam fora: os planos gratuitos das APIs de mercado costumam proibir a redistribuição dos dados.
- Curva de juros brasileira a partir das taxas do Tesouro Direto (títulos sem cupom), com vértices de prazo constante interpolados e inflação implícita.
- Proposta completa: documento "Proposta — Painel diário de indicadores" no projeto do Claude.

## Decisões

| Tema | Decisão |
| --- | --- |
| Repositório | GitHub privado, fonte oficial de configuração e histórico |
| Entrega | Arquivos Markdown no repositório, em ordem cronológica; aviso por e-mail via issue do GitHub (resumo e links) |
| Agendamento | Todos os dias, 07h30, America/Sao_Paulo (ativo desde 18/11/2026, após 3 execuções manuais validadas) |
| Idioma | Instruções e documentação em português; relatórios em inglês e português |
| Fontes | Apenas gratuitas: APIs públicas, RSS e busca |
| Mudanças de configuração | Somente por pull request revisado |
| Painel de indicadores | Diário, janelas de 7 e 30 dias, Markdown com gráficos SVG em PT e EN; GitHub Pages quando o repositório ficar público |
| Base histórica | CSV em `dados/`, desde jan/2016, gravados pelo GitHub Actions |

## Fases

1. **Fase 1 — estrutura:** este repositório, CLAUDE.md, configurações, etapas, modelos; três execuções manuais de validação.
2. **Fase 2 — piloto agendado:** ativação do agendamento e revisão diária por amostragem por duas semanas.
3. **Fase 3 — dados estruturados:** scripts de coleta das APIs oficiais e painel diário de indicadores (iniciada em 18/11/2026).
4. **Fase 4 — plataforma:** histórico pesquisável, alertas e painéis.

Proposta completa: documento "Proposta de arquitetura — Global Economic & Financial Intelligence" no projeto do Claude.
