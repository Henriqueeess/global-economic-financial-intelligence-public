# Etapa 4 — Triagem

**Objetivo:** eliminar duplicatas, agrupar por evento e ordenar por relevância.

## Passos

1. **Normalize URLs:** minúsculas no domínio, sem `utm_*`, sem `#fragmento`, sem barra final.
2. **Duplicidade no dia:** candidatos com a mesma URL normalizada viram um só.
3. **Agrupamento por evento:** notícias sobre o mesmo fato (por exemplo, "decisão do BCE de hoje" em vários veículos) formam um evento. Dentro do evento, escolha a fonte principal pela hierarquia: comunicado oficial > agência > veículo de referência. As demais podem ser citadas como apoio.
4. **Duplicidade entre dias:** consulte `estado/urls-publicadas.csv`.
   - URL já publicada: descarte, **exceto** se houver fato novo; nesse caso, o item entra marcado "Em andamento / Ongoing" com a data original e o fato novo.
5. **Janela:** descarte publicações fora da janela, salvo temas em `estado/temas-em-andamento.md` com fato novo.
6. **Relevância:** pontue cada evento pelos critérios de `config/temas.yaml` (`relevancia.criterios`) multiplicados pelo `peso` do tema. Não há cota por país.
7. **Corte:** respeite `relatorio.limite_itens` de `config/parametros.yaml`. Leve à verificação até 1,5 vez o limite, para ter reserva em caso de descarte.

## Saída

Lista ordenada de eventos, cada um com fonte principal, fontes de apoio, seção do relatório e pontuação. Registre no log: candidatos recebidos, duplicatas removidas (no dia e entre dias), eventos formados, eventos levados à verificação.
