# Etapa 2 — Orquestração

**Objetivo:** abrir a execução, definir a janela de tempo e criar a pasta e o log sem sobrescrever nada.

## Passos

1. Obtenha o horário de início no fuso `America/Sao_Paulo`:
   `TZ=America/Sao_Paulo date '+%Y-%m-%dT%H:%M:%S%:z'`
2. Defina o tipo de execução:
   - `agendada`, se iniciada pelo agendamento;
   - `manual`, em qualquer outro caso (as pastas levam o sufixo `-manual`).
3. Monte o nome da pasta conforme `saida.padrao_pasta`:
   `relatorios/AAAA/MM/AAAA-MM-DD_HHMM[-manual]`
4. **Nunca sobrescrever:** se a pasta já existir, acrescente `-2`, `-3`, e assim por diante, até encontrar um nome livre.
5. Crie a pasta e o arquivo `execucao.log`.
6. Defina a janela de notícias: de (início − 24 h) até o início. Registre os dois limites no log.

## Formato do log (`execucao.log`)

Uma linha por evento, com campos separados por ` | `:

```
2026-11-19T07:30:04-03:00 | 02-orquestracao | inicio | execucao=manual pasta=relatorios/2026/11/2026-11-19_0730-manual
2026-11-19T07:30:05-03:00 | 02-orquestracao | janela | de=2026-11-18T07:30-03:00 ate=2026-11-19T07:30-03:00
2026-11-19T07:31:10-03:00 | 03-coleta | api_ok | fonte=BCB-SGS serie=432
2026-11-19T07:31:12-03:00 | 03-coleta | api_falha | fonte=FRED motivo=sem_chave
```

**Grave o log em tempo real.** Cada linha é acrescentada no momento em que o evento acontece, com o horário obtido na hora (`TZ=America/Sao_Paulo date '+%Y-%m-%dT%H:%M:%S%:z'`), por exemplo:

```bash
log() { printf '%s | %s\n' "$(TZ=America/Sao_Paulo date '+%Y-%m-%dT%H:%M:%S%:z')" "$*" >> "$PASTA/execucao.log"; }
log "03-coleta | api_ok | fonte=BCB-SGS serie=432 http=200"
```

Nunca escreva o log de uma vez no fim, nem copie o mesmo horário para várias linhas: o log serve para auditar a ordem e a duração das etapas. Contagens (buscas, páginas abertas, candidatos) são contadas a partir das linhas do próprio log, não estimadas. Antes do evento `fim`, confira que a soma de `consultas` nas linhas `cobertura` é igual ao número de linhas `busca`, e registre `log_conferido buscas=<n> linhas=<n>`; se não bater, corrija a linha `cobertura` e anote a correção.

Eventos mínimos: `inicio`, `janela`, um evento por fonte consultada (`ok` ou `falha` com motivo), um evento `busca` por consulta de busca, totais de cada etapa, `paridade`, `checagem_segredos`, `commit`, `push`, `fim`. Nunca registre valores de chaves ou tokens.

## Saída

Pasta da execução criada, log iniciado, janela definida.
