# Envio ao Google Drive (NotebookLM)

Decisão de 18/11/2026: cada relatório também vai para uma pasta do Google Drive, ligada como fonte no NotebookLM para o trabalho de storytelling.

## Como funciona

Um Google Apps Script, na conta Google do responsável, roda todos os dias entre 9h e 10h (America/Sao_Paulo), depois da execução das 07h30. Ele lê as duas edições no GitHub e grava na pasta **Briefing Econômico – NotebookLM**:

| Arquivo | O que é |
|---|---|
| `Briefing – últimos 30 dias (PT)` | Google Doc fixo, reescrito todo dia com os relatórios dos últimos 30 dias, do mais recente ao mais antigo. **Este é o que se liga ao NotebookLM.** |
| `Briefing – last 30 days (EN)` | O mesmo, com a International Edition. |
| `Arquivo/AAAA-MM-DD_HHMM – PT` e `– EN` | Uma cópia de cada relatório, criada uma vez e nunca alterada. |

Por que Docs fixos: o NotebookLM não acompanha pastas (ao escolher uma pasta, ele importa só os arquivos que já estão nela), mas um Google Doc ligado como fonte é sincronizado automaticamente. Reescrever sempre o mesmo Doc mantém o notebook atualizado sem nenhum passo diário.

## Por que este desenho é seguro

- **A execução das 07h30 continua sem conectores.** Ela lê páginas da internet; um texto malicioso numa notícia não tem como alcançar o Drive, porque essa sessão não tem acesso a ele.
- **O acesso ao Drive fica dentro do Google**, na sua conta, e com o escopo `drive.file`: o script só enxerga os arquivos e pastas que ele mesmo criou, e não vê o resto do seu Drive.
- **O único segredo é um token do GitHub somente leitura**, restrito a este repositório, guardado nas Propriedades do script e nunca no código nem no repositório.
- O script não executa nada do conteúdo dos relatórios e só acessa `api.github.com`, neste repositório.

## Instalação (uma vez, cerca de 10 minutos)

### 1. Token do GitHub somente leitura

1. GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. Nome: `drive-notebooklm`. Expiração: a maior disponível (anote a data para renovar).
3. **Repository access → Only select repositories →** `global-economic-financial-intelligence`.
4. **Permissions → Repository permissions → Contents: Read-only.** Nenhuma outra permissão.
5. Gere e copie o token (ele aparece uma vez só).

### 2. Projeto no Apps Script

1. Abra <https://script.google.com>, logado na conta Google do Drive, e clique em **Novo projeto**. Dê o nome `Briefing → Drive`.
2. **Configurações do projeto** (engrenagem): marque **Mostrar arquivo de manifesto "appsscript.json" no editor**.
3. No editor, substitua o conteúdo de `appsscript.json` pelo arquivo [`appsscript.json`](appsscript.json) desta pasta, e o de `Código.gs` pelo [`Codigo.gs`](Codigo.gs). Salve.
4. **Configurações do projeto → Propriedades do script → Adicionar propriedade:** nome `GITHUB_TOKEN`, valor = o token do passo 1. Salve.

### 3. Primeiro teste e gatilho diário

1. No editor, escolha a função `sincronizar` e clique em **Executar**. Autorize os acessos pedidos (Drive limitado aos arquivos do próprio script, serviço externo e gatilhos). Na conta pessoal, o Google mostra "app não verificado": clique em **Avançado → Acessar Briefing → Drive**, porque o app é seu.
2. Confira no Drive a pasta **Briefing Econômico – NotebookLM** com os dois Docs e a subpasta **Arquivo**.
3. Escolha a função `instalarGatilho` e clique em **Executar**. Isso cria o gatilho diário entre 9h e 10h.

### 4. Ligar ao NotebookLM

1. Abra o notebook em <https://notebooklm.google.com> (ou crie um).
2. **Adicionar fonte → Google Drive →** pasta **Briefing Econômico – NotebookLM**.
3. Selecione **Briefing – últimos 30 dias (PT)** e, se quiser, **Briefing – last 30 days (EN)**. Não é preciso adicionar os arquivos da subpasta Arquivo.
4. Pronto. Os dois Docs se atualizam sozinhos no notebook; se algum dia parecer desatualizado, abra a fonte e clique em **Sincronizar com o Google Drive**.

