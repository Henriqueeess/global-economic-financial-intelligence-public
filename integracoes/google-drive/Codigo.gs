/**
 * Envio dos relatórios ao Google Drive, para uso como fonte no NotebookLM.
 *
 * Roda na conta Google do responsável (Google Apps Script), uma vez por dia.
 * Lê as duas edições de cada relatório no GitHub (somente leitura) e grava no Drive:
 *   - dois Google Docs fixos, reescritos a cada execução, com os relatórios dos
 *     últimos DIAS dias (um em português, outro em inglês). São esses que se ligam
 *     ao NotebookLM, porque um Doc ligado como fonte se atualiza sozinho;
 *   - uma cópia de cada relatório na subpasta "Arquivo".
 *
 * Segurança:
 *   - Escopo drive.file: o script só enxerga os arquivos que ele mesmo criou.
 *   - O único segredo é um token do GitHub somente leitura, guardado em
 *     Propriedades do script (GITHUB_TOKEN). Nunca coloque o token neste arquivo.
 *   - O conteúdo dos relatórios é tratado como texto: nada nele é executado.
 *   - Só acessa api.github.com, no repositório fixo abaixo.
 *
 * Passo a passo de instalação: integracoes/google-drive/README.md
 */

const REPO = 'Henriqueeess/global-economic-financial-intelligence';
const RAMO = 'main';
const DIAS = 30;
const NOME_PASTA = 'Briefing Econômico – NotebookLM';
const NOME_ARQUIVO = 'Arquivo';
const LIMITE_CARACTERES = 900000; // margem abaixo do limite de uma fonte do NotebookLM
const EDICOES = [
  { arquivo: 'relatorio-pt.md', sufixo: 'PT', titulo: 'Briefing – últimos 30 dias (PT)' },
  { arquivo: 'relatorio-en.md', sufixo: 'EN', titulo: 'Briefing – last 30 days (EN)' },
];
const PADRAO_PASTA = /^\d{4}-\d{2}-\d{2}_\d{4}(-manual)?(-\d+)?$/;
const MIME_DOC = 'application/vnd.google-apps.document';
const MIME_PASTA = 'application/vnd.google-apps.folder';

/** Executado pelo gatilho diário. Também pode ser rodado à mão para testar. */
function sincronizar() {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('Falta a propriedade GITHUB_TOKEN (Configurações do projeto → Propriedades do script).');

  const pastaId = garantirPasta_(props, 'PASTA_ID', NOME_PASTA, null);
  const arquivoId = garantirPasta_(props, 'ARQUIVO_ID', NOME_ARQUIVO, pastaId);

  const execucoes = listarExecucoes_(token); // mais recente primeiro
  console.log('Execuções na janela: ' + execucoes.length);

  EDICOES.forEach(function (ed) {
    const partes = [];
    let total = 0;
    execucoes.forEach(function (ex) {
      const md = baixarTexto_(token, ex.caminho + '/' + ed.arquivo);
      if (md === null) return; // edição ausente nesta execução
      arquivarSeNovo_(arquivoId, ex.nome + ' – ' + ed.sufixo, md);
      if (total + md.length > LIMITE_CARACTERES) return;
      partes.push('<!-- execução ' + ex.nome + ' -->\n\n' + md);
      total += md.length;
    });
    const cabecalho = '# ' + ed.titulo + '\n\nAtualizado em ' +
      Utilities.formatDate(new Date(), 'America/Sao_Paulo', 'dd/MM/yyyy HH:mm') +
      ' (America/Sao_Paulo). Relatórios do mais recente para o mais antigo.\n\n';
    const conteudo = cabecalho + (partes.length ? partes.join('\n\n---\n\n') : 'Nenhum relatório na janela.');
    gravarDocFixo_(props, 'DOC_' + ed.sufixo, ed.titulo, pastaId, conteudo);
  });
}

/** Rode uma vez para criar o gatilho diário das 9h (horário de Brasília). */
function instalarGatilho() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'sincronizar') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('sincronizar').timeBased().everyDays(1).atHour(9).create();
  console.log('Gatilho diário criado: sincronizar, entre 9h e 10h.');
}

