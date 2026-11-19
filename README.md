# Global Economic & Financial Intelligence

Agente que pesquisa, verifica e redige um briefing econômico e financeiro diário bilíngue (inglês e português), com cada notícia rastreável até a fonte original, e um painel de cerca de 30 indicadores oficiais (Selic, câmbio, Focus, curva do Tesouro Direto, Treasuries, BCE, Eurostat, Argentina).

*An agent that researches, verifies and writes a daily bilingual (English and Portuguese) economic and financial briefing, with every item traceable to its original source, plus a dashboard of about 30 official indicators. The instructions and documentation are in Portuguese.*

## O que está aqui

Este repositório é a **cópia pública** do projeto: código, instruções do agente e documentação. Ele é atualizado automaticamente a partir do repositório de operação, que é privado.

```
├── CLAUDE.md               regras permanentes do agente
├── etapas/                 instruções de cada uma das sete etapas
├── config/                 fontes, temas, agenda, parâmetros e indicadores
├── modelos/                modelos das duas edições e do item de notícia
├── glossario/              termos do English Learning Corner
├── scripts/                coleta das APIs oficiais e geração do painel
├── tests/                  testes dos scripts
├── integracoes/            Google Apps Script (cópia no Drive e e-mail em HTML)
├── docs/                   arquitetura, segurança, fontes e operação
└── referencia/workflows/   workflows do GitHub Actions usados na operação
```

## O que não está aqui

Os relatórios diários, o estado do agente, as séries coletadas e o painel **não são publicados**. Os relatórios resumem reportagens de veículos de terceiros, e os direitos sobre esse conteúdo são deles. Por isso as referências a `relatorios/`, `estado/`, `dados/` e `painel/` na documentação apontam para pastas que só existem no repositório privado.

Os workflows ficam em `referencia/workflows/` para leitura: fora de `.github/workflows/`, o GitHub não os executa.

## Usar no seu próprio repositório

1. Copie este repositório para um repositório **privado** seu.
2. Mova `referencia/workflows/*.yml` para `.github/workflows/` (o `espelho-publico.yml` só é útil se você também quiser uma cópia pública).
3. Ajuste `config/` e as referências ao nome do repositório em `integracoes/google-drive/Codigo.gs`.
4. Siga `docs/operacao.md` para a execução manual, o agendamento e os avisos.

Tudo usa apenas fontes gratuitas: APIs oficiais, RSS e busca.

## Licença

[MIT](LICENSE).
