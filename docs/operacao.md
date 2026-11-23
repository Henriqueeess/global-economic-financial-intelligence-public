# Operação

## Ambiente do Claude

As execuções (manuais e agendadas) rodam no ambiente de nuvem **`global-economic-financial-intelligence`**, criado em 18/11/2026. Desde 18/11/2026 ele tem acesso total à rede, o que inclui as APIs oficiais gratuitas (BCB, IBGE, Fed, Tesouro dos EUA, BLS, BEA, FRED, BCE, Eurostat, Banco da Inglaterra, ONS, NBS da China e demais).

No ambiente padrão essas APIs são bloqueadas (teste de 18/11/2026). As threads do projeto no Claude usam o ambiente configurado em **Project settings → Cloud environment**; ele deve estar em `global-economic-financial-intelligence`. Uma thread já aberta não muda de ambiente. Para incluir um domínio novo, peça a mudança e aprove no Claude; não há custo.

## Execução manual (fase de validação)

Em uma sessão do Claude **no ambiente `global-economic-financial-intelligence`**, com este repositório conectado, peça:

> Execute o briefing seguindo o CLAUDE.md (execução manual).

O agente segue as sete etapas e grava a pasta `relatorios/AAAA/MM/AAAA-MM-DD_HHMM-manual/` na `main`.

### Critérios para validar cada execução manual

- [ ] Todos os links abrem e levam à publicação citada.
- [ ] Títulos, veículos e datas conferem com as páginas.
- [ ] Tipos de fonte estão corretos.
- [ ] Números conferem com a fonte primária.
- [ ] As duas edições são equivalentes (`paridade.md` aprovada e leitura humana).
- [ ] Cobertura equilibrada por relevância (Brasil, EUA, Europa, China, Japão, América Latina, geopolítica).
- [ ] Inglês profissional e português natural.
- [ ] Log completo, sem segredos.

Três execuções manuais foram aprovadas em 18/11/2026, e o agendamento foi ativado (Fase 2).

## Agendamento (Fase 2, ativo desde 18/11/2026)

- Tarefa agendada do Claude na nuvem, criando uma sessão nova a cada disparo no ambiente `global-economic-financial-intelligence`.
- Todos os dias, inclusive sábados e domingos, às 07h30 (America/Sao_Paulo). Decisão do responsável em 18/11/2026, substituindo o plano original de segunda a sexta.
- Expressão: `CRON_TZ=America/Sao_Paulo 30 7 * * *` (na plataforma: `30 10 * * *` em UTC, já que São Paulo não tem horário de verão).
- Cada disparo grava `relatorios/AAAA/MM/AAAA-MM-DD_HHMM/` na `main`, e o Apps Script do responsável envia a edição em português por e-mail no Gmail (ver "E-mail diário em HTML").
- Enquanto as chaves gratuitas (FRED, BEA, BLS, Banxico, BCentral Chile) não estiverem no ambiente, essas APIs são registradas como `api_falha` no log e os dados são buscados nas páginas oficiais.
- Sem conectores externos.
- O início pode atrasar alguns minutos em horários de pico da plataforma.

## Coleta de indicadores e painel (ativo desde a aprovação do PR)

- Workflow `.github/workflows/coleta-indicadores.yml`, todos os dias às 05h47 (08h47 UTC).
- Grava `dados/series/`, `dados/curva/` e o painel do dia em `painel/AAAA/MM/AAAA-MM-DD/`; o mais recente fica em [`painel/ultimo-pt.md`](../painel/ultimo-pt.md) e [`painel/ultimo-en.md`](../painel/ultimo-en.md).
- Para rodar à mão: **Actions → Coleta de indicadores → Run workflow** (marque "backfill" para rebuscar todo o histórico).
- Chaves gratuitas opcionais (FRED, BLS, Banxico, BC do Chile): **Settings → Secrets and variables → Actions → New repository secret**, com os nomes `FRED_API_KEY`, `BLS_API_KEY`, `BANXICO_TOKEN`, `BCENTRAL_USER` e `BCENTRAL_PASS`. Na coleta seguinte, os indicadores correspondentes saem de "Fora do painel hoje".

## Aviso por issue do GitHub (desligado em 23/11/2026)

Desligado a pedido do responsável em 23/11/2026: o briefing chega só pelo e-mail do Gmail (seção seguinte). O workflow continua no repositório, sem o gatilho por push, e só roda à mão. Para religar, devolver o bloco `push` em `on:` de `.github/workflows/aviso-relatorio.yml`. Registro de como funcionava:

Decisão de 18/11/2026: o aviso de cada relatório chega por e-mail via notificação do GitHub, sem senhas e sem dar ao agente capacidade de enviar e-mails.