// ---------- GitHub (somente leitura) ----------

function chamarGitHub_(token, caminho, bruto) {
  const url = 'https://api.github.com/repos/' + REPO + '/contents/' +
    caminho.split('/').map(encodeURIComponent).join('/') + '?ref=' + RAMO;
  const resp = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: bruto ? 'application/vnd.github.raw' : 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
    },
    muteHttpExceptions: true,
    followRedirects: false,
  });
  const codigo = resp.getResponseCode();
  if (codigo === 404) return null;
  if (codigo !== 200) throw new Error('GitHub respondeu ' + codigo + ' para ' + caminho);
  return resp.getContentText('UTF-8');
}

function baixarTexto_(token, caminho) {
  return chamarGitHub_(token, caminho, true);
}

/** Pastas de execução dos últimos DIAS dias, da mais recente para a mais antiga. */
function listarExecucoes_(token) {
  const hoje = new Date();
  const limite = Utilities.formatDate(new Date(hoje.getTime() - DIAS * 86400000), 'America/Sao_Paulo', 'yyyy-MM-dd');
  const meses = {};
  for (let d = 0; d <= DIAS + 1; d++) {
    meses[Utilities.formatDate(new Date(hoje.getTime() - d * 86400000), 'America/Sao_Paulo', 'yyyy/MM')] = true;
  }
  const lista = [];
  Object.keys(meses).forEach(function (mes) {
    const json = chamarGitHub_(token, 'relatorios/' + mes, false);
    if (json === null) return;
    JSON.parse(json).forEach(function (item) {
      if (item.type !== 'dir' || !PADRAO_PASTA.test(item.name)) return;
      if (item.name.slice(0, 10) < limite) return;
      lista.push({ nome: item.name, caminho: 'relatorios/' + mes + '/' + item.name });
    });
  });
  lista.sort(function (a, b) { return a.nome < b.nome ? 1 : -1; });
  return lista;
}

// ---------- Drive (escopo drive.file) ----------

function garantirPasta_(props, chave, nome, paiId) {
  const id = props.getProperty(chave);
  if (id && existe_(id)) return id;
  const meta = { name: nome, mimeType: MIME_PASTA };
  if (paiId) meta.parents = [paiId];
  const criada = Drive.Files.create(meta);
  props.setProperty(chave, criada.id);
  console.log('Pasta criada: ' + nome + ' (' + criada.id + ')');
  return criada.id;
}

function existe_(id) {
  try {
    const f = Drive.Files.get(id, { fields: 'id,trashed' });
    return !f.trashed;
  } catch (e) {
    return false;
  }
}

function blobMarkdown_(texto) {
  return Utilities.newBlob(texto, 'text/markdown', 'relatorio.md');
}

function arquivarSeNovo_(pastaId, nome, md) {
  const q = "name = '" + nome.replace(/'/g, "\\'") + "' and '" + pastaId + "' in parents and trashed = false";
  const achados = Drive.Files.list({ q: q, fields: 'files(id)', pageSize: 1 }).files;
  if (achados && achados.length) return; // relatórios anteriores nunca são alterados
  Drive.Files.create({ name: nome, mimeType: MIME_DOC, parents: [pastaId] }, blobMarkdown_(md));
  console.log('Arquivado: ' + nome);
}

/** Reescreve o Doc fixo mantendo o mesmo ID, para o NotebookLM continuar ligado a ele. */
function gravarDocFixo_(props, chave, titulo, pastaId, conteudo) {
  const id = props.getProperty(chave);
  if (id && existe_(id)) {
    Drive.Files.update({ name: titulo }, id, blobMarkdown_(conteudo));
    console.log('Atualizado: ' + titulo);
    return;
  }
  const criado = Drive.Files.create({ name: titulo, mimeType: MIME_DOC, parents: [pastaId] }, blobMarkdown_(conteudo));
  props.setProperty(chave, criado.id);
  console.log('Criado: ' + titulo + ' (' + criado.id + ')');
}