## E-mail diário em HTML (edição em português)

Decisão de 19/11/2026: o briefing chega também como e-mail formatado no Gmail, com a edição em português. O mesmo projeto do Apps Script envia o e-mail, usando o mesmo token somente leitura; nada muda na execução das 07h30.

**O que chega:** assunto com a data e a manchete principal; cabeçalho com o botão **Read in English** (página com troca de idioma, ver abaixo) e o link para a edição no GitHub; o resumo executivo em destaque no topo; a lista das seções; cada notícia num cartão com o tipo de fonte (etiqueta colorida), veículo, data, título original e o botão **Ler na fonte**; tabelas de mercados e agenda em linhas empilhadas, legíveis no celular; seções de análise marcadas como "análise do briefing"; no rodapé, os links para fontes, verificação, paridade e log.

**Quando chega:** um gatilho verifica o GitHub a cada 15 minutos, a partir das 7h. Quando aparece um relatório de hoje completo (com `paridade.md`), o e-mail sai uma vez só, em geral até uns 15 minutos depois da gravação. Execuções manuais do dia também são enviadas.

**Segurança:** o destinatário é sempre você (o dono da conta Google do script) ou o endereço que você puser na propriedade `EMAIL_DESTINO`. O texto do relatório é escapado antes de virar HTML, e só links `http(s)` viram links. O escopo novo é `script.send_mail`, que só envia e não lê sua caixa de entrada.

### Instalação (uma vez, cerca de 5 minutos, depois da instalação acima)

1. Abra o projeto **Briefing → Drive** em <https://script.google.com>.
2. Substitua o conteúdo de `appsscript.json` pelo arquivo [`appsscript.json`](appsscript.json) desta pasta (ele traz os dois escopos novos de e-mail). Salve.
3. Clique em **+ → Script**, dê o nome `Email` e cole o conteúdo de [`Email.gs`](Email.gs). Salve.
4. Escolha a função `enviarUltimoAgora` e clique em **Executar**. O Google pede de novo a autorização, agora com "Enviar e-mail como você": aceite (**Avançado → Acessar Briefing → Drive**). Confira o e-mail no Gmail.
5. Escolha a função `instalarGatilhoEmail` e clique em **Executar**. Isso cria o gatilho de 15 em 15 minutos.
6. Opcional: para receber em outro endereço, crie em **Propriedades do script** a propriedade `EMAIL_DESTINO` com esse endereço.

### Página com o botão PT/EN (cerca de 2 minutos)

O Gmail não permite botões interativos dentro do e-mail. Por isso o botão **🇬🇧 Read in English** do e-mail abre uma página do próprio script, com o mesmo visual e o botão **🇧🇷 Ler em português** para voltar. Sem esta etapa, o botão abre a edição em inglês no GitHub.

1. No editor do Apps Script: **Implantar → Nova implantação → engrenagem → App da Web**.
2. Descrição: `Briefing PT/EN`. **Executar como: Eu. Quem pode acessar: Somente eu.** Clique em **Implantar** e autorize se for pedido.
3. Copie o **URL do app da Web** (termina em `/exec`) e crie em **Propriedades do script** a propriedade `URL_PAGINA` com esse endereço.
4. Rode `enviarUltimoAgora` de novo e toque em **Read in English** no e-mail para conferir.

A página só abre logado na sua conta Google. Se o navegador tiver várias contas Google abertas e aparecer erro, abra o link numa janela anônima ou saia das outras contas. Quando o `Email.gs` mudar, atualize a página em **Implantar → Gerenciar implantações → editar → Versão: nova versão**, sem trocar o endereço.

Para parar o e-mail: **Acionadores** → apagar o gatilho `verificarEEnviar`.

## Manutenção

- **Token expirado:** o script falha e o Google envia e-mail de erro do gatilho. Gere um token novo (passo 1) e troque o valor de `GITHUB_TOKEN`.
- **Mudar a janela de 30 dias ou o horário:** altere `DIAS` em `Codigo.gs` ou a hora em `instalarGatilho` (e rode `instalarGatilho` de novo), por pull request neste repositório e depois no editor do Apps Script.
- **Desligar:** no Apps Script, **Acionadores** → apagar o gatilho; no GitHub, revogar o token.