- A automação `.github/workflows/aviso-relatorio.yml` roda no GitHub sempre que um relatório novo é gravado na `main` e abre uma issue "Relatório AAAA-MM-DD_HHMM" com a International Edition completa no corpo (formato de newsletter) e os links da edição em português, das fontes, da verificação e da paridade. Se a edição passar de 60.000 caracteres, o e-mail traz o início e o link para o restante.
- A issue é criada pelo `github-actions[bot]`, então o GitHub envia a notificação para quem acompanha o repositório.
- Usa só o `GITHUB_TOKEN` automático do GitHub. Consome minutos gratuitos do GitHub Actions (poucos segundos por relatório).

A issue é atribuída ao dono do repositório, o que garante o e-mail mesmo com o Watch em "Participating and @mentions". Para testar sem esperar um relatório: **Actions → Aviso de relatório novo → Run workflow**, informando a pasta de um relatório existente.

Configuração única, feita pelo responsável no GitHub:

1. **Settings → Emails:** adicionar e verificar o endereço que vai receber os avisos.
2. **Settings → Notifications → Default notifications email:** escolher esse endereço (ou, em **Custom routing**, apontar só este repositório para ele).
3. **Settings → Notifications:** em **Watching**, deixar **Email** marcado.
4. No repositório: **Watch → Custom → Issues → Apply**.

## E-mail diário em HTML (Gmail)

Decisão de 19/11/2026: a edição em português chega como e-mail formatado (resumo no topo, notícias em cartões, botão "Ler na fonte" em cada uma), enviado pelo mesmo Google Apps Script da cópia no Drive, até cerca de 15 minutos depois de o relatório ser gravado. O agente continua sem capacidade de enviar e-mails: quem envia é o script, na conta Google do responsável, sempre para o próprio responsável. Instalação: seção "E-mail diário" de [`integracoes/google-drive/README.md`](../integracoes/google-drive/README.md). É o único aviso por e-mail desde 23/11/2026, quando o aviso por issue do GitHub foi desligado.

## Cópia no Google Drive (NotebookLM)

Decisão de 18/11/2026: os relatórios também vão para a pasta **Briefing Econômico – NotebookLM** no Google Drive, por um Google Apps Script na conta Google do responsável, todos os dias entre 9h e 10h. Dois Google Docs fixos (PT e EN) reúnem os últimos 30 dias e são as fontes ligadas ao NotebookLM; cada relatório também fica na subpasta **Arquivo**. A execução das 07h30 não muda e continua sem conectores. Instalação e manutenção: [`integracoes/google-drive/README.md`](../integracoes/google-drive/README.md).

## Onde ler os relatórios

No GitHub: `relatorios/` → ano → mês → pasta da execução → `relatorio-en.md` ou `relatorio-pt.md`. O GitHub exibe o Markdown formatado no site e no app.

## Mudanças de configuração

Fontes, temas, parâmetros, instruções e modelos mudam apenas por pull request revisado pelo responsável do projeto.

## Cópia pública do código

Decisão de 19/11/2026: o código, as instruções do agente e a documentação ficam visíveis num repositório público separado; relatórios, estado, dados e painel ficam só aqui, que continua privado. Nada muda no briefing das 07h30, na coleta das 05h47, nem no Apps Script, porque todos continuam usando este repositório.

- Workflow `.github/workflows/espelho-publico.yml`: roda a cada mudança de código, instruções ou documentação na `main` (os relatórios e a coleta diária não o disparam) e pode ser rodado à mão em **Actions → Espelho público → Run workflow**.
- A lista do que vai para o público e as checagens estão em `scripts/espelho/montar.sh`. O `README.md` e a licença (MIT) da versão pública ficam em `publico/`.
- O público recebe commits do `github-actions[bot]`, sem o histórico daqui.

Configuração única, feita pelo responsável:

1. Criar no GitHub o repositório público **vazio** (sem README, licença ou `.gitignore`), por exemplo `global-economic-financial-intelligence-public`.
2. **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**: nome `espelho-publico`, **Only select repositories →** só o repositório público, **Contents: Read and write**, nenhuma outra permissão. Anote a data de expiração.
3. Neste repositório privado, **Settings → Secrets and variables → Actions**: em **Secrets**, criar `ESPELHO_TOKEN` com o token; em **Variables**, criar `ESPELHO_REPO` com `dono/nome` do público.
4. **Actions → Espelho público → Run workflow** e conferir o repositório público.

Sem o segredo e a variável, o workflow avisa e termina sem erro. Se o token expirar, o workflow falha ao clonar: gere outro e troque o segredo. **Não mude a visibilidade deste repositório**, nem para criar o público a partir dele (um fork ou cópia levaria o histórico com os relatórios).
